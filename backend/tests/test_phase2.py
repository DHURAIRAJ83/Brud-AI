"""
Phase 2 Advanced Test Suite
Tests: Agent system, Model Router, Tamil Intelligence, Observability, Plugin System
"""

import asyncio
import pytest
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ─────────────────────────────────────────────────────────────────────────────
# Tamil Intelligence Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_language_detect_tamil():
    from ai.tamil_intelligence import tamil_intelligence, Language
    result = tamil_intelligence.detect_language("வணக்கம் நண்பா")
    assert result == Language.TAMIL
    print("✅ Language detect: Tamil script")


def test_language_detect_english():
    from ai.tamil_intelligence import tamil_intelligence, Language
    result = tamil_intelligence.detect_language("Hello, how are you?")
    assert result == Language.ENGLISH
    print("✅ Language detect: English")


def test_language_detect_tanglish():
    from ai.tamil_intelligence import tamil_intelligence, Language
    result = tamil_intelligence.detect_language("enna panra nee ippo")
    assert result == Language.TANGLISH
    print("✅ Language detect: Tanglish")


def test_tanglish_to_tamil_vanakkam():
    from ai.tamil_intelligence import tamil_intelligence
    result = tamil_intelligence.tanglish_to_tamil("vanakkam")
    assert "வணக்கம்" in result
    print(f"✅ Tanglish→Tamil: 'vanakkam' → '{result}'")


def test_tanglish_to_tamil_naan():
    from ai.tamil_intelligence import tamil_intelligence
    result = tamil_intelligence.tanglish_to_tamil("naan nandri solren")
    assert "நான்" in result
    assert "நன்றி" in result
    print(f"✅ Tanglish→Tamil multi-word: '{result}'")


def test_tanglish_normalize():
    from ai.tamil_intelligence import tamil_intelligence
    text, meta = tamil_intelligence.normalize_for_llm("enna panra romba nandri")
    assert meta["tanglish_converted"] is True
    assert meta["detected_language"] == "tanglish"
    print(f"✅ Normalize: tanglish_converted=True, lang=tanglish")


def test_no_conversion_for_english():
    from ai.tamil_intelligence import tamil_intelligence
    text, meta = tamil_intelligence.normalize_for_llm("What is machine learning?")
    assert meta["tanglish_converted"] is False
    assert meta["detected_language"] == "en"
    print("✅ English: no conversion applied")


def test_response_hint_for_tamil():
    from ai.tamil_intelligence import tamil_intelligence, Language
    hint = tamil_intelligence.get_response_language_hint(Language.TAMIL)
    assert "Tamil" in hint
    print(f"✅ Response hint: '{hint}'")


# ─────────────────────────────────────────────────────────────────────────────
# Model Router Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_router_simple_query_uses_fast():
    from ai.model_router import ModelRouter, ModelTier
    router = ModelRouter()
    model, tier = router.select_model("hi", "chat")
    assert tier == ModelTier.FAST
    print(f"✅ Router: simple query → {tier} → {model}")


def test_router_long_query_uses_balanced():
    from ai.model_router import ModelRouter, ModelTier
    router = ModelRouter()
    long_query = "Explain in detail the complete history of Tamil literature including sangam period " \
                 "and modern developments with examples from various poets and their contributions."
    model, tier = router.select_model(long_query, "chat")
    assert tier in (ModelTier.BALANCED, ModelTier.STRONG)
    print(f"✅ Router: long query → {tier} → {model}")


def test_router_score_calculator():
    from ai.model_router import ModelRouter
    router = ModelRouter()
    score = router.score("calculate 5 + 3", "calculate")
    # Should be low (calculate has complexity 0)
    assert score <= 2
    print(f"✅ Router score for 'calculate': {score}")


def test_router_override():
    from ai.model_router import ModelRouter
    router = ModelRouter()
    router.set_override("tinyllama")
    model, _ = router.select_model("very complex multi-step reasoning query " * 5, "chat")
    assert model == "tinyllama"
    router.set_override(None)
    print("✅ Router override: forced model respected")


# ─────────────────────────────────────────────────────────────────────────────
# Agent System Tests (no LLM — unit logic)
# ─────────────────────────────────────────────────────────────────────────────

