import whisper
import torch
import numpy as np


class WhisperRecognizer:
    def __init__(self, model_size="tiny", device="auto"):
        self.model_size = model_size
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self.model = None

    def load_model(self):
        try:
            print(f"正在加载 Whisper {self.model_size} 模型...")
            self.model = whisper.load_model(self.model_size, device=self.device)
            print(f"Whisper {self.model_size} 模型加载完成")
            return True
        except Exception as e:
            print(f"加载 Whisper 模型失败: {e}")
            return False

    def transcribe_audio_data(self, audio_bytes, sample_rate=16000):
        try:
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_float = audio_array.astype(np.float32) / 32768.0

            result = self.model.transcribe(
                audio_float,
                language="zh",
                fp16=self.device == "cuda",
                verbose=False
            )
            return result.get('text', '')
        except Exception as e:
            print(f"语音识别出错: {e}")
            return ''

    def transcribe_file(self, file_path):
        try:
            result = self.model.transcribe(
                file_path,
                language="zh",
                fp16=self.device == "cuda",
                verbose=False
            )
            return result.get('text', '')
        except Exception as e:
            print(f"识别文件出错: {e}")
            return ''
