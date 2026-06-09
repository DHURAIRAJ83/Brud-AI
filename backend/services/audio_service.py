import logging
import os
import tempfile
import asyncio
import threading
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Lock to ensure only one thread accesses pyttsx3/SAPI5 at a time (critical on Windows)
_tts_lock = threading.Lock()

class AudioService:
    """
    Manages Speech-to-Text and Text-to-Speech tasks with robust local + online fallbacks.
    """
    def __init__(self):
        self.whisper_cpp_available = False
        try:
            from pywhispercpp.model import Model
            self.whisper_cpp_available = True
            logger.info("pywhispercpp is available for STT.")
        except ImportError:
            logger.info("pywhispercpp not installed. Will default to faster-whisper.")

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: Optional[str] = None
    ) -> dict:
        """
        Transcribe audio bytes using whisper.cpp (pywhispercpp) or fallback to faster-whisper.
        """
        if self.whisper_cpp_available:
            try:
                # Write to temp file (whisper.cpp needs file path)
                ext = Path(filename).suffix.lower() or ".wav"
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name

                try:
                    from pywhispercpp.model import Model
                    logger.info("Attempting transcription with pywhispercpp (whisper.cpp)...")
                    # whisper.cpp models are typically loaded using 'tiny', 'base', etc.
                    # We specify gpu=False or rely on compile-time config, but try to avoid crashes
                    model = Model('tiny')
                    
                    # Convert language codes ('ta' -> 'ta', etc.)
                    lang_code = language if language else None
                    
                    # Run transcription
                    segments = model.transcribe(tmp_path, language=lang_code)
                    
                    full_text = " ".join([s.text.strip() for s in segments]).strip()
                    logger.info("Successfully transcribed with whisper.cpp: %s...", full_text[:40])
                    
                    return {
                        "text": full_text,
                        "language": language or "auto",
                        "source": "whisper.cpp",
                        "duration_s": 0.0,  # Whispercpp segments list doesn't always contain duration info simply
                    }
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            except Exception as e:
                logger.warning("whisper.cpp transcription failed: %s. Falling back to faster-whisper.", e)
        
        # Fallback to faster-whisper
        from services.voice_service import voice_service
        logger.info("Transcribing using faster-whisper fallback...")
        res = voice_service.transcribe(audio_bytes, filename, language)
        res["source"] = "faster-whisper"
        return res

    async def speak(self, text: str, language: str = "ta") -> tuple[bytes, str]:
        """
        Synthesize text to speech.
        Tries offline pyttsx3 first. Falls back to edge-tts if no Tamil voice or output empty.
        Returns:
            (audio_bytes, mime_type)
        """
        lang = (language or "ta").lower()
        
        # 1. Attempt offline pyttsx3 (SAPI5 on Windows)
        pyttsx3_success = False
        temp_wav = os.path.join(tempfile.gettempdir(), f"tts_{os.getpid()}_{threading.get_ident()}.wav")
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except:
                pass

        try:
            import pyttsx3
            # Find if we have a voice matching the requested language
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            target_voice_id = None

            # Look for a voice matching language
            for voice in voices:
                # Tamil keys: 'tamil', 'ta-IN', 'valluvar'
                # English keys: 'english', 'en-US', 'zira', 'david'
                voice_name = voice.name.lower()
                voice_id = voice.id.lower()
                
                if lang == "ta" and ("tamil" in voice_name or "ta-in" in voice_id or "valluvar" in voice_name):
                    target_voice_id = voice.id
                    break
                elif lang == "en" and ("english" in voice_name or "en-us" in voice_id or "zira" in voice_name or "david" in voice_name):
                    target_voice_id = voice.id
                    # Don't break immediately so we can look for Zira (usually better than David)
                    if "zira" in voice_name:
                        break

            # If translating to Tamil but no Tamil SAPI5 voice is installed, skip pyttsx3 to avoid English-gibberish
            if lang == "ta" and not target_voice_id:
                logger.warning("No native Tamil SAPI5 voice installed. Skipping pyttsx3 offline TTS.")
            else:
                # Run SAPI5 generation with thread-lock safety
                with _tts_lock:
                    if target_voice_id:
                        engine.setProperty('voice', target_voice_id)
                    engine.setProperty('rate', 150)  # Moderate speed
                    engine.save_to_file(text, temp_wav)
                    engine.runAndWait()
                    
                    # Need a tiny sleep to allow the SAPI5 background thread to write out
                    await asyncio.sleep(0.2)

                # Check if file exists and has actual audio data (more than 46-byte wav header)
                if os.path.exists(temp_wav) and os.path.getsize(temp_wav) > 100:
                    logger.info("Successfully generated speech offline using pyttsx3 (SAPI5).")
                    with open(temp_wav, "rb") as f:
                        audio_data = f.read()
                    pyttsx3_success = True
                    return audio_data, "audio/wav"
                else:
                    logger.warning("pyttsx3 save_to_file returned empty file (46 bytes). Trying fallback.")
        except Exception as e:
            logger.warning("pyttsx3 offline TTS failed: %s", e)
        finally:
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except:
                    pass

        # 2. Fallback: Online Edge-TTS (Premium neural voices)
        logger.info("Using online edge-tts fallback...")
        try:
            import edge_tts
            # Select appropriate voice
            # ta-IN-ValluvarNeural is excellent for Tamil
            # en-US-AriaNeural is excellent for English
            voice_map = {
                "ta": "ta-IN-ValluvarNeural",
                "en": "en-US-AriaNeural"
            }
            voice = voice_map.get(lang, "ta-IN-ValluvarNeural")
            
            communicate = edge_tts.Communicate(text, voice)
            
            # Write to a temp file and read bytes
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name
                
            try:
                await communicate.save(tmp_path)
                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    with open(tmp_path, "rb") as f:
                        audio_data = f.read()
                    logger.info("Successfully generated speech using Edge-TTS: %s", voice)
                    return audio_data, "audio/mpeg"
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except Exception as e:
            logger.error("Edge-TTS fallback failed: %s", e)
            
        # 3. Final Fallback: If both fail, force pyttsx3 even if empty/gibberish to prevent crash
        logger.info("Both TTS engines failed/unavailable. Forcing pyttsx3 default voice fallback.")
        try:
            import pyttsx3
            with _tts_lock:
                engine = pyttsx3.init()
                engine.save_to_file(text, temp_wav)
                engine.runAndWait()
            if os.path.exists(temp_wav):
                with open(temp_wav, "rb") as f:
                    data = f.read()
                os.remove(temp_wav)
                return data, "audio/wav"
        except Exception as last_error:
            logger.error("Final fallback failed: %s", last_error)
            
        raise RuntimeError("Failed to generate speech with all available TTS engines.")

# Singleton instance
audio_service = AudioService()
