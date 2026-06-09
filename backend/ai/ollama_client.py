"""
Ollama Client — thin wrapper around the Ollama HTTP API.
Handles generation, error recovery, and CPU-friendly timeout management.
"""

import logging
from typing import Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OllamaClient:
    """Synchronous + async Ollama API client."""

    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout

    # ── Core generation ───────────────────────────────────────────────────────
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        """
        Send a prompt to Ollama and return the generated text.
        Keeps context window small for CPU efficiency.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": 2048,          # Small context → faster on CPU
                "num_thread": 4,           # Tune to your CPU core count
            },
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()

        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama. Is it running? (ollama serve)")
            raise RuntimeError(
                "Ollama service is not available. Run: ollama serve"
            )
        except httpx.TimeoutException:
            logger.error("Ollama request timed out after %ds", self.timeout)
            raise RuntimeError("LLM request timed out. Try a shorter prompt.")
        except httpx.HTTPStatusError as e:
            logger.error("Ollama HTTP error: %s", e)
            raise RuntimeError(f"LLM error: {e.response.text}")

    # ── Health check ─────────────────────────────────────────────────────────
    async def is_alive(self) -> bool:
        """Return True if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    # ── Available models ──────────────────────────────────────────────────────
    async def list_models(self) -> list[str]:
        """Return list of locally available model names."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]


# Singleton
ollama_client = OllamaClient()
