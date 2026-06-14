import tempfile
import os
import logging
import httpx
from pathlib import Path
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class STTTranscriber:
    def __init__(self):
        self._local_model = None

    def _get_local_model(self):
        if self._local_model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info("Loading local Whisper model for fallback STT...")
                self._local_model = WhisperModel("base", device="cpu", compute_type="int8")
                logger.info("✅ Local Whisper model loaded")
            except Exception as e:
                logger.error("Could not import faster-whisper locally: %s", e)
                raise RuntimeError("faster-whisper not available locally")
        return self._local_model

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav", language: str = None) -> dict:
        """
        Transcribe audio bytes to text.
        Primary: call VPS backend /api/voice/transcribe.
        Fallback: offline local faster-whisper.
        """
        if not settings.stt_enabled:
            logger.info("STT is disabled in settings.")
            return {"text": "", "language": "en", "confidence": 1.0, "source": "disabled"}

        # Try backend primary
        try:
            with httpx.Client(timeout=30.0) as client:
                files = {"audio": (filename, audio_bytes, "audio/wav")}
                # Try voice/transcribe endpoint
                response = client.post(
                    f"{settings.vps_url}/api/voice/transcribe",
                    files=files,
                    data={"language": language} if language else {}
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "text": data.get("text", "").strip(),
                        "language": data.get("language", "ta"),
                        "confidence": data.get("language_probability", 1.0),
                        "source": "backend"
                    }
                else:
                    logger.warning("Backend /api/voice/transcribe status %d. Trying /api/audio/transcribe...", response.status_code)
                    files = {"audio": (filename, audio_bytes, "audio/wav")}
                    response = client.post(
                        f"{settings.vps_url}/api/audio/transcribe",
                        files=files,
                        data={"language": language} if language else {}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "text": data.get("text", "").strip(),
                            "language": data.get("language", "ta"),
                            "confidence": data.get("language_probability", 1.0) if "language_probability" in data else 0.80,
                            "source": "backend_legacy"
                        }
                    else:
                        raise RuntimeError(f"Backend STT failed with status {response.status_code}")
        except Exception as e:
            logger.warning("Primary Backend STT failed: %s. Falling back to local offline STT...", e)
            return self._transcribe_locally(audio_bytes, filename, language)

    def _transcribe_locally(self, audio_bytes: bytes, filename: str, language: str) -> dict:
        """Fallback: run faster-whisper locally on the agent machine."""
        ext = Path(filename).suffix.lower() or ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            model = self._get_local_model()
            segments, info = model.transcribe(
                tmp_path,
                language=language,
                beam_size=3,
                vad_filter=True
            )
            full_text = " ".join([seg.text.strip() for seg in segments]).strip()
            logger.info("Local STT transcribed: %s", full_text)
            return {
                "text": full_text,
                "language": info.language,
                "confidence": info.language_probability,
                "source": "local_fallback"
            }
        except Exception as e:
            logger.error("Local STT fallback failed: %s", e)
            return {
                "text": "",
                "language": "ta",
                "confidence": 0.0,
                "source": "error",
                "error": str(e)
            }
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass


# Global singleton
stt_transcriber = STTTranscriber()
