"""
Runtime Manager — Phase 4: Hybrid AI Runtime System
------------------------------------------------------
Manages three execution modes:
  - local   → Use local Ollama at localhost:11434
  - cloud   → Use VPS/cloud Ollama instance
  - hybrid  → Try local first; auto-failover to cloud (default)

Background task retries local Ollama every 60 s and auto-recovers.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Enums ─────────────────────────────────────────────────────────────────────

class RuntimeMode(str, Enum):
    LOCAL  = "local"
    CLOUD  = "cloud"
    HYBRID = "hybrid"


class ActiveRuntime(str, Enum):
    LOCAL  = "local"
    CLOUD  = "cloud"
    NONE   = "none"


# ── RuntimeManager ────────────────────────────────────────────────────────────

class RuntimeManager:
    """
    Singleton that tracks and switches between local and cloud AI runtimes.

    Usage:
        status = await runtime_manager.get_runtime()
        await runtime_manager.switch_runtime(RuntimeMode.CLOUD)
    """

    def __init__(self):
        self._mode: RuntimeMode = RuntimeMode(
            getattr(settings, "runtime_mode", "hybrid")
        )
        self._active: ActiveRuntime = ActiveRuntime.NONE
        self._local_available: bool = False
        self._cloud_available: bool = False
        self._active_model: str = getattr(settings, "ollama_model", "tinyllama")
        self._local_models: list[str] = []
        self._cloud_models: list[str] = []
        self._failover_count: int = 0
        self._last_local_check: float = 0.0
        self._last_cloud_check: float = 0.0
        self._retry_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    # ── Internal probes ───────────────────────────────────────────────────────

    async def _probe(self, url: str, timeout: float = 4.0) -> tuple[bool, list[str]]:
        """HTTP probe an Ollama endpoint. Returns (alive, model_names)."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(f"{url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["name"].split(":")[0] for m in data.get("models", [])]
                    return True, models
        except Exception:
            pass
        return False, []

    # ── Public check methods ──────────────────────────────────────────────────

    async def check_local(self) -> bool:
        """Probe local Ollama and update internal state."""
        url = getattr(settings, "ollama_base_url", "http://localhost:11434")
        alive, models = await self._probe(url)
        async with self._lock:
            self._local_available = alive
            self._local_models = models
            self._last_local_check = time.time()
        return alive

    async def check_cloud(self) -> bool:
        """Probe cloud Ollama and update internal state."""
        url = getattr(settings, "cloud_ollama_url", "")
        if not url:
            async with self._lock:
                self._cloud_available = False
                self._last_cloud_check = time.time()
            return False
        alive, models = await self._probe(url)
        async with self._lock:
            self._cloud_available = alive
            self._cloud_models = models
            self._last_cloud_check = time.time()
        return alive

    # ── Runtime resolution ────────────────────────────────────────────────────

    async def get_runtime(self) -> dict:
        """
        Return full runtime status dict. Resolves hybrid logic.
        This is the single source of truth for all runtime decisions.
        """
        async with self._lock:
            mode = self._mode
            local_ok = self._local_available
            cloud_ok = self._cloud_available

        if mode == RuntimeMode.LOCAL:
            resolved = ActiveRuntime.LOCAL if local_ok else ActiveRuntime.NONE
        elif mode == RuntimeMode.CLOUD:
            resolved = ActiveRuntime.CLOUD if cloud_ok else ActiveRuntime.NONE
        else:  # hybrid
            if local_ok:
                resolved = ActiveRuntime.LOCAL
            elif cloud_ok:
                resolved = ActiveRuntime.CLOUD
            else:
                resolved = ActiveRuntime.NONE

        async with self._lock:
            self._active = resolved

        return {
            "mode":            mode.value,
            "runtime":         resolved.value,
            "local_available": local_ok,
            "cloud_available": cloud_ok,
            "active_model":    self._active_model,
            "local_models":    self._local_models,
            "cloud_models":    self._cloud_models,
            "failover_count":  self._failover_count,
            "last_local_check": self._last_local_check,
            "last_cloud_check": self._last_cloud_check,
        }

    async def get_active_url(self) -> str:
        """Return the base URL of the currently active Ollama instance."""
        status = await self.get_runtime()
        if status["runtime"] == ActiveRuntime.LOCAL:
            return getattr(settings, "ollama_base_url", "http://localhost:11434")
        elif status["runtime"] == ActiveRuntime.CLOUD:
            return getattr(settings, "cloud_ollama_url", "")
        return getattr(settings, "ollama_base_url", "http://localhost:11434")

    # ── Mode switching ────────────────────────────────────────────────────────

    async def switch_runtime(self, mode: RuntimeMode) -> dict:
        """Explicitly switch runtime mode."""
        async with self._lock:
            old_mode = self._mode
            self._mode = mode
        logger.info("Runtime mode switched: %s → %s", old_mode.value, mode.value)
        return await self.get_runtime()

    async def set_active_model(self, model: str):
        async with self._lock:
            self._active_model = model

    # ── Failover helpers ──────────────────────────────────────────────────────

    async def _handle_failover(self):
        """Called when local goes offline during hybrid mode."""
        async with self._lock:
            if self._mode == RuntimeMode.HYBRID and self._cloud_available:
                self._failover_count += 1
                logger.warning(
                    "⚡ Failover #%d: local → cloud", self._failover_count
                )

    async def _handle_recovery(self):
        """Called when local comes back online during hybrid mode."""
        async with self._lock:
            if self._mode == RuntimeMode.HYBRID:
                logger.info("✅ Local Ollama recovered — switching back from cloud")

    # ── Background retry loop ─────────────────────────────────────────────────

    async def _retry_loop(self):
        """
        Background task: re-probe local Ollama every 60 s.
        Triggers failover/recovery events automatically.
        """
        await asyncio.sleep(5)  # Give startup a moment
        while True:
            try:
                prev_local = self._local_available
                await self.check_local()
                await self.check_cloud()

                now_local = self._local_available

                if prev_local and not now_local:
                    await self._handle_failover()
                elif not prev_local and now_local:
                    await self._handle_recovery()

            except Exception as exc:
                logger.debug("Runtime retry loop error: %s", exc)

            await asyncio.sleep(60)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def startup(self):
        """Run on app startup: initial probes + start background loop."""
        logger.info("🔍 Runtime Manager: probing AI endpoints…")
        await self.check_local()
        await self.check_cloud()
        status = await self.get_runtime()
        logger.info(
            "✅ Runtime: mode=%s  active=%s  local=%s  cloud=%s",
            status["mode"], status["runtime"],
            status["local_available"], status["cloud_available"],
        )
        self._retry_task = asyncio.create_task(self._retry_loop())

    async def shutdown(self):
        """Cancel background task on app shutdown."""
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

    # ── Model discovery ───────────────────────────────────────────────────────

    async def list_models(self) -> dict:
        """Return available models on both local and cloud."""
        return {
            "local": self._local_models or [],
            "cloud": self._cloud_models or [],
        }

    # ── Auto model routing ────────────────────────────────────────────────────

    def score_query(self, query: str) -> int:
        """
        Score a query to decide model tier.
          0-1 → TinyLlama
          2-3 → Mistral
          4+  → Llama3
        """
        score = 0
        words = query.split()
        # Length factor
        if len(words) > 30:
            score += 2
        elif len(words) > 15:
            score += 1
        # Question marks (complexity indicator)
        score += min(query.count("?"), 2)
        # Technical keywords
        technical = [
            "explain", "compare", "analyze", "difference", "why", "how",
            "complex", "detailed", "elaborate", "comprehensive",
            "formula", "algorithm", "implement", "architecture",
        ]
        score += sum(1 for kw in technical if kw.lower() in query.lower())
        return score

    def route_model(self, query: str, override: Optional[str] = None) -> str:
        """Return the best model name for a given query."""
        if override:
            return override
        score = self.score_query(query)
        if score <= 1:
            return getattr(settings, "llm_fast", "tinyllama")
        elif score <= 3:
            return getattr(settings, "llm_balanced", "mistral")
        else:
            return getattr(settings, "llm_strong", "llama3")


# ── Singleton ─────────────────────────────────────────────────────────────────
runtime_manager = RuntimeManager()
