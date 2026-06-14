"""
Challenge-Response Manager
--------------------------
Handles generating, speaking (in Tamil), and verifying spoken random digits liveness challenges.
"""

import logging
import httpx
import random
from typing import Callable, Optional
# Unshadow config module import for agent
import os
import importlib.util

def _get_agent_settings():
    try:
        from config import get_settings
        s = get_settings()
        if hasattr(s, "user_id"):
            return s
    except Exception:
        pass
    try:
        agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        config_path = os.path.join(agent_dir, "config.py")
        spec = importlib.util.spec_from_file_location("agent_config", config_path)
        agent_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent_config)
        return agent_config.get_settings()
    except Exception:
        class MockSettings:
            vps_url = "http://localhost:8000"
            user_id = "admin-user-123"
        return MockSettings()

settings = _get_agent_settings()
from voice.tts import tts_player
from voice.stt import stt_transcriber

logger = logging.getLogger(__name__)


class ChallengeManager:
    """Manages liveness challenge sequence and digit transcription normalizations."""

    def generate_challenge(self, auth_session_id: str) -> Optional[dict]:
        """Request the backend to create a challenge for this voice session."""
        # Generate 3 random digits spaced out
        random_digits = " ".join(str(random.randint(0, 9)) for _ in range(3))
        try:
            with httpx.Client(timeout=10.0) as client:
                headers = {"X-User-Id": settings.user_id}
                resp = client.post(
                    f"{settings.vps_url}/api/voice/auth-session/challenge",
                    headers=headers,
                    data={"auth_session_id": auth_session_id, "digits": random_digits}
                )
                if resp.status_code == 200:
                    return resp.json().get("challenge")
                else:
                    logger.warning("Failed to register challenge with backend: %d", resp.status_code)
        except Exception as e:
            logger.error("Failed to generate challenge on backend: %s", e)
        return None

    def speak_challenge(self, digits: str):
        """Translate numeric digits into Tamil speech text and playback via TTS."""
        tamil_digits = {
            "0": "பூஜ்யம்",
            "1": "ஒன்று",
            "2": "இரண்டு",
            "3": "மூன்று",
            "4": "நான்கு",
            "5": "ஐந்து",
            "6": "ஆறு",
            "7": "ஏழு",
            "8": "எட்டு",
            "9": "ஒன்பது"
        }
        
        spoken_parts = []
        for d in digits.split():
            spoken_parts.append(tamil_digits.get(d, d))
            
        spoken_text = " ".join(spoken_parts)
        prompt = f"உறுதிப்படுத்த இந்த எண்களைக் கூறவும்: {spoken_text}"
        logger.info("Speaking challenge prompt: %s", prompt)
        tts_player.speak(prompt)

    def verify_response(
        self,
        auth_session_id: str,
        challenge_id: str,
        challenge_digits: str,
        record_callback: Callable[[], bytes]
    ) -> bool:
        """Record spoken digits, transcribe, normalize, and verify against challenge."""
        # Speak challenge prompts
        self.speak_challenge(challenge_digits)

        # Record audio confirmation response
        logger.info("Recording challenge response speech...")
        audio_bytes = record_callback()
        if not audio_bytes:
            logger.warning("Empty recording for challenge confirmation.")
            return False

        # Transcribe speech
        logger.info("Transcribing challenge response...")
        stt_result = stt_transcriber.transcribe(audio_bytes, "challenge_response.wav")
        transcript = stt_result.get("text", "").strip()
        logger.info("Challenge Response raw transcript: '%s'", transcript)

        # Normalize transcript
        normalized_resp = self.normalize_digits(transcript)
        normalized_orig = challenge_digits.replace(" ", "")
        logger.info("Normalized Response: '%s', Expected: '%s'", normalized_resp, normalized_orig)

        # Submit verification to backend
        try:
            with httpx.Client(timeout=10.0) as client:
                headers = {"X-User-Id": settings.user_id}
                resp = client.post(
                    f"{settings.vps_url}/api/voice/auth-session/verify-challenge",
                    headers=headers,
                    data={
                        "auth_session_id": auth_session_id,
                        "challenge_id": challenge_id,
                        "digits": normalized_resp
                    }
                )
                if resp.status_code == 200:
                    return resp.json().get("success", False)
                else:
                    logger.warning("Backend challenge verification call failed: %d", resp.status_code)
        except Exception as e:
            logger.error("Failed to post challenge verification to backend: %s", e)

        return False

    def normalize_digits(self, text: str) -> str:
        """Map Tamil, Tanglish, and English digit names to numeric strings."""
        tamil_map = {
            "பூஜ்யம்": "0", "பூஜ்ஜியம்": "0", "ஒன்று": "1", "இரண்டு": "2",
            "மூன்று": "3", "நான்கு": "4", "ஐந்து": "5", "ஆறு": "6",
            "ஏழு": "7", "எட்டு": "8", "ஒன்பது": "9"
        }
        eng_map = {
            "zero": "0", "one": "1", "two": "2", "three": "3",
            "four": "4", "five": "5", "six": "6", "seven": "7",
            "eight": "8", "nine": "9"
        }
        tanglish_map = {
            "aaru": "6", "ettu": "8", "aezhu": "7", "ezhu": "7",
            "oatru": "1", "onru": "1", "irandu": "2", "moonru": "3",
            "naangu": "4", "aindhu": "5", "onbadhu": "9", "ettu.": "8",
            "etti": "8", "ett": "8"
        }
        
        cleaned = text.lower().strip()
        for word, val in tamil_map.items():
            cleaned = cleaned.replace(word, val)
        for word, val in tanglish_map.items():
            cleaned = cleaned.replace(word, val)
        for word, val in eng_map.items():
            cleaned = cleaned.replace(word, val)

        return "".join(c for c in cleaned if c.isdigit())


# Global singleton
challenge_manager = ChallengeManager()
