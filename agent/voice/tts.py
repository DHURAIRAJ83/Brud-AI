import io
import wave
import logging
import threading
import httpx
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TTSPlayer:
    def __init__(self):
        self._interrupt_event = threading.Event()
        self._playing = False
        self._engine = None

    def interrupt(self):
        """Set the interrupt flag to stop current audio playback immediately."""
        logger.info("TTSPlayer: Interrupt triggered.")
        self._interrupt_event.set()
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

    def speak(self, text: str, voice_profile: str = None) -> bool:
        """
        Speak text using resolved voice profiles, with robust fallbacks and chunked interruptible playback.
        Returns True if played successfully, False otherwise (or interrupted).
        """
        if not settings.tts_enabled:
            logger.info("TTS is disabled in settings.")
            return False

        self._interrupt_event.clear()
        self._playing = True

        lang = "ta"
        # Determine language based on text or voice profile
        if voice_profile and "en" in voice_profile.lower():
            lang = "en"
        elif any(char.isalpha() and ord(char) < 128 for char in text):
            # Contains English chars, let's look if it's mostly English
            english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
            tamil_chars = sum(1 for char in text if 0x0B80 <= ord(char) <= 0x0BFF)
            if english_chars > tamil_chars:
                lang = "en"

        try:
            # Call backend TTS speak endpoint
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    f"{settings.vps_url}/api/audio/speak",
                    json={"text": text, "language": lang}
                )
                if response.status_code != 200:
                    logger.warning("Backend TTS failed, status %d. Falling back to pyttsx3 offline.", response.status_code)
                    return self._speak_offline(text, lang)
                
                audio_bytes = response.content
                mime_type = response.headers.get("content-type", "audio/wav")
                
                return self._play_audio(audio_bytes, mime_type)
                
        except Exception as e:
            logger.warning("Failed to connect to backend TTS: %s. Falling back to pyttsx3 offline.", e)
            return self._speak_offline(text, lang)
        finally:
            self._playing = False

    def _play_audio(self, audio_bytes: bytes, mime_type: str) -> bool:
        """Play WAV audio in small chunks, checking for interrupt signal in between."""
        try:
            import pyaudio
        except ImportError:
            logger.warning("PyAudio not installed. Cannot play audio in desktop client.")
            return False

        try:
            if not audio_bytes.startswith(b"RIFF"):
                logger.warning("Audio bytes do not look like a WAV file (missing RIFF header).")
                return False

            f = io.BytesIO(audio_bytes)
            wf = wave.open(f, 'rb')
            
            p = pyaudio.PyAudio()
            
            # Determine speaker index
            speaker_idx = None
            if settings.speaker_device_index != "default":
                try:
                    speaker_idx = int(settings.speaker_device_index)
                except ValueError:
                    pass

            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=speaker_idx
            )
            
            # Play in 1024-byte chunks
            chunk = 1024
            data = wf.readframes(chunk)
            
            interrupted = False
            while len(data) > 0:
                if self._interrupt_event.is_set():
                    logger.info("Playback interrupted verbally!")
                    interrupted = True
                    break
                stream.write(data)
                data = wf.readframes(chunk)
                
            stream.stop_stream()
            stream.close()
            p.terminate()
            wf.close()
            
            return not interrupted
            
        except Exception as e:
            logger.error("Error playing audio: %s", e)
            return False

    def _speak_offline(self, text: str, lang: str) -> bool:
        """Fallback to local SAPI5 (pyttsx3) on Windows."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)
            
            # SAPI5 voice setup
            voices = engine.getProperty('voices')
            target_voice_id = None
            for voice in voices:
                voice_name = voice.name.lower()
                voice_id = voice.id.lower()
                if lang == "ta" and ("tamil" in voice_name or "ta-in" in voice_id or "valluvar" in voice_name):
                    target_voice_id = voice.id
                    break
                elif lang == "en" and ("english" in voice_name or "en-us" in voice_id or "zira" in voice_name):
                    target_voice_id = voice.id
                    break
            
            if target_voice_id:
                engine.setProperty('voice', target_voice_id)
                
            self._engine = engine
            
            def run_tts():
                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    pass
                
            t = threading.Thread(target=run_tts)
            t.start()
            
            while t.is_alive():
                if self._interrupt_event.is_set():
                    logger.info("Offline SAPI5 Playback interrupted!")
                    try:
                        engine.stop()
                    except Exception:
                        pass
                    break
                t.join(timeout=0.1)
                
            return not self._interrupt_event.is_set()
        except Exception as e:
            logger.error("Offline TTS fallback failed: %s", e)
            return False


# Global singleton
tts_player = TTSPlayer()
