import os
import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Ensure backend folder is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def app_client(tmp_path):
    db_file = tmp_path / "app_test.db"

    # Patch the singletons to avoid locking live DB
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


@pytest.mark.anyio
async def test_finetune_sessions(app_client):
    resp = await app_client.get("/api/v1/admin/finetune/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


@pytest.mark.anyio
async def test_finetune_curate(app_client):
    # Retrieve target to write dummy turn
    from ai.sqlite_memory import sqlite_memory
    session_id = "test_finetune_session_abc"
    await sqlite_memory.add_turn(session_id, "user", "வணக்கம், என் பெயர் அருண்.")
    await sqlite_memory.add_turn(session_id, "assistant", "வணக்கம் அருண்! நான் உங்களுக்கு எப்படி உதவ முடியும்?")

    # Curate as Alpaca dataset with censoring
    body = {
        "session_ids": [session_id],
        "format": "alpaca",
        "censor_words": ["அருண்"]
    }
    resp = await app_client.post("/api/v1/admin/finetune/curate", json=body)
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["format"] == "alpaca"
    assert data["item_count"] == 1
    
    dataset = data["dataset"]
    assert "[CENSORED]" in dataset[0]["instruction"]
    assert "[CENSORED]" in dataset[0]["output"]
    assert "உதவ" in dataset[0]["output"]

    # Clean up session
    await sqlite_memory.delete_session(session_id)
