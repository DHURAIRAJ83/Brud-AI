"""
Voice Input Service — Whisper STT (CPU-Friendly)
-------------------------------------------------
Uses faster-whisper (CTranslate2-based) which is 4× faster
than original Whisper on CPU with same accuracy.

Supported models (size vs speed on CPU):
  tiny    → fastest,  ~39MB,  good for short queries
  base    → balanced, ~74MB,  recommended
  small   → accurate, ~244MB, for long audio

Tamil support: Whisper natively supports Tamil (ISO code: "ta")

Usage:
  POST /api/voice/transcribe
  Body: multipart/form-data with audio file
  Returns: { "text": "...", "language": "ta", "duration_s": 4.2 }
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy-loaded model instance
_whisper_model = None
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")


def _get_model():
    """Lazy-load Whisper model on first use."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading Whisper model: %s (CPU)", WHISPER_MODEL_SIZE)
            _whisper_model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8",  # INT8 quantization = 2× faster on CPU
            )
            logger.info("✅ Whisper model loaded")
        except ImportError:
            raise RuntimeError(
                "faster-whisper not installed. Run: pip install faster-whisper"
            )
    return _whisper_model


class VoiceService:
    """Transcribes audio files to text using Whisper STT."""

    SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
    MAX_DURATION_S = 120  # 2 minutes max

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: Optional[str] = None,
    ) -> dict:
        """
        Transcribe audio bytes → text.

        Args:
            audio_bytes: Raw audio file content
            filename:    Original filename (used to detect format)
            language:    ISO code hint e.g. 'ta' for Tamil, None=auto-detect

        Returns:
            {
              "text": "transcribed text",
              "language": "ta",
              "language_probability": 0.98,
              "duration_s": 4.2,
              "segments": [...]
            }
        """
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported audio format '{ext}'. "
                f"Supported: {self.SUPPORTED_FORMATS}"
            )

        # Write to temp file (faster-whisper needs file path)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            model = _get_model()

            # Transcribe
            # language=None → auto-detect (detects Tamil well)
            segments, info = model.transcribe(
                tmp_path,
                language=language,          # 'ta' for Tamil, None = auto
                beam_size=3,               # Lower = faster on CPU
                vad_filter=True,           # Skip silence
                vad_parameters={
                    "min_silence_duration_ms": 500
                },
            )

            # Collect segments
            seg_list = []
            full_text_parts = []
            for seg in segments:
                seg_list.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                })
                full_text_parts.append(seg.text.strip())

            full_text = " ".join(full_text_parts).strip()

            logger.info(
                "Transcribed %.1fs audio → lang=%s (%.0f%%) | text='%s…'",
                info.duration,
                info.language,
                info.language_probability * 100,
                full_text[:50],
            )

            return {
                "text": full_text,
                "language": info.language,
                "language_probability": round(info.language_probability, 3),
                "duration_s": round(info.duration, 2),
                "segments": seg_list,
                "model": WHISPER_MODEL_SIZE,
            }

        finally:
            os.unlink(tmp_path)  # Always clean up temp file

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa
            return True
        except ImportError:
            return False


# Singleton
voice_service = VoiceService()
