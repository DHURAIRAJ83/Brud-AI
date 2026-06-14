"""
Desktop Agent Configuration
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings

class AgentSettings(BaseSettings):
    # VPS Backend connection
    vps_url: str = "http://localhost:8000"
    api_key: str = ""
    user_id: str = "admin-user-123"

    # Agent identity
    device_name: str = "TamilAI-Desktop"
    device_type: str = "desktop"
    agent_version: str = "1.0.0"

    # Polling & Heartbeat
    poll_interval_seconds: float = 2.0
    heartbeat_interval_seconds: float = 30.0

    # Paths
    ocr_tesseract_cmd: Optional[str] = None  # e.g., "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

    # Voice settings
    voice_mode: bool = True
    voice_trigger_mode: str = "wakeword"  # "wakeword" or "push_to_talk"
    mic_device_index: str = "default"      # "default" or integer device ID
    speaker_device_index: str = "default"  # "default" or integer device ID
    wakeword_enabled: bool = True
    stt_enabled: bool = True
    tts_enabled: bool = True
    stt_confidence_threshold: float = 0.75
    wakeword_cooldown: float = 3.0
    voice_session_timeout: float = 15.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()
