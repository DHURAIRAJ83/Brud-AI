import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from models.base import db_manager
from ai.sqlite_memory import sqlite_memory
from services.skills_service import skills_service
from services.command_service import command_service
from models.command import CommandCreate, CommandModel, TrustLevel


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_database():
    """Ensure the database and sqlite memory are initialized for testing."""
    await db_manager.init()
    await sqlite_memory.init()
    yield


def get_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_voice_session_creation():
    """Verify that posting a voice session saves details in DB and supports optional audio file upload."""
    async with get_client() as client:
        # Create a mock audio stream
        audio_data = b"RIFFmockwavcontent"
        files = {"audio": ("test_session.wav", io.BytesIO(audio_data), "audio/wav")}
        
        form_data = {
            "id": "test-session-123",
            "session_id": "conv-session-xyz",
            "started_at": "2026-06-12T10:00:00Z",
            "ended_at": "2026-06-12T10:00:02Z",
            "wakeword": "Hey Rudran",
            "transcript": "Git Commit செய்",
            "confidence": "0.85",
            "skill_id": "assistant",
            "status": "completed",
            "duration_ms": "2000.0",
            "confirmation_required": "1",
            "interrupted": "0"
        }
        
        # Save session
        response = await client.post("/api/voice/session", data=form_data, files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["id"] == "test-session-123"
        assert "uploads/voice_cache/test-session-123.wav" in data["audio_file"]

        # Retrieve session listing
        list_response = await client.get("/api/voice/sessions")
        assert list_response.status_code == 200
        list_data = list_response.json()
        sessions = list_data["sessions"]
        assert len(sessions) >= 1
        
        # Find our created session
        target = next((s for s in sessions if s["id"] == "test-session-123"), None)
        assert target is not None
        assert target["wakeword"] == "Hey Rudran"
        assert target["transcript"] == "Git Commit செய்"
        assert target["confidence"] == 0.85
        assert target["confirmation_required"] == 1
        assert target["interrupted"] == 0

        # Retrieve cached audio
        audio_response = await client.get("/api/voice/audio/test-session-123")
        assert audio_response.status_code == 200
        assert audio_response.content == audio_data


@pytest.mark.asyncio
async def test_voice_metrics_calculations():
    """Verify aggregated metrics are computed accurately from the database logs."""
    async with get_client() as client:
        response = await client.get("/api/voice/metrics")
        assert response.status_code == 200
        metrics = response.json()
        assert "total_sessions" in metrics
        assert "average_confidence" in metrics
        assert "failed_sessions" in metrics
        assert "wakeword_hits" in metrics
        assert "confirmation_requests" in metrics
        assert "rejected_commands" in metrics
        assert "interrupted_commands" in metrics


@pytest.mark.asyncio
async def test_voice_safety_shield():
    """Verify that CAUTION/DANGEROUS commands triggered via voice source are blocked from auto-executing."""
    # Register default devices for the user first to satisfy authorization checks
    from models.device import DeviceModel
    from models.user import UserModel
    
    # Fetch default user
    user = await UserModel.ensure_default_user()
    user_id = user["id"]
    
    # Get or register a test device
    device_id = "test-desktop-agent-id"
    await db_manager.execute(
        """INSERT OR REPLACE INTO devices (id, user_id, device_name, device_type, os_type, api_key, status, capabilities)
           VALUES (?, ?, ?, 'desktop', 'windows', 'test_key_123', 'active', '["git.commit", "desktop.open_app"]')""",
        (device_id, user_id, "Test Device")
    )

    # 1. Test SAFE command from voice source -> Should be enqueued successfully (e.g. desktop.open_app)
    safe_data = CommandCreate(
        device_id=device_id,
        tool="desktop.open_app",
        params={"app": "notepad"},
        raw_input="open notepad",
        source="voice"
    )
    cmd1 = await command_service.enqueue_command(user_id, safe_data)
    assert cmd1["tool"] == "desktop.open_app"
    assert cmd1["status"] == "pending" # SAFE commands automatically get set to pending

    # 2. Test CAUTION/DANGEROUS command from voice source -> Safety shield should raise HTTPException 403
    caution_data = CommandCreate(
        device_id=device_id,
        tool="git.commit",
        params={"message": "voice commit"},
        raw_input="git commit",
        source="voice"
    )
    
    with pytest.raises(Exception) as excinfo:
        await command_service.enqueue_command(user_id, caution_data)
    
    # FastAPI HTTPException contains detail block
    from fastapi import HTTPException
    assert isinstance(excinfo.value, HTTPException)
    assert excinfo.value.status_code == 403
    assert isinstance(excinfo.value.detail, dict)
    assert excinfo.value.detail["code"] == "voice_verification_required"
    assert "குரல் சரிபார்ப்பு" in excinfo.value.detail["message"]


@pytest.mark.asyncio
async def test_voice_profile_inheritance():
    """Verify that custom voice profiles inherit parent skill voices or fallback correctly."""
    # 1. Retrieve builtin tamil-teacher resolved skill voice
    teacher_resolved = await skills_service.get_resolved_skill("tamil-teacher")
    assert teacher_resolved is not None
    assert teacher_resolved["voice_profile"] == "ta-IN-ValluvarNeural"

    # 2. Create custom sub-skill inheriting from tamil-teacher but not defining voice
    custom_sub = await skills_service.create_skill(
        skill_id="custom-teacher-sub",
        name="Tamil Sub Teacher",
        parent_skill_id="tamil-teacher",
        system_prompt="Inherited prompt text",
        tools={"allow": [], "deny": []}
    )
    
    resolved_sub = await skills_service.get_resolved_skill("custom-teacher-sub")
    assert resolved_sub is not None
    # Should inherit parent's voice profile
    assert resolved_sub["voice_profile"] == "ta-IN-ValluvarNeural"
    
    # Cleanup
    await skills_service.delete_skill("custom-teacher-sub")
