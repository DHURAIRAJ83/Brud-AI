"""
Tests — Phase 4: Hybrid AI Runtime System
------------------------------------------
Covers:
  - Local available
  - Cloud available
  - Hybrid switch logic
  - Failover (local → cloud)
  - Recovery (cloud → local)
  - Consent persistence (localStorage equivalent via env)
  - Model scoring / auto-routing
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.runtime_manager import RuntimeManager, RuntimeMode, ActiveRuntime


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_manager(mode: str = "hybrid") -> RuntimeManager:
    """Create a fresh RuntimeManager with a specific mode."""
    mgr = RuntimeManager()
    mgr._mode = RuntimeMode(mode)
    return mgr


def _patch_probe(mgr: RuntimeManager, local_ok: bool, cloud_ok: bool,
                 local_models=None, cloud_models=None):
    """Patch the internal _probe method with fixed results."""
    local_models = local_models or (["tinyllama", "mistral"] if local_ok else [])
    cloud_models = cloud_models or (["tinyllama", "mistral", "llama3", "qwen3:8b"] if cloud_ok else [])

    async def fake_probe(url, timeout=4.0):
        if "localhost" in url or "127.0.0.1" in url:
            return local_ok, local_models
        return cloud_ok, cloud_models

    mgr._probe = fake_probe


# ── Test: Local available ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_local_available():
    mgr = make_manager("local")
    _patch_probe(mgr, local_ok=True, cloud_ok=False)
    alive = await mgr.check_local()
    assert alive is True
    assert mgr._local_available is True
    assert "tinyllama" in mgr._local_models


@pytest.mark.asyncio
async def test_local_unavailable():
    mgr = make_manager("local")
    _patch_probe(mgr, local_ok=False, cloud_ok=False)
    alive = await mgr.check_local()
    assert alive is False
    assert mgr._local_available is False
    assert mgr._local_models == []


# ── Test: Cloud available ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cloud_available():
    mgr = make_manager("cloud")
    # We need to set a cloud URL so the probe doesn't short-circuit
    with patch("services.runtime_manager.settings") as mock_settings:
        mock_settings.cloud_ollama_url = "http://vps.example.com:11434"
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_model = "mistral"
        mock_settings.llm_fast = "tinyllama"
        mock_settings.llm_balanced = "mistral"
        mock_settings.llm_strong = "llama3"
        _patch_probe(mgr, local_ok=False, cloud_ok=True)
        alive = await mgr.check_cloud()
    assert alive is True
    assert mgr._cloud_available is True
    assert "qwen3:8b" in mgr._cloud_models


@pytest.mark.asyncio
async def test_cloud_unavailable_no_url():
    """Cloud check must return False when no cloud URL is configured."""
    mgr = make_manager("cloud")
    with patch("services.runtime_manager.settings") as mock_settings:
        mock_settings.cloud_ollama_url = ""
        alive = await mgr.check_cloud()
    assert alive is False


# ── Test: Hybrid logic ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hybrid_prefers_local_when_both_available():
    mgr = make_manager("hybrid")
    mgr._local_available = True
    mgr._cloud_available = True
    status = await mgr.get_runtime()
    assert status["runtime"] == "local"
    assert status["mode"] == "hybrid"


@pytest.mark.asyncio
async def test_hybrid_falls_back_to_cloud_when_local_down():
    mgr = make_manager("hybrid")
    mgr._local_available = False
    mgr._cloud_available = True
    status = await mgr.get_runtime()
    assert status["runtime"] == "cloud"


@pytest.mark.asyncio
async def test_hybrid_none_when_both_down():
    mgr = make_manager("hybrid")
    mgr._local_available = False
    mgr._cloud_available = False
    status = await mgr.get_runtime()
    assert status["runtime"] == "none"


# ── Test: Mode switching ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_switch_to_cloud_mode():
    mgr = make_manager("hybrid")
    mgr._local_available = True
    mgr._cloud_available = True
    status = await mgr.switch_runtime(RuntimeMode.CLOUD)
    assert status["mode"] == "cloud"


@pytest.mark.asyncio
async def test_switch_to_local_mode():
    mgr = make_manager("cloud")
    mgr._local_available = True
    status = await mgr.switch_runtime(RuntimeMode.LOCAL)
    assert status["mode"] == "local"
    assert status["runtime"] == "local"


@pytest.mark.asyncio
async def test_switch_to_hybrid_mode():
    mgr = make_manager("local")
    status = await mgr.switch_runtime(RuntimeMode.HYBRID)
    assert status["mode"] == "hybrid"


# ── Test: Failover ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_failover_increments_count():
    mgr = make_manager("hybrid")
    mgr._local_available = True
    mgr._cloud_available = True
    initial_count = mgr._failover_count
    # Simulate local going offline
    mgr._local_available = False
    await mgr._handle_failover()
    assert mgr._failover_count == initial_count + 1


@pytest.mark.asyncio
async def test_failover_no_count_when_cloud_unavailable():
    mgr = make_manager("hybrid")
    mgr._local_available = False
    mgr._cloud_available = False  # no cloud to fail over to
    initial_count = mgr._failover_count
    await mgr._handle_failover()
    # Should NOT increment because cloud is also down
    assert mgr._failover_count == initial_count


@pytest.mark.asyncio
async def test_failover_only_in_hybrid_mode():
    mgr = make_manager("local")  # not hybrid
    mgr._cloud_available = True
    initial_count = mgr._failover_count
    await mgr._handle_failover()
    assert mgr._failover_count == initial_count  # no failover in local mode


# ── Test: Recovery ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recovery_restores_local_in_hybrid():
    mgr = make_manager("hybrid")
    mgr._local_available = False
    mgr._cloud_available = True
    # Simulate recovery
    mgr._local_available = True
    await mgr._handle_recovery()
    status = await mgr.get_runtime()
    assert status["runtime"] == "local"


# ── Test: Model routing ───────────────────────────────────────────────────────

def test_model_routing_simple_query():
    mgr = make_manager()
    with patch("services.runtime_manager.settings") as mock_settings:
        mock_settings.llm_fast = "tinyllama"
        mock_settings.llm_balanced = "mistral"
        mock_settings.llm_strong = "llama3"
        model = mgr.route_model("hi")
    assert model == "tinyllama"


def test_model_routing_medium_query():
    mgr = make_manager()
    with patch("services.runtime_manager.settings") as mock_settings:
        mock_settings.llm_fast = "tinyllama"
        mock_settings.llm_balanced = "mistral"
        mock_settings.llm_strong = "llama3"
        query = "Explain the difference between supervised and unsupervised learning algorithms"
        model = mgr.route_model(query)
    assert model == "mistral"


def test_model_routing_complex_query():
    mgr = make_manager()
    with patch("services.runtime_manager.settings") as mock_settings:
        mock_settings.llm_fast = "tinyllama"
        mock_settings.llm_balanced = "mistral"
        mock_settings.llm_strong = "llama3"
        query = (
            "Compare and analyze the architectural differences between transformer-based "
            "and recurrent neural network models. How do they differ in complexity, "
            "training efficiency, and long-range dependency handling? Elaborate in detail."
        )
        model = mgr.route_model(query)
    assert model == "llama3"


def test_model_routing_override():
    mgr = make_manager()
    model = mgr.route_model("simple question", override="llama3")
    assert model == "llama3"


# ── Test: Consent persistence ─────────────────────────────────────────────────

def test_consent_fields_in_settings():
    """Verify that cloud_ollama_url and runtime_mode fields exist in settings."""
    from config import get_settings
    s = get_settings()
    # These must exist and have defaults
    assert hasattr(s, "cloud_ollama_url")
    assert hasattr(s, "runtime_mode")


# ── Test: List models ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_models():
    mgr = make_manager("hybrid")
    mgr._local_models = ["tinyllama", "mistral"]
    mgr._cloud_models = ["tinyllama", "mistral", "llama3", "qwen3:8b"]
    result = await mgr.list_models()
    assert result["local"] == ["tinyllama", "mistral"]
    assert result["cloud"] == ["tinyllama", "mistral", "llama3", "qwen3:8b"]


# ── Test: Status structure ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_runtime_status_structure():
    mgr = make_manager("hybrid")
    mgr._local_available = True
    mgr._cloud_available = True
    mgr._active_model = "mistral"
    status = await mgr.get_runtime()
    required_keys = {
        "mode", "runtime", "local_available", "cloud_available",
        "active_model", "failover_count",
    }
    assert required_keys.issubset(status.keys())
    assert status["mode"] == "hybrid"
    assert status["active_model"] == "mistral"
    assert status["local_available"] is True


# ── Test: Score query ─────────────────────────────────────────────────────────

def test_score_simple():
    mgr = make_manager()
    assert mgr.score_query("hello") <= 1


def test_score_medium():
    mgr = make_manager()
    score = mgr.score_query("Explain how machine learning works in detail?")
    assert score >= 2


def test_score_complex():
    mgr = make_manager()
    score = mgr.score_query(
        "Compare and analyze the architectural differences between transformer-based "
        "and recurrent neural network models. How do they differ in complexity, "
        "training efficiency, and long-range dependency handling? Elaborate in detail "
        "with a comprehensive formula and algorithm explanation."
    )
    assert score >= 4
