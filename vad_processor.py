import numpy as np
import torch
import silero_vad

class VADProcessor:
    """人声活动检测，优先使用 Silero VAD，失败时使用 WebRTC VAD 或能量阈值"""

    def __init__(self, sample_rate=16000, threshold=0.5, min_speech_duration_ms=250,
                 min_silence_duration_ms=500, speech_pad_ms=100):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms
        self.model = None
        self.webrtc_vad = None
        self._load_model()

    def _load_model(self):
        """加载 Silero VAD 模型"""
        try:
            self.model = silero_vad.load_silero_vad()
            print("Silero VAD 模型加载成功")
        except Exception as e:
            print(f"Silero VAD 模型加载失败: {e}")
            self._init_webrtc_vad()

    def _init_webrtc_vad(self):
        """初始化 WebRTC VAD 作为备用"""
        try:
            import webrtcvad
            self.webrtc_vad = webrtcvad.Vad(2)  #  aggressiveness 0-3
            print("WebRTC VAD 备用检测已启用")
        except Exception as e:
            print(f"WebRTC VAD 初始化失败: {e}")
            print("将使用简单能量阈值作为备用VAD")

    def _bytes_to_float(self, audio_data):
        """统一转换为 float32 numpy array [-1, 1]"""
        if isinstance(audio_data, (bytes, bytearray)):
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
        elif isinstance(audio_data, np.ndarray):
            audio_array = audio_data
        else:
            audio_array = np.array(audio_data)

        if audio_array.dtype == np.int16:
            return audio_array.astype(np.float32) / 32768.0
        return audio_array.astype(np.float32)

    def is_speech(self, audio_data):
        """判断一段音频是否包含人声，返回概率 0-1"""
        # Silero VAD
        if self.model is not None:
            try:
                audio_float = self._bytes_to_float(audio_data)
                min_samples = int(self.sample_rate / 31.25)
                if len(audio_float) < min_samples:
                    audio_float = np.pad(audio_float, (0, min_samples - len(audio_float)), mode='constant')
                tensor = torch.from_numpy(audio_float)
                if tensor.dim() > 1:
                    tensor = tensor.mean(dim=1)
                with torch.no_grad():
                    speech_prob = self.model(tensor, self.sample_rate).item()
                return speech_prob
            except Exception as e:
                print(f"Silero VAD检测出错: {e}")

        # WebRTC VAD 备用
        if self.webrtc_vad is not None:
            try:
                if isinstance(audio_data, (bytes, bytearray)):
                    audio_bytes = bytes(audio_data)
                else:
                    audio_bytes = audio_data.astype(np.int16).tobytes()
                # WebRTC VAD 只支持 8/16/32kHz，帧长 10/20/30ms
                frame_duration = 30  # ms
                frame_length = int(self.sample_rate * frame_duration / 1000) * 2
                if len(audio_bytes) >= frame_length:
                    frame = audio_bytes[:frame_length]
                    is_speech = self.webrtc_vad.is_speech(frame, self.sample_rate)
                    return 1.0 if is_speech else 0.0
            except Exception as e:
                print(f"WebRTC VAD检测出错: {e}")

        # 能量阈值备用
        return self._fallback_vad(audio_data)

    def _fallback_vad(self, audio_data):
        """备用VAD：基于音频能量"""
        try:
            audio_array = self._bytes_to_float(audio_data)
            if len(audio_array) == 0:
                return 0.0
            energy = np.sqrt(np.mean(audio_array ** 2))
            normalized = min(energy * 3.0, 1.0)  # 调整能量缩放
            return normalized
        except Exception:
            return 0.0

    def get_speech_chunks(self, audio_data, return_probs=False):
        """使用 Silero VAD 切分语音段"""
        if self.model is None:
            return []

        try:
            audio_float = self._bytes_to_float(audio_data)
            tensor = torch.from_numpy(audio_float)
            if tensor.dim() > 1:
                tensor = tensor.mean(dim=1)

            timestamps = silero_vad.get_speech_timestamps(
                tensor,
                self.model,
                threshold=self.threshold,
                sampling_rate=self.sample_rate,
                min_speech_duration_ms=self.min_speech_duration_ms,
                min_silence_duration_ms=self.min_silence_duration_ms,
                speech_pad_ms=self.speech_pad_ms
            )

            if return_probs:
                return [(ts['start'], ts['end'], ts.get('prob', 0.0)) for ts in timestamps]
            return [(ts['start'], ts['end']) for ts in timestamps]
        except Exception as e:
            print(f"切分语音段出错: {e}")
            return []
