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
async def test_list_plugins(app_client):
    resp = await app_client.get("/api/v1/admin/plugins")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    calc_plugin = next((p for p in data if p["name"] == "Calculator"), None)
    assert calc_plugin is not None
    assert calc_plugin["enabled"] is True


@pytest.mark.anyio
async def test_toggle_plugin(app_client):
    # Toggle off
    resp = await app_client.post("/api/v1/admin/plugins/Calculator/toggle", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # Verify disabled in list
    resp = await app_client.get("/api/v1/admin/plugins")
    calc_plugin = next((p for p in resp.json() if p["name"] == "Calculator"), None)
    assert calc_plugin["enabled"] is False

    # Toggle back on
    resp = await app_client.post("/api/v1/admin/plugins/Calculator/toggle", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


@pytest.mark.anyio
async def test_upload_invalid_plugin(app_client):
    # 1. Non-py extension
    resp = await app_client.post(
        "/api/v1/admin/plugins/upload",
        files={"file": ("invalid_ext.txt", b"print('hello')")}
    )
    assert resp.status_code == 400
    assert "Only .py files" in resp.json()["detail"]

    # 2. Syntax error
    resp = await app_client.post(
        "/api/v1/admin/plugins/upload",
        files={"file": ("syntax_error.py", b"def invalid_syntax(:")}
    )
    assert resp.status_code == 400
    assert "syntax error" in resp.json()["detail"].lower()

    # 3. Missing execute function
    resp = await app_client.post(
        "/api/v1/admin/plugins/upload",
        files={"file": ("missing_exec.py", b"PLUGIN_NAME = 'MissingExec'\n# no execute function")}
    )
    assert resp.status_code == 400
    assert "must define async def execute" in resp.json()["detail"]


@pytest.mark.anyio
async def test_upload_and_delete_valid_plugin(app_client):
    plugin_code = b"""
PLUGIN_NAME = "TestPlugin"
PLUGIN_INTENTS = ["test_intent"]
PLUGIN_DESCRIPTION = "A dynamic testing plugin"

async def execute(message, **kwargs):
    return f"Executed with message: {message}"
"""
    # Upload
    resp = await app_client.post(
        "/api/v1/admin/plugins/upload",
        files={"file": ("test_plugin.py", plugin_code)}
    )
    assert resp.status_code == 200
    assert "uploaded and registered successfully" in resp.json()["message"]

    # Check listed
    resp = await app_client.get("/api/v1/admin/plugins")
    test_plugin = next((p for p in resp.json() if p["name"] == "TestPlugin"), None)
    assert test_plugin is not None
    assert "test_intent" in test_plugin["intents"]
    assert test_plugin["source"] == "plugin:test_plugin.py"

    # Check deletion
    resp = await app_client.delete("/api/v1/admin/plugins/TestPlugin")
    assert resp.status_code == 200
    assert "uninstalled and deleted successfully" in resp.json()["message"]

    # Check no longer listed
    resp = await app_client.get("/api/v1/admin/plugins")
    test_plugin = next((p for p in resp.json() if p["name"] == "TestPlugin"), None)
    assert test_plugin is None
