"""
Test Suite — Task 13: System Validation
Tests: Chat, Intent Detection, Tool Execution, RAG accuracy
"""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import sys, os

# Make sure backend is on the path when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from main import app


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_memory():
    from ai.sqlite_memory import sqlite_memory
    await sqlite_memory.init()


@pytest_asyncio.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    print("✅ Health check passed")


# ─────────────────────────────────────────────────────────────────────────────
# Intent Detection (unit — no LLM needed for keyword cases)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intent_keyword_summarize():
    from ai.intent_engine import IntentEngine
    engine = IntentEngine()
    result = engine._quick_classify("summarize this text for me")
    assert result is not None
    assert result["intent"] == "summarize"
    print("✅ Intent keyword 'summarize' detected")


@pytest.mark.asyncio
async def test_intent_keyword_calculate():
    from ai.intent_engine import IntentEngine
    engine = IntentEngine()
    result = engine._quick_classify("calculate 10 + 20")
    assert result is not None
    assert result["intent"] == "calculate"
    print("✅ Intent keyword 'calculate' detected")


@pytest.mark.asyncio
async def test_intent_keyword_translate():
    from ai.intent_engine import IntentEngine
    engine = IntentEngine()
    result = engine._quick_classify("translate this to english")
    assert result is not None
    assert result["intent"] == "translate"
    print("✅ Intent keyword 'translate' detected")


# ─────────────────────────────────────────────────────────────────────────────
# Calculator Tool (no LLM)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_calculator_basic_add():
    from tools.calculator import calculate_tool
    result = await calculate_tool("calculate 5 + 3")
    assert "8" in result
    print("✅ Calculator: 5 + 3 = 8")


@pytest.mark.asyncio
async def test_calculator_power():
    from tools.calculator import calculate_tool
    result = await calculate_tool("calculate 2 ^ 10")
    assert "1024" in result
    print("✅ Calculator: 2^10 = 1024")


@pytest.mark.asyncio
async def test_calculator_division():
    from tools.calculator import calculate_tool
    result = await calculate_tool("calculate 100 / 4")
    assert "25" in result
    print("✅ Calculator: 100 / 4 = 25")


# ─────────────────────────────────────────────────────────────────────────────
# Memory System (no LLM)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memory_add_and_retrieve():
    from ai.sqlite_memory import sqlite_memory
    await sqlite_memory.add_turn("session1", "user", "Hello, what is AI?")
    await sqlite_memory.add_turn("session1", "assistant", "AI is artificial intelligence.")
    ctx = await sqlite_memory.get_context("session1")
    assert "Hello" in ctx
    assert "artificial intelligence" in ctx
    print("✅ Memory: add and retrieve working")


@pytest.mark.asyncio
async def test_memory_session_isolation():
    from ai.sqlite_memory import sqlite_memory
    await sqlite_memory.add_turn("s1", "user", "Message for S1")
    ctx_s2 = await sqlite_memory.get_context("s2")
    assert ctx_s2 == ""
    print("✅ Memory: sessions are isolated")


@pytest.mark.asyncio
async def test_memory_max_turns():
    from ai.sqlite_memory import sqlite_memory
    for i in range(25):
        await sqlite_memory.add_turn("s_limit", "user", f"msg {i}")
    ctx = await sqlite_memory.get_context("s_limit")
    # deque maxlen=20 → stores last 20 entries; 25 user-only turns → 20 fit
    # All 20 stored entries are "User:" lines
    user_count = ctx.count("User:")
    assert user_count <= 20, f"Expected ≤ 20 User: lines, got {user_count}"
    # Verify old messages are trimmed (msg 0-4 should be gone)
    assert "msg 0" not in ctx
    assert "msg 24" in ctx
    print(f"✅ Memory: max_turns limit enforced — {user_count} turns retained")


# ─────────────────────────────────────────────────────────────────────────────
# RAG Engine (no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def test_rag_ingest_and_search(tmp_path):
    from ai.rag_engine import RAGEngine
    engine = RAGEngine()

    # Create a temp text file
    test_file = tmp_path / "test_doc.txt"
    test_file.write_text(
        "Tamil Nadu is a state in southern India. "
        "The capital city is Chennai. "
        "Tamil is the official language. "
        "The state has a rich cultural heritage and ancient literature.",
        encoding="utf-8",
    )

    count = engine.ingest_file(str(test_file))
    assert count > 0

    results = engine.search("What is the capital of Tamil Nadu?")
    assert len(results) > 0
    assert any("Chennai" in r["chunk"] for r in results)
    print(f"✅ RAG: ingested {count} chunks, search returned {len(results)} results")


# ─────────────────────────────────────────────────────────────────────────────
# Cache Service
# ─────────────────────────────────────────────────────────────────────────────

def test_cache_set_get():
    from services.cache_service import CacheService
    cache = CacheService()
    cache.set("hello world", "mistral", "Hello there!")
    result = cache.get("hello world", "mistral")
    assert result == "Hello there!"
    print("✅ Cache: set and get working")


def test_cache_miss():
    from services.cache_service import CacheService
    cache = CacheService()
    result = cache.get("nonexistent query", "mistral")
    assert result is None
    print("✅ Cache: miss returns None")


def test_cache_stats():
    from services.cache_service import CacheService
    cache = CacheService()
    cache.set("q1", "model", "ans1")
    cache.get("q1", "model")
    cache.get("q_missing", "model")
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    print("✅ Cache: stats tracking correct")
