import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import sys
import os
import io
import json
import wave
import tempfile
import pathlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from models.base import db_manager
from models.audit_log import AuditLogModel, AuditAction
from services.auth_service import require_user, require_admin

# Dynamically link the agent folder to import speaker verifier code
agent_path = str(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../agent")))
if agent_path not in sys.path:
    sys.path.append(agent_path)

from voice.speaker_verifier import enrollment_calibration, extract_mfcc_features, verify_speaker
from security.voice_security import sign_embedding, verify_signature, get_voice_secret, generate_audio_hash
from models.voice_profile import VoiceProfileModel, VoiceAuthLogModel, VoiceLockoutModel, VoiceReplayModel, VoiceChallengeModel

# --- Mock Authentication Overrides ---
mock_user = {
    "id": "test_user_123",
    "username": "standard_user",
    "role": "standard"
}

async def override_require_user():
    return mock_user

async def override_require_admin():
    return {
        "id": "admin_user_456",
        "username": "admin_user",
        "role": "admin"
    }


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_database():
    """Initialize DB and mount auth overrides for testing routes."""
    # Use a fresh temp DB so we don't contend with the live agent.db held by main.py
    _tmp = tempfile.NamedTemporaryFile(suffix="_test_biometrics.db", delete=False)
    _tmp.close()
    tmp_db_path = pathlib.Path(_tmp.name)
    db_manager._db_path = tmp_db_path
    db_manager._db = None  # ensure re-init on fresh path

    await db_manager.init()
    
    # Insert test users into the database so foreign keys will succeed
    await db_manager.execute(
        "INSERT OR REPLACE INTO users (id, username, role) VALUES (?, ?, ?)",
        ("test_user_123", "standard_user", "standard")
    )
    await db_manager.execute(
        "INSERT OR REPLACE INTO users (id, username, role) VALUES (?, ?, ?)",
        ("admin_user_456", "admin_user", "admin")
    )
    await db_manager.execute(
        "INSERT OR REPLACE INTO users (id, username, role) VALUES (?, ?, ?)",
        ("other_user_id", "other_user_id", "standard")
    )
    
    # Apply FastAPI dependency overrides
    app.dependency_overrides[require_user] = override_require_user
    app.dependency_overrides[require_admin] = override_require_admin
    
    yield
    
    # Clean up test users
    await db_manager.execute(
        "DELETE FROM users WHERE id IN (?, ?, ?)",
        ("test_user_123", "admin_user_456", "other_user_id")
    )
    
    # Teardown overrides
    app.dependency_overrides.clear()
    await db_manager.close()
    # Remove temp DB file
    try:
        tmp_db_path.unlink(missing_ok=True)
        pathlib.Path(str(tmp_db_path) + "-shm").unlink(missing_ok=True)
        pathlib.Path(str(tmp_db_path) + "-wal").unlink(missing_ok=True)
    except Exception:
        pass



def get_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def create_dummy_wav(duration_sec=0.5, amplitude=1000) -> bytes:
    """Helper to generate a valid in-memory dummy WAV buffer for testing MFCC parsing."""
    out = io.BytesIO()
    with wave.open(out, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # Create a simple sine wave
        num_samples = int(16000 * duration_sec)
        samples = []
        for i in range(num_samples):
            val = int(amplitude * math.sin(2 * math.pi * 440 * i / 16000))
            samples.append(val)
        import struct
        data = struct.pack('<' + 'h' * num_samples, *samples)
        wf.writeframes(data)
    return out.getvalue()

import math


# --- TESTS ---

@pytest.mark.asyncio
async def test_signature_validation_and_tampering():
    """Verify that templates are HMAC signed and tampered templates are auto-revoked."""
    user_id = "test_user_123"
    
    # 1. Create a simulated profile
    embedding = [0.1] * 128
    sig = sign_embedding(embedding, get_voice_secret())
    
    profile_data = {
        "user_id": user_id,
        "profile_name": "dhura_voice",
        "embedding_vector": embedding,
        "embedding_signature": sig,
        "adaptive_threshold": 0.82,
        "confirm_threshold": 0.72,
        "enrollment_mean": 0.85,
        "enrollment_std": 0.01,
        "status": "active"
    }
    
    profile = await VoiceProfileModel.create_profile(profile_data)
    assert profile["id"] is not None
    assert profile["embedding_signature"] == sig
    
    # 2. Retrieve profile -> Should succeed without error
    retrieved = await VoiceProfileModel.get_profile(profile["id"])
    assert retrieved is not None
    assert retrieved["status"] == "active"
    
    # 3. Manually tamper with embedding vector inside DB
    tampered_embedding = [0.9] * 128
    await db_manager.execute(
        "UPDATE voice_profiles SET embedding_vector = ? WHERE id = ?",
        (json.dumps(tampered_embedding), profile["id"])
    )
    
    # 4. Attempt to retrieve tampered profile -> Should raise ValueError and set status to 'compromised'
    with pytest.raises(ValueError) as excinfo:
        await VoiceProfileModel.get_profile(profile["id"])
    
    assert "auto-revoked" in str(excinfo.value)
    
    # Verify DB status is updated to compromised
    compromised_row = await db_manager.fetch_one(
        "SELECT status FROM voice_profiles WHERE id = ?", (profile["id"],)
    )
    assert compromised_row["status"] == "compromised"
    
    # Verify security audit log exists
    audit_logs = await AuditLogModel.recent_security_events(limit=5)
    alert_log = next((log for log in audit_logs if log["details"].get("profile_id") == profile["id"]), None)
    assert alert_log is not None
    assert alert_log["action"] == AuditAction.SECURITY_ALERT.value
    assert alert_log["details"]["reason"] == "compromised_tampering"


@pytest.mark.asyncio
async def test_biometric_calibration_math():
    """Verify adaptive and confirm threshold calculations and L2 embedding pooling."""
    s1 = create_dummy_wav(0.5, 1000)
    s2 = create_dummy_wav(0.5, 1200)
    s3 = create_dummy_wav(0.5, 900)
    
    calib = enrollment_calibration([s1, s2, s3])
    
    # Verify output parameters
    assert "adaptive_threshold" in calib
    assert "confirm_threshold" in calib
    assert "embedding_vector" in calib
    
    # Enforce threshold constraints clamping [0.75, 0.88]
    assert 0.75 <= calib["adaptive_threshold"] <= 0.88
    assert 0.65 <= calib["confirm_threshold"] <= 0.78
    assert len(calib["embedding_vector"]) == 128
    
    # Check L2 normalization of returned vector
    norm = sum(x*x for x in calib["embedding_vector"]) ** 0.5
    assert pytest.approx(norm, abs=1e-4) == 1.0


@pytest.mark.asyncio
async def test_replay_hash_deduplication():
    """Verify audio hash calculation and database cache duplicate filters."""
    audio_data = b"RIFFsamplewavpayloadforhashchecking"
    h = generate_audio_hash(audio_data)
    assert len(h) == 64  # SHA-256 length
    
    session_id = "test-session-hash-111"
    
    # Validate not cached
    assert await VoiceReplayModel.hash_exists(h) is False
    
    # Store in cache
    stored = await VoiceReplayModel.store_hash(h, session_id)
    assert stored is True
    
    # Check deduplication
    assert await VoiceReplayModel.hash_exists(h) is True
    
    # Clear expired hashes
    deleted = await VoiceReplayModel.cleanup_expired(hours=0) # delete all immediately by setting age to 0
    assert deleted >= 1
    assert await VoiceReplayModel.hash_exists(h) is False


@pytest.mark.asyncio
async def test_api_security_enforcement():
    """Verify enrollment, list, and delete routes enforce JWT credentials, role rules, and guest blocks."""
    global mock_user
    
    async with get_client() as client:
        # Prepare valid 3 samples
        s1 = create_dummy_wav(0.5, 1000)
        s2 = create_dummy_wav(0.5, 1100)
        s3 = create_dummy_wav(0.5, 950)
        
        files = [
            ("audio_files", ("s1.wav", io.BytesIO(s1), "audio/wav")),
            ("audio_files", ("s2.wav", io.BytesIO(s2), "audio/wav")),
            ("audio_files", ("s3.wav", io.BytesIO(s3), "audio/wav")),
        ]
        
        form_data = {
            "profile_name": "test_verification_profile",
            "user_id": "test_user_123"
        }
        
        # 1. Standard enrollment (authorized)
        mock_user = {"id": "test_user_123", "username": "standard_user", "role": "standard"}
        response = await client.post("/api/voice/enroll", data=form_data, files=files)
        assert response.status_code == 200
        enroll_data = response.json()
        assert enroll_data["success"] is True
        profile_id = enroll_data["profile"]["id"]
        
        # 2. Guest user block check
        mock_user = {"id": "guest_user", "username": "guest", "role": "guest"}
        response_guest = await client.post("/api/voice/enroll", data=form_data, files=files)
        assert response_guest.status_code == 403
        assert "Guest" in response_guest.json()["detail"]
        
        # 3. Self-enroll check (trying to enroll standard user's profile with user_id="other_user")
        mock_user = {"id": "test_user_123", "username": "standard_user", "role": "standard"}
        form_other = {"profile_name": "other_profile", "user_id": "other_user_id"}
        # Reset file pointers for upload retry
        files_retry = [
            ("audio_files", ("s1.wav", io.BytesIO(s1), "audio/wav")),
            ("audio_files", ("s2.wav", io.BytesIO(s2), "audio/wav")),
            ("audio_files", ("s3.wav", io.BytesIO(s3), "audio/wav")),
        ]
        response_other = await client.post("/api/voice/enroll", data=form_other, files=files_retry)
        assert response_other.status_code == 403
        
        # 4. ADMIN override check
        mock_user = {"id": "admin_user_456", "username": "admin_user", "role": "admin"}
        # Reset file pointers for admin retry
        files_admin = [
            ("audio_files", ("s1.wav", io.BytesIO(s1), "audio/wav")),
            ("audio_files", ("s2.wav", io.BytesIO(s2), "audio/wav")),
            ("audio_files", ("s3.wav", io.BytesIO(s3), "audio/wav")),
        ]
        response_admin = await client.post("/api/voice/enroll", data=form_other, files=files_admin)
        assert response_admin.status_code == 200
        assert response_admin.json()["success"] is True
        admin_enrolled_id = response_admin.json()["profile"]["id"]
        
        # 5. List profiles (standard user gets standard user's profiles)
        mock_user = {"id": "test_user_123", "username": "standard_user", "role": "standard"}
        list_response = await client.get("/api/voice/profiles")
        assert list_response.status_code == 200
        profiles = list_response.json()["profiles"]
        assert len(profiles) >= 1
        assert profiles[0]["user_id"] == "test_user_123"
        
        # 6. Delete permissions block (standard user tries to delete admin-created template owned by 'other_user_id')
        mock_user = {"id": "test_user_123", "username": "standard_user", "role": "standard"}
        del_unauthorized = await client.delete(f"/api/voice/profiles/{admin_enrolled_id}")
        assert del_unauthorized.status_code == 403
        
        # 7. Delete profiles success (owner deletes standard profile)
        del_success = await client.delete(f"/api/voice/profiles/{profile_id}")
        assert del_success.status_code == 200
        assert del_success.json()["success"] is True
        
        # Clean up admin created profile
        await db_manager.execute("DELETE FROM voice_profiles WHERE id = ?", (admin_enrolled_id,))
        await db_manager.execute("DELETE FROM voice_profiles WHERE id = ?", (response_admin.json()["profile"]["id"],))
