import time
import threading
import numpy as np
from collections import deque
from audio_capture import AudioCapture
from whisper_recognizer import WhisperRecognizer
from vad_processor import VADProcessor
from tes_detector import TESDetector, GameState
from config import TES_CONFIG


class RealtimeTESMonitor:
    def __init__(self, whisper_model="medium", device="auto"):
        self.audio_capture = AudioCapture()
        self.whisper = WhisperRecognizer(model_size=whisper_model, device=device)
        self.vad = VADProcessor(sample_rate=16000)
        self.detector = TESDetector()

        self.is_running = False
        self.ai_result = None
        self.ai_reasoning = None
        self.result_lock = threading.Lock()

        self.speech_buffer = bytearray()
        self.is_in_speech = False
        self.silence_frames = 0
        self.max_speech_duration = 10.0
        self.min_speech_duration = 0.3
        self.silence_threshold_seconds = 0.8
        self.silence_accumulated_seconds = 0.0
        self.vad_threshold = 0.4
        self.game_ended = False

        self.vad_buffer = bytearray()
        self.last_speech_prob = 0.0
        self.vad_frame_bytes = 1024  # 512 samples * 2 bytes (16kHz mono int16)

        self.audio_buffer = deque(maxlen=int(16000 * 3))

    def display_status(self):
        while self.is_running:
            with self.result_lock:
                result = self.ai_result
                reasoning = self.ai_reasoning
                state = self.detector.current_state
                state_desc = self.detector._get_state_description(state)

            if result == "victory":
                print(f"\r[实时状态] TES胜利 | 理由: {reasoning[:50]}...", end="", flush=True)
            elif result == "defeat":
                print(f"\r[实时状态] TES失败 | 理由: {reasoning[:50]}...", end="", flush=True)
            elif reasoning:
                print(f"\r[实时状态] {state_desc} | 理由: {reasoning[:50]}...", end="", flush=True)
            else:
                print(f"\r[实时状态] {state_desc} | 监听中...", end="", flush=True)

            time.sleep(0.5)

    def ai_judge_async(self, text):
        def judge():
            action = self.detector.process_text(text)
            with self.result_lock:
                self.ai_result = action
                self.ai_reasoning = self.detector.last_reasoning

        thread = threading.Thread(target=judge, daemon=True)
        thread.start()

    def process_speech_segment(self, audio_bytes):
        try:
            duration = len(audio_bytes) / (16000 * 2)
            if duration < self.min_speech_duration:
                return

            print(f"\n[检测到语音] 长度: {duration:.2f}s，正在识别...")
            text = self.whisper.transcribe_audio_data(bytes(audio_bytes), sample_rate=16000)

            if text and text.strip():
                print(f"[Whisper识别] {text}")
                self.ai_judge_async(text)
            else:
                print("[识别结果为空]")
        except Exception as e:
            print(f"处理语音段出错: {e}")

    def run(self):
        print("=" * 60)
        print("      TES战队比赛实时AI监听系统")
        print("=" * 60)
        print("\n系统说明:")
        print("- 持续实时监听比赛解说音频")
        print("- 使用 Silero VAD 检测人声")
        print("- 使用 Whisper 进行语音识别")
        print("- 使用 DeepSeek AI 持续跟踪比赛状态")
        print("- 胜利时自动关闭系统，失败时打开安慰视频")
        print("- 按 Ctrl+C 可手动停止\n")

        print("正在加载 Whisper 模型...")
        if not self.whisper.load_model():
            print("Whisper 模型加载失败，程序退出")
            return

        print("\nTES检测配置:")
        print(f"  Whisper模型: {self.whisper.model_size}")
        print(f"  设备: {self.whisper.device}")
        print(f"  上下文窗口: {TES_CONFIG['context_window_size']}段解说")
        print(f"  安慰视频: {TES_CONFIG['comfort_video_url']}")

        print("\n正在启动实时录音...")
        if not self.audio_capture.start_recording():
            print("启动录音失败，程序退出")
            return

        self.is_running = True

        status_thread = threading.Thread(target=self.display_status, daemon=True)
        status_thread.start()

        print("\n[OK] 实时监听已启动，正在持续分析比赛解说...")

        try:
            while self.is_running:
                with self.result_lock:
                    action = self.ai_result
                    if action in ("victory", "defeat") and not self.game_ended:
                        self.game_ended = True
                        self.is_running = False
                        if action == "victory":
                            self.detector.handle_victory()
                        else:
                            self.detector.handle_defeat()
                        break

                chunk = self.audio_capture.get_audio_chunk(timeout=0.1)
                if not chunk:
                    continue

                converted_chunk = self.audio_capture.convert_to_target_format(chunk)
                if not converted_chunk:
                    continue

                self.vad_buffer.extend(converted_chunk)
                while len(self.vad_buffer) >= self.vad_frame_bytes:
                    vad_frame = self.vad_buffer[:self.vad_frame_bytes]
                    self.vad_buffer = self.vad_buffer[self.vad_frame_bytes:]
                    self.last_speech_prob = self.vad.is_speech(vad_frame)

                chunk_samples = len(converted_chunk) // 2
                chunk_duration = chunk_samples / 16000
                speech_prob = self.last_speech_prob

                if speech_prob >= self.vad_threshold:
                    if not self.is_in_speech:
                        self.is_in_speech = True
                        self.silence_accumulated_seconds = 0.0
                        self.speech_buffer = bytearray(converted_chunk)
                    else:
                        self.speech_buffer.extend(converted_chunk)

                    duration = len(self.speech_buffer) / (16000 * 2)
                    if duration >= self.max_speech_duration:
                        self.process_speech_segment(bytes(self.speech_buffer))
                        self.is_in_speech = False
                        self.silence_accumulated_seconds = 0.0
                        self.speech_buffer = bytearray()
                else:
                    if self.is_in_speech:
                        self.silence_accumulated_seconds += chunk_duration
                        self.speech_buffer.extend(converted_chunk)

                        if self.silence_accumulated_seconds >= self.silence_threshold_seconds:
                            self.process_speech_segment(bytes(self.speech_buffer))
                            self.is_in_speech = False
                            self.silence_accumulated_seconds = 0.0
                            self.speech_buffer = bytearray()

        except KeyboardInterrupt:
            print("\n\n用户手动停止监听")
        except Exception as e:
            print(f"\n监听过程中出错: {e}")
        finally:
            self.is_running = False
            print("\n正在清理资源...")
            self.audio_capture.cleanup()
            self.detector.cleanup()
            print("系统已退出")


def main():
    monitor = RealtimeTESMonitor(
        whisper_model="medium",
        device="auto"
    )
    monitor.run()


if __name__ == "__main__":
    main()
