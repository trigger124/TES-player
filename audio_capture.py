import pyaudiowpatch as pyaudio
import numpy as np
import threading
import queue
import torch
import torchaudio


class AudioCapture:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.stream = None
        self.audio_queue = queue.Queue(maxsize=100)
        self.is_recording = False
        self.recording_thread = None
        self.device_info = None
        self.resampler = None

    def get_default_speaker_device(self):
        try:
            speakers = self.pa.get_default_output_device_info()
            if speakers.get('isLoopbackDevice', False):
                return speakers

            speaker_name = speakers.get('name', '')
            loopback_devices = []
            for i in range(self.pa.get_device_count()):
                device = self.pa.get_device_info_by_index(i)
                if device.get('isLoopbackDevice', False):
                    loopback_devices.append(device)
                    if speaker_name and speaker_name in device.get('name', ''):
                        return device

            return loopback_devices[0] if loopback_devices else None
        except Exception as e:
            print(f"获取扬声器设备失败: {e}")
            return None

    def start_recording(self):
        self.device_info = self.get_default_speaker_device()
        if not self.device_info:
            print("未找到扬声器回环设备")
            return False

        source_rate = int(self.device_info['defaultSampleRate'])
        print(f"使用设备: {self.device_info['name']}")
        print(f"采样率: {source_rate}")

        if source_rate != 16000:
            self.resampler = torchaudio.transforms.Resample(source_rate, 16000)
        else:
            self.resampler = None

        self.is_recording = True
        self.recording_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.recording_thread.start()
        return True

    def _record_loop(self):
        try:
            sample_rate = int(self.device_info['defaultSampleRate'])
            chunk_size = 1024

            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=2,
                rate=sample_rate,
                input=True,
                input_device_index=self.device_info['index'],
                frames_per_buffer=chunk_size
            )

            while self.is_recording:
                try:
                    data = self.stream.read(chunk_size, exception_on_overflow=False)
                    if data:
                        self.audio_queue.put(data)
                except Exception as e:
                    print(f"读取音频数据出错: {e}")
                    break

        except Exception as e:
            print(f"录音线程出错: {e}")
        finally:
            self.cleanup()

    def get_audio_chunk(self, timeout=0.1):
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def convert_to_target_format(self, audio_chunk):
        try:
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_array = audio_array.reshape(-1, 2)
            audio_mono = audio_array.mean(axis=1).astype(np.float32) / 32768.0

            if self.resampler is not None:
                tensor = torch.from_numpy(audio_mono).unsqueeze(0)
                tensor = self.resampler(tensor)
                audio_mono = tensor.squeeze(0).numpy()

            return (audio_mono * 32768.0).astype(np.int16).tobytes()
        except Exception as e:
            print(f"音频格式转换出错: {e}")
            return None

    def cleanup(self):
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self.pa.terminate()
