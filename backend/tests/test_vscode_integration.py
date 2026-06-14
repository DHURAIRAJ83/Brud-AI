import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from main import app
from models.command import CommandModel, TrustLevel, CommandCreate
from services.command_service import command_service
from routes.vscode import vscode_manager
from ai.workspace_indexer import workspace_indexer
from models.base import db_manager
import tempfile
import pathlib


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_db():
    _tmp = tempfile.NamedTemporaryFile(suffix="_test_vscode.db", delete=False)
    _tmp.close()
    tmp_db_path = pathlib.Path(_tmp.name)
    db_manager._db_path = tmp_db_path
    db_manager._db = None
    await db_manager.init()
    yield
    await db_manager.close()
    try:
        tmp_db_path.unlink(missing_ok=True)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="module")
async def test_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_vscode_trust_mappings():
    """Verify that VS Code operations are classified as SAFE and Git operations are classified as CAUTION."""
    assert CommandModel.classify_trust("vscode.open_file") == TrustLevel.SAFE
    assert CommandModel.classify_trust("vscode.search_code") == TrustLevel.SAFE
    assert CommandModel.classify_trust("vscode.create_project") == TrustLevel.SAFE
    assert CommandModel.classify_trust("vscode.run_tests") == TrustLevel.SAFE
    
    assert CommandModel.classify_trust("git.commit") == TrustLevel.CAUTION
    assert CommandModel.classify_trust("git.push") == TrustLevel.DANGEROUS


@pytest.mark.asyncio
async def test_blocked_commands_prevention():
    """Verify that terminal.execute_anything and powershell.raw_command are strictly blocked."""
    cmd_data = CommandCreate(
        device_id="dev_123",
        tool="terminal.execute_anything",
        params={}
    )
    with pytest.raises(HTTPException) as exc_info:
        await command_service.enqueue_command("admin-user-123", cmd_data)
    assert exc_info.value.status_code == 403
    assert "blocked" in exc_info.value.detail.lower()

    cmd_data2 = CommandCreate(
        device_id="dev_123",
        tool="powershell.raw_command",
        params={}
    )
    with pytest.raises(HTTPException) as exc_info:
        await command_service.enqueue_command("admin-user-123", cmd_data2)
    assert exc_info.value.status_code == 403
    assert "blocked" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_vscode_status_endpoint(test_client):
    """Test that the status endpoint returns connected=False and lists empty sessions initially."""
    # Ensure manager is clear
    vscode_manager.active_connections.clear()
    
    resp = await test_client.get("/api/vscode/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert "sessions" in data
    assert len(data["sessions"]) == 0


@pytest.mark.asyncio
async def test_vscode_execute_endpoint_no_connection(test_client):
    """Test that execution command fails with a clear message when there are no connected extensions."""
    resp = await test_client.post("/api/vscode/execute", json={
        "command": "vscode.open_file",
        "params": {"file_path": "h:/AI_LLM/Tamil_AI/backend/main.py"}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert "No active VS Code extension connection" in data["message"]


@pytest.mark.asyncio
async def test_vscode_execute_endpoint_routing(test_client):
    """Test routing of a VS Code command to a simulated connected WebSocket."""
    mock_websocket = AsyncMock()
    mock_websocket.accept = AsyncMock()
    mock_websocket.send_text = AsyncMock()
    
    # Simulate connection
    session_id = "test-session-123"
    await vscode_manager.connect(session_id, mock_websocket)
    
    with patch.object(vscode_manager, "send_command", return_value={"status": "success", "file": "main.py"}):
        resp = await test_client.post("/api/vscode/execute", json={
            "command": "vscode.open_file",
            "params": {"file_path": "main.py"},
            "session_id": session_id
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["file"] == "main.py"
        
    vscode_manager.disconnect(session_id)


@pytest.mark.asyncio
async def test_workspace_indexer_logic():
    """Verify scanning and querying methods in the WorkspaceIndexer."""
    # Run scan
    res = await workspace_indexer.scan()
    assert res["status"] == "success"
    assert res["files_scanned"] >= 0
    
    # Query symbols
    results = await workspace_indexer.query("main")
    assert isinstance(results, list)
    
    # Query FastAPI app creation
    app_creation = workspace_indexer.find_app_creation()
    assert app_creation is None or isinstance(app_creation, dict)
    if isinstance(app_creation, dict):
        assert "file" in app_creation
        assert "line" in app_creation
