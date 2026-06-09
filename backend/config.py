"""
Config v3 — adds Phase 2 settings + Phase 4 Hybrid Runtime settings.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama — Local
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    ollama_timeout: int = 60

    # Ollama — Cloud / VPS (Phase 4)
    cloud_ollama_url: str = ""          # e.g. "http://your-vps:11434"
    runtime_mode: str = "hybrid"        # local | cloud | hybrid
    cloud_consent: bool = False         # set True once user consents

    # Smart Model Router (llm_ prefix avoids pydantic namespace conflict)
    llm_fast: str = "tinyllama"
    llm_balanced: str = "tinyllama"  # Fallback to tinyllama if mistral isn't pulled yet
    llm_strong: str = "tinyllama"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # RAG
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5

    # Memory
    memory_max_turns: int = 10

    # Upload
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 20

    # Cache
    cache_max_size: int = 256
    cache_ttl_seconds: int = 300

    # Security
    security_enabled: bool = False       # Set True in production
    api_keys: str = ""                   # "key1:admin,key2:standard"

    # Monetization
    billing_webhook_url: str = ""        # Stripe or custom webhook
    cost_per_1k_tokens: float = 0.001

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "protected_namespaces": ("settings_",)}


@lru_cache
def get_settings() -> Settings:
    return Settings()
