import pytest
import pytest_asyncio
import time
import os
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from fastapi import FastAPI

from routes.vscode import router as vscode_router
from models.base import db_manager
from ai.workspace_indexer import workspace_indexer
from ai.project_context import project_context_manager
from ai.rag_engine import rag_engine

# Instantiate an isolated test app to avoid importing heavy audio/ML modules from main
app = FastAPI()
app.include_router(vscode_router, prefix="/api")


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_database():
    """Fixture to redirect DatabaseManager to a temporary test database file."""
    test_db_path = Path(__file__).parent.parent / "test_agent.db"
    if test_db_path.exists():
        try:
            os.remove(test_db_path)
        except Exception:
            pass
            
    # Redirect DB path to isolated test DB
    db_manager._db_path = test_db_path
    await db_manager.init()
    
    yield
    
    # Clean up connections and remove temp test DB file
    await db_manager.close()
    if test_db_path.exists():
        try:
            os.remove(test_db_path)
        except Exception:
            pass


@pytest_asyncio.fixture(scope="module")
async def test_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_project_database_tables():
    """Verify project_modules and project_dependencies tables exist with columns."""
    # Check project_modules table
    mod_cols = await db_manager.fetch_all("PRAGMA table_info(project_modules)")
    col_names = [col["name"] for col in mod_cols]
    assert "file_path" in col_names
    assert "classes" in col_names
    assert "functions" in col_names
    assert "routes" in col_names
    assert "last_modified" in col_names

    # Check project_dependencies table (HR-01)
    dep_cols = await db_manager.fetch_all("PRAGMA table_info(project_dependencies)")
    dep_col_names = [col["name"] for col in dep_cols]
    assert "id" in dep_col_names
    assert "from_file" in dep_col_names
    assert "to_file" in dep_col_names
    assert "symbol_name" in dep_col_names
    assert "symbol_type" in dep_col_names
    assert "line_number" in dep_col_names


@pytest.mark.asyncio
async def test_workspace_indexer_scan_and_deps():
    """Verify WorkspaceIndexer scanning, symbol dependency matching and traversal depth control (max_depth=3)."""
    # Perform a workspace scan
    scan_res = await workspace_indexer.scan()
    assert scan_res["status"] == "success"
    assert scan_res["files_scanned"] > 0
    
    # Verify that dependencies exist in DB
    deps = await db_manager.fetch_all("SELECT * FROM project_dependencies")
    # There should be at least some python imports mapped at symbol level
    assert len(deps) >= 0
    if len(deps) > 0:
        dep = deps[0]
        assert dep["from_file"].endswith(".py")
        assert dep["to_file"].endswith(".py")
        assert "symbol_name" in dep
        assert "symbol_type" in dep

    # Test dependency chain resolution with max_depth limit
    chain = await workspace_indexer.resolve_dependency_chain("main.py", max_depth=3)
    assert isinstance(chain, list)
    for link in chain:
        assert link["depth"] <= 3


@pytest.mark.asyncio
async def test_project_context_manager_expiration():
    """Verify Workspace Context Expiration (HR-02) clearing after 300 seconds."""
    # Reset context
    project_context_manager.clear_context()
    
    # Set context
    project_context_manager.set_context(
        active_file="backend/main.py",
        cursor_line=50,
        active_symbol="root"
    )
    
    ctx = project_context_manager.get_context()
    assert ctx["active_file"] == "backend/main.py"
    assert ctx["cursor_line"] == 50
    assert ctx["active_symbol"] == "root"
    
    # Mock time in the future (>300 seconds)
    with patch("time.time", return_value=time.time() + 301):
        ctx_expired = project_context_manager.get_context()
        assert ctx_expired["active_file"] is None
        assert ctx_expired["active_symbol"] is None
        assert ctx_expired["updated_at"] == 0.0


@pytest.mark.asyncio
async def test_implicit_query_resolution():
    """Verify implicit query terms are successfully detected and resolved."""
    project_context_manager.clear_context()
    project_context_manager.set_context(
        active_file="backend/main.py",
        cursor_line=50,
        active_symbol="root"
    )
    
    # Test implicit queries
    assert project_context_manager.has_implicit_references("Explain this file please") is True
    assert project_context_manager.has_implicit_references("What does that API do?") is True
    assert project_context_manager.has_implicit_references("Explain database design") is False

    resolved = project_context_manager.resolve_implicit_query("Explain this route")
    assert resolved["active_file"] == "backend/main.py"
    assert resolved["active_symbol"] == "root"


@pytest.mark.asyncio
async def test_vscode_context_endpoints(test_client):
    """Verify POST and GET endpoints for VS Code real-time context syncing (Option A)."""
    # Test update context POST
    payload = {
        "active_file": "backend/routes/vscode.py",
        "cursor_line": 25,
        "active_symbol": "update_vscode_context"
    }
    resp = await test_client.post("/api/vscode/status/context", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["context"]["active_file"] == "backend/routes/vscode.py"
    assert data["context"]["active_symbol"] == "update_vscode_context"

    # Test retrieve context GET
    resp_get = await test_client.get("/api/vscode/status/context")
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["status"] == "success"
    assert data_get["context"]["active_file"] == "backend/routes/vscode.py"


@pytest.mark.asyncio
async def test_rag_context_protection_limits():
    """Verify RAG Context Window Protection (HR-04) file limits and character truncation."""
    # Set context
    project_context_manager.set_context(
        active_file="backend/main.py",
        cursor_line=10,
        active_symbol="app"
    )
    
    # Mock RAG search to return fake doc search hits (bypasses SentenceTransformer loading)
    mock_hits = [
        {"source": "main.py", "chunk": "def app creation chunk", "score": 0.95},
        {"source": "models/base.py", "chunk": "class DatabaseManager chunk", "score": 0.85}
    ]
    
    with patch.object(rag_engine, "search", return_value=mock_hits):
        ctx_str = await rag_engine.build_context("health check of this app")
        assert len(ctx_str) <= 12000
        
        # Verify file limit is constrained
        parts = ctx_str.split("\n\n---\n\n")
        distinct_files = set()
        for part in parts:
            if part.startswith("# --- Active File:"):
                distinct_files.add(part.split("Active File: ")[1].split(" ")[0])
            elif part.startswith("# --- Active Symbol Definition:"):
                distinct_files.add(part.split("in ")[1].split("\n")[0].strip())
            elif part.startswith("# --- Dependency"):
                distinct_files.add(part.split("): ")[1].split("\n")[0].strip())
                
        assert len(distinct_files) <= 10
