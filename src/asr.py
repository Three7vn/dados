"""
Speech recognition using Whisper
"""

import whisper
try:
    import torch  # optional; whisper depends on it but guard just in case
except Exception:  # pragma: no cover
    torch = None
import numpy as np
from pathlib import Path
from data_logger import DataLogger


class ASREngine:
    def __init__(self, model_size="base", enable_logging=True):
        """
        Initialize Whisper model
        Model sizes: tiny, base, small, medium, large
        base = good balance of speed/accuracy
        """
        try:
            print(f"Loading Whisper model ({model_size})...")
            self.model = whisper.load_model(model_size)
            self.sample_rate = 16000
            # Use FP16 only if CUDA is available to avoid CPU warning
            self._use_fp16 = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
            print(f"Loaded Whisper model ({model_size})")
            
            # Initialize data logger (legacy; may be replaced by Dados event logger)
            self.logger = DataLogger() if enable_logging else None
            if self.logger:
                print("📝 Data logging enabled - saving audio/transcriptions for training")
                
        except Exception as e:
            print(f"Could not load Whisper model: {e}")
            raise
    
    def transcribe(self, audio_data):
        """Convert audio data to text using Whisper"""
        if not audio_data:
            return ""
        
        try:
            # Convert audio bytes to numpy array
            audio_np = self._bytes_to_numpy(audio_data)
            
            # Transcribe with Whisper
            result = self.model.transcribe(audio_np, language="en", fp16=self._use_fp16)
            text = result["text"].strip()
            
            # Log the audio and transcription (optional)
            if self.logger and text:
                self.logger.save_transcription(audio_data, text, self.sample_rate)
            
            return text
            
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return ""
    
    def _bytes_to_numpy(self, audio_data):
        """Convert audio bytes to numpy array for Whisper"""
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        
        # Convert to float32 and normalize to [-1, 1]
        audio_np = audio_np.astype(np.float32) / 32768.0
        
        return audio_np 