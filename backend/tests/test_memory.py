"""
tests/test_memory.py — Persistent Memory System Tests (TASK 3)
===============================================================
Tests for memory_store CRUD, search, auto-extraction, and API endpoints.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from ai.memory_store import (
    MemoryStore,
    CATEGORY_USER_FACT,
    CATEGORY_PREFERENCE,
    CATEGORY_LONG_TERM,
    CATEGORY_USER_PREFERENCE,
    CATEGORY_PROJECT_CONTEXT,
    CATEGORY_DEVICE_LOG,
    CATEGORY_WORKFLOW_HISTORY,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def store(tmp_path):
    """Create a fresh in-memory MemoryStore backed by a temp SQLite file."""
    db_file = tmp_path / "test_memory.db"
    ms = MemoryStore(db_path=db_file)
    await ms.init()
    return ms


@pytest_asyncio.fixture
async def app_client(tmp_path):
    """Full FastAPI test client with memory_store pointing at temp DB."""
    db_file = tmp_path / "app_test.db"

    # Patch the singleton's db_path before app imports
    from ai import memory_store as ms_module
    ms_module.memory_store.db_path = db_file
    await ms_module.memory_store.init()

    from ai import sqlite_memory as sm_module
    sm_module.sqlite_memory.db_path = db_file
    await sm_module.sqlite_memory.init()

    from main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── Unit Tests: CRUD ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_and_retrieve_fact(store):
    uid = "user_001"
    fact_id = await store.save_fact(uid, "name", "Dhurairaj", CATEGORY_USER_FACT)
    assert fact_id > 0

    result = await store.retrieve_facts(uid)
    assert "Dhurairaj" in result
    assert "User Facts" in result


@pytest.mark.asyncio
async def test_upsert_fact(store):
    """Saving the same key twice should update, not duplicate."""
    uid = "user_002"
    id1 = await store.save_fact(uid, "name", "Old Name", CATEGORY_USER_FACT)
    id2 = await store.save_fact(uid, "name", "New Name", CATEGORY_USER_FACT)
    assert id1 == id2  # same row updated

    facts = await store.get_all_facts(uid)
    names = [f for f in facts if f["key"] == "name"]
    assert len(names) == 1
    assert names[0]["value"] == "New Name"


@pytest.mark.asyncio
async def test_preference_category(store):
    uid = "user_003"
    await store.save_fact(uid, "reply_language", "Tamil", CATEGORY_PREFERENCE)
    result = await store.retrieve_facts(uid)
    assert "User Preferences" in result
    assert "Tamil" in result


@pytest.mark.asyncio
async def test_long_term_context(store):
    uid = "user_004"
    await store.save_fact(uid, "interest", "machine learning", CATEGORY_LONG_TERM)
    result = await store.retrieve_facts(uid)
    assert "Long-term Context" in result
    assert "machine learning" in result


@pytest.mark.asyncio
async def test_delete_fact(store):
    uid = "user_005"
    fact_id = await store.save_fact(uid, "name", "Test User", CATEGORY_USER_FACT)
    deleted = await store.delete_fact(uid, fact_id)
    assert deleted is True

    facts = await store.get_all_facts(uid)
    assert len(facts) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_fact(store):
    deleted = await store.delete_fact("nobody", 999999)
    assert deleted is False


@pytest.mark.asyncio
async def test_delete_all_facts(store):
    uid = "user_006"
    await store.save_fact(uid, "name", "X", CATEGORY_USER_FACT)
    await store.save_fact(uid, "reply_language", "Tamil", CATEGORY_PREFERENCE)
    count = await store.delete_all_facts(uid)
    assert count == 2
    facts = await store.get_all_facts(uid)
    assert len(facts) == 0


@pytest.mark.asyncio
async def test_retrieve_empty(store):
    result = await store.retrieve_facts("no_such_user")
    assert result == ""


# ── Unit Tests: Auto-extraction ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_name(store):
    uid = "user_ext_001"
    saved = await store.extract_and_save(uid, "My name is Dhurairaj")
    keys = [s["key"] for s in saved]
    assert "name" in keys


@pytest.mark.asyncio
async def test_extract_language_preference(store):
    uid = "user_ext_002"
    saved = await store.extract_and_save(uid, "Reply in Tamil please")
    keys = [s["key"] for s in saved]
    assert "reply_language" in keys


@pytest.mark.asyncio
async def test_extract_age(store):
    uid = "user_ext_003"
    saved = await store.extract_and_save(uid, "I am 28 years old")
    keys = [s["key"] for s in saved]
    assert "age" in keys


@pytest.mark.asyncio
async def test_no_extraction_from_unrelated(store):
    uid = "user_ext_004"
    saved = await store.extract_and_save(uid, "What is the weather today?")
    assert len(saved) == 0


# ── Unit Tests: Search ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_memory(store):
    uid = "user_srch_001"
    await store.save_fact(uid, "name", "Dhurairaj", CATEGORY_USER_FACT)
    await store.save_fact(uid, "interest", "artificial intelligence", CATEGORY_LONG_TERM)

    results = await store.search_memory(uid, "Dhurairaj")
    assert len(results) >= 1
    assert any(r["value"] == "Dhurairaj" for r in results)


@pytest.mark.asyncio
async def test_search_no_results(store):
    uid = "user_srch_002"
    results = await store.search_memory(uid, "zzznomatch999")
    assert len(results) == 0


# ── Unit Tests: Admin ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memory_stats(store):
    await store.save_fact("u1", "name", "A", CATEGORY_USER_FACT)
    await store.save_fact("u2", "reply_language", "Tamil", CATEGORY_PREFERENCE)
    stats = await store.memory_stats()
    assert stats["total"] >= 2
    assert stats["unique_users"] >= 2


@pytest.mark.asyncio
async def test_purge_all(store):
    await store.save_fact("u1", "name", "A", CATEGORY_USER_FACT)
    await store.save_fact("u2", "name", "B", CATEGORY_USER_FACT)
    count = await store.purge_all()
    assert count >= 2
    stats = await store.memory_stats()
    assert stats["total"] == 0


# ── API Integration Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_save_memory(app_client):
    resp = await app_client.post(
        "/api/memory/test_user",
        json={"key": "name", "value": "Dhurairaj", "category": "user_fact"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "name"
    assert data["value"] == "Dhurairaj"


@pytest.mark.asyncio
async def test_api_list_memories(app_client):
    await app_client.post(
        "/api/memory/test_user2",
        json={"key": "reply_language", "value": "Tamil", "category": "preference"},
    )
    resp = await app_client.get("/api/memory/test_user2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_api_search_memory(app_client):
    await app_client.post(
        "/api/memory/test_user3",
        json={"key": "interest", "value": "deep learning", "category": "long_term_context"},
    )
    resp = await app_client.get("/api/memory/test_user3/search?q=deep")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_api_delete_memory(app_client):
    save_resp = await app_client.post(
        "/api/memory/test_user4",
        json={"key": "goal", "value": "learn Tamil", "category": "long_term_context"},
    )
    fact_id = save_resp.json()["id"]
    del_resp = await app_client.delete(f"/api/memory/test_user4/{fact_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == f"Memory {fact_id} deleted."


@pytest.mark.asyncio
async def test_api_invalid_category(app_client):
    resp = await app_client.post(
        "/api/memory/test_user5",
        json={"key": "x", "value": "y", "category": "invalid_category"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_list_all_memories(app_client):
    await app_client.post(
        "/api/memory/admin_test_user",
        json={"key": "name", "value": "Admin Test", "category": "user_fact"},
    )
    resp = await app_client.get("/api/admin/memories")
    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data
    assert "memories" in data


@pytest.mark.asyncio
async def test_admin_memory_stats(app_client):
    resp = await app_client.get("/api/admin/memory-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "memory_store" in data


@pytest.mark.asyncio
async def test_new_memory_namespaces(store):
    uid = "user_new_namespaces"
    
    # Save facts in the new categories
    await store.save_fact(uid, "editor_theme", "dark", CATEGORY_USER_PREFERENCE)
    await store.save_fact(uid, "active_workspace", "Tamil_AI", CATEGORY_PROJECT_CONTEXT)
    await store.save_fact(uid, "cpu_usage", "45%", CATEGORY_DEVICE_LOG)
    await store.save_fact(uid, "deploy_app", "git checkout -> npm install -> npm run build", CATEGORY_WORKFLOW_HISTORY)
    
    # Retrieve and verify all of them are formatted correctly
    retrieved = await store.retrieve_facts(uid)
    assert "User Preferences (Advanced)" in retrieved
    assert "editor_theme: dark" in retrieved
    assert "Project Context" in retrieved
    assert "active_workspace: Tamil_AI" in retrieved
    assert "Device Log" in retrieved
    assert "cpu_usage: 45%" in retrieved
    assert "Workflow History" in retrieved
    assert "deploy_app" in retrieved


@pytest.mark.asyncio
async def test_faiss_semantic_search(store):
    uid = "user_faiss"
    
    # Save distinctive facts
    await store.save_fact(uid, "favorite_food", "I love eating delicious Biryani.", CATEGORY_USER_FACT)
    await store.save_fact(uid, "hobby", "I enjoy painting landscapes during weekends.", CATEGORY_LONG_TERM)
    
    # Perform semantic searches
    res1 = await store.search_vector(uid, "What is your favorite dish to eat?")
    assert len(res1) >= 1
    assert "Biryani" in res1[0]["value"]
    
    res2 = await store.search_vector(uid, "Tell me about your artistic weekend hobbies")
    assert len(res2) >= 1
    assert "painting" in res2[0]["value"]


@pytest.mark.asyncio
async def test_api_semantic_search(app_client):
    # Save a fact via API
    await app_client.post(
        "/api/memory/api_faiss_user",
        json={"key": "server_setup", "value": "FastAPI is running on port 8000.", "category": "project_context"},
    )
    
    # Query via semantic search API endpoint
    resp = await app_client.get("/api/memory/api_faiss_user/search?q=Which port does the web server run on?&semantic=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["semantic"] is True
    assert data["total"] >= 1
    assert "port 8000" in data["results"][0]["value"]
