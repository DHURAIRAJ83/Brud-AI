import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from main import app
from models.base import db_manager
from models.command import CommandCreate
from ai.sqlite_memory import sqlite_memory
from services.skills_service import skills_service
from services.command_service import command_service

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_database():
    """Ensure the database and sqlite memory are initialized for testing."""
    await db_manager.init()
    await sqlite_memory.init()
    yield

@pytest_asyncio.fixture(scope="module")
async def test_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_builtin_skills_seeding():
    """Verify that all 8 seed skills are pre-populated on startup."""
    skills = await skills_service.get_all_skills()
    assert len(skills) >= 8
    
    slugs = [s["id"] for s in skills]
    expected = [
        "assistant", "tamil-teacher", "researcher", "python-developer",
        "fastapi-expert", "devops-engineer", "ai-engineer", "textile-expert"
    ]
    for slug in expected:
        assert slug in slugs

@pytest.mark.asyncio
async def test_skill_inheritance_resolution():
    """Verify recursive parent property merging for fastapi-expert."""
    resolved = await skills_service.get_resolved_skill("fastapi-expert")
    assert resolved is not None
    assert resolved["model"] == "qwen2.5-coder"
    assert resolved["parent_skill_id"] == "python-developer"
    
    # Prompt contains parent prompt + child prompt
    assert "expert Python Developer" in resolved["system_prompt"]
    assert "FastAPI Expert" in resolved["system_prompt"]
    
    # Merged tools
    assert "coding.*" in resolved["tools"]["allow"]
    assert "git.*" in resolved["tools"]["allow"]

@pytest.mark.asyncio
async def test_skill_version_history():
    """Verify creating a custom skill increments version logs."""
    skill_id = "test-version-skill"
    
    try:
        # 1. Create version 1
        skill1 = await skills_service.create_skill(
            skill_id=skill_id,
            name="Test Version V1",
            system_prompt="Prompt V1",
            model="default",
            tools={"allow": ["browser.*"], "deny": []}
        )
        assert skill1["name"] == "Test Version V1"
        
        # Check database versions table count
        v1_row = await db_manager.fetch_one(
            "SELECT COUNT(*) as count FROM skill_versions WHERE skill_id = ?",
            (skill_id,)
        )
        assert v1_row["count"] == 1
        
        # Check details
        details = await db_manager.fetch_one(
            "SELECT version, system_prompt FROM skill_versions WHERE skill_id = ? ORDER BY version DESC",
            (skill_id,)
        )
        assert details["version"] == 1
        assert details["system_prompt"] == "Prompt V1"

        # 2. Update to version 2
        skill2 = await skills_service.create_skill(
            skill_id=skill_id,
            name="Test Version V2",
            system_prompt="Prompt V2",
            model="llama3",
            tools={"allow": ["browser.*"], "deny": []}
        )
        assert skill2["name"] == "Test Version V2"

        v2_row = await db_manager.fetch_one(
            "SELECT COUNT(*) as count FROM skill_versions WHERE skill_id = ?",
            (skill_id,)
        )
        assert v2_row["count"] == 2
        
        details2 = await db_manager.fetch_one(
            "SELECT version, system_prompt FROM skill_versions WHERE skill_id = ? ORDER BY version DESC",
            (skill_id,)
        )
        assert details2["version"] == 2
        assert details2["system_prompt"] == "Prompt V2"
        
    finally:
        # Clean up
        await db_manager.execute("DELETE FROM skill_versions WHERE skill_id = ?", (skill_id,))
        await db_manager.execute("DELETE FROM skills WHERE id = ?", (skill_id,))

@pytest.mark.asyncio
async def test_tool_permissions_matching():
    """Verify tool allowance matches wildcards and deny overrides."""
    # DevOps allowed files.* and git.*, denied git.push
    assert await skills_service.is_tool_allowed("devops-engineer", "files.list") is True
    assert await skills_service.is_tool_allowed("devops-engineer", "git.commit") is True
    assert await skills_service.is_tool_allowed("devops-engineer", "git.push") is False
    assert await skills_service.is_tool_allowed("devops-engineer", "coding.write_code") is False

    # AI Engineer allowed coding.*, files.*, vscode.*, git.commit, denied git.push
    assert await skills_service.is_tool_allowed("ai-engineer", "coding.write_code") is True
    assert await skills_service.is_tool_allowed("ai-engineer", "git.commit") is True
    assert await skills_service.is_tool_allowed("ai-engineer", "git.push") is False
    assert await skills_service.is_tool_allowed("ai-engineer", "browser.search") is False

    # Textile expert denies coding.*, git.*, vscode.*
    assert await skills_service.is_tool_allowed("textile-expert", "coding.write_code") is False
    assert await skills_service.is_tool_allowed("textile-expert", "files.list") is True

@pytest.mark.asyncio
async def test_skills_rest_routes(test_client):
    """Verify GET, POST, DELETE HTTP endpoints for skills and activation."""
    session_id = "test-session-skills-route"
    
    try:
        # 1. List skills
        res_list = await test_client.get("/api/skills")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 8
        
        # 2. Get resolved skill
        res_get = await test_client.get("/api/skills/fastapi-expert")
        assert res_get.status_code == 200
        assert res_get.json()["model"] == "qwen2.5-coder"

        # 3. Activate skill
        res_act = await test_client.post("/api/skills/activate", json={
            "session_id": session_id,
            "skill_id": "fastapi-expert"
        })
        assert res_act.status_code == 200
        assert res_act.json()["active_skill_id"] == "fastapi-expert"
        
        # Verify active skill survives backend logic
        active = await sqlite_memory.get_active_skill(session_id)
        assert active == "fastapi-expert"

        # 4. Deactivate skill
        res_deact = await test_client.post("/api/skills/activate", json={
            "session_id": session_id,
            "skill_id": None
        })
        assert res_deact.status_code == 200
        assert res_deact.json()["active_skill_id"] is None
        
        active_none = await sqlite_memory.get_active_skill(session_id)
        assert active_none is None
        
    finally:
        await sqlite_memory.delete_session(session_id)

@pytest.mark.asyncio
async def test_skills_execution_blocking():
    """Verify command_service throws HTTPException when tool is blocked by active skill."""
    session_id = "test-session-blocking"
    
    try:
        # Activate tamil-teacher
        await sqlite_memory.set_active_skill(session_id, "tamil-teacher")
        
        # Attempt to queue git.commit (denied by tamil-teacher)
        cmd_data = CommandCreate(
            device_id="desktop001",
            tool="git.commit",
            params={"message": "commit from test"}
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await command_service.enqueue_command(
                user_id="admin-user-123",
                data=cmd_data,
                session_id=session_id
            )
            
        assert exc_info.value.status_code == 403
        assert "blocked under active skill" in exc_info.value.detail
        
    finally:
        await sqlite_memory.delete_session(session_id)
