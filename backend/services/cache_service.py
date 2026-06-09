"""
Cache Service — simple LRU + TTL cache for LLM responses.
Avoids re-running expensive LLM calls for identical queries.
"""

import hashlib
import logging
import time
from collections import OrderedDict

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheEntry:
    def __init__(self, value: str, ttl: int):
        self.value = value
        self.expires_at = time.time() + ttl


class CacheService:
    def __init__(self):
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = settings.cache_max_size
        self._ttl = settings.cache_ttl_seconds
        self._hits = 0
        self._misses = 0

    def init(self):
        logger.info(
            "Cache service ready (max=%d, ttl=%ds)", self._max_size, self._ttl
        )

    def _key(self, prompt: str, model: str) -> str:
        raw = f"{model}::{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, prompt: str, model: str) -> str | None:
        key = self._key(prompt, model)
        entry = self._store.get(key)
        if not entry:
            self._misses += 1
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            self._misses += 1
            return None
        # Move to end (LRU refresh)
        self._store.move_to_end(key)
        self._hits += 1
        logger.debug("Cache HIT for key %s…", key[:8])
        return entry.value

    def set(self, prompt: str, model: str, value: str):
        key = self._key(prompt, model)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = CacheEntry(value, self._ttl)
        if len(self._store) > self._max_size:
            evicted = self._store.popitem(last=False)
            logger.debug("Evicted cache entry: %s…", evicted[0][:8])

    def clear(self):
        self._store.clear()
        logger.info("Cache cleared")

    def stats(self) -> dict:
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": (
                round(self._hits / (self._hits + self._misses), 2)
                if (self._hits + self._misses) > 0 else 0
            ),
        }


# Singleton
cache_service = CacheService()
