"""
Voice Security Utilities
------------------------
Cryptographic signature and hashing helpers for biometric template integrity and replay detection.
"""

import hmac
import hashlib
import json
import logging
from typing import List
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def get_voice_secret() -> str:
    """Retrieve secret key for signing biometric embeddings."""
    secret = getattr(settings, "secret_key", None) or getattr(settings, "api_key", None)
    if not secret:
        raise RuntimeError("SECRET_KEY must be configured in environment (.env) for voice biometric security.")
    return secret

def sign_embedding(embedding: List[float], secret_key: str) -> str:
    """Generates an HMAC-SHA256 signature for a biometric float vector."""
    # Canonical JSON representation
    serialized = json.dumps(embedding, sort_keys=True)
    return hmac.new(
        secret_key.encode("utf-8"),
        serialized.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def verify_signature(embedding: List[float], signature: str, secret_key: str) -> bool:
    """Verifies that the embedding has not been tampered with."""
    expected = sign_embedding(embedding, secret_key)
    return hmac.compare_digest(expected, signature)

def generate_audio_hash(audio_bytes: bytes) -> str:
    """Generates a SHA-256 hash representing recorded WAV audio bytes."""
    return hashlib.sha256(audio_bytes).hexdigest()