def test_agent_complexity_simple():
    from ai.agent import Agent
    a = Agent()
    assert not a._is_complex("Hi, how are you?")
    print("✅ Agent complexity: 'hi' → NOT complex")


def test_agent_complexity_multi_step():
    from ai.agent import Agent
    a = Agent()
    assert a._is_complex("Analyze this PDF and summarize it then translate to Tamil")
    print("✅ Agent complexity: multi-step query → complex")


def test_agent_complexity_long():
    from ai.agent import Agent
    a = Agent()
    long_q = "word " * 30
    assert a._is_complex(long_q)
    print("✅ Agent complexity: long query (30 words) → complex")


# ─────────────────────────────────────────────────────────────────────────────
# Plugin System Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_plugin_registry_has_builtins():
    from tools.tool_engine import plugin_registry
    plugins = plugin_registry.list_plugins()
    names = [p["name"] for p in plugins]
    assert "Summarizer" in names
    assert "Calculator" in names
    assert "Translator" in names
    assert "FileReader" in names
    print(f"✅ Plugin registry: {len(plugins)} plugins loaded")


def test_plugin_registry_has_word_counter():
    from tools.tool_engine import plugin_registry
    plugins = plugin_registry.list_plugins()
    names = [p["name"] for p in plugins]
    assert "word_counter" in names
    print("✅ Plugin: word_counter auto-loaded from plugins/")


@pytest.mark.asyncio
async def test_word_counter_plugin():
    from tools.tool_engine import tool_engine
    result = await tool_engine.execute("count_words", "Hello world this is a test")
    assert "6" in result["result"] or "Words" in result["result"]
    print("✅ Plugin execution: word_counter working")


# ─────────────────────────────────────────────────────────────────────────────
# Observability Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_obs_record_and_metrics():
    from services.observability import ObservabilityService
    obs = ObservabilityService()
    obs.record("sess1", "chat", "mistral", "llm", 120.5, "hello", "world")
    obs.record("sess2", "calculate", "tinyllama", "tool", 45.0, "2+2", "4")
    obs.record("sess3", "summarize", "mistral", "tool", 200.0, "text", "", error="timeout")

    m = obs.get_metrics()
    assert m["total_requests"] == 3
    assert m["total_errors"] == 1
    assert m["error_rate"] == pytest.approx(1/3, abs=0.01)
    assert "chat" in m["intent_distribution"]
    assert "mistral" in m["model_usage"]
    print(f"✅ Observability: {m['total_requests']} requests tracked, error_rate={m['error_rate']:.2f}")


def test_obs_recent_errors():
    from services.observability import ObservabilityService
    obs = ObservabilityService()
    obs.record("s1", "chat", "m", "llm", 100.0, "q", "a", error="timeout")
    errors = obs.get_recent_errors()
    assert len(errors) > 0
    print(f"✅ Observability: error log has {len(errors)} entry/entries")


# ─────────────────────────────────────────────────────────────────────────────
# Monetization Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_monetization_record():
    from services.monetization import MonetizationService
    m = MonetizationService()
    rec = m.record("key123", "standard", "sess1", "chat", "mistral", 500)
    assert rec.tokens_estimated == 500
    assert rec.cost_units == pytest.approx(0.5, abs=0.001)
    print(f"✅ Monetization: tokens=500 → cost_units={rec.cost_units}")


def test_monetization_quota_pass():
    from services.monetization import MonetizationService
    m = MonetizationService()
    allowed, info = m.check_quota("key_new", "standard")
    assert allowed is True
    print("✅ Monetization: quota check passes for fresh key")


def test_monetization_quota_admin_unlimited():
    from services.monetization import MonetizationService
    m = MonetizationService()
    allowed, info = m.check_quota("admin_key", "admin")
    assert allowed is True
    assert info["quota"] == "unlimited"
    print("✅ Monetization: admin tier has unlimited quota")


def test_monetization_summary():
    from services.monetization import MonetizationService
    m = MonetizationService()
    m.record("k1", "standard", "s1", "chat", "mistral", 100)
    m.record("k1", "standard", "s2", "chat", "mistral", 200)
    summary = m.get_usage_summary("k1")
    assert "k1" in summary
    print(f"✅ Monetization: usage summary: {summary}")
