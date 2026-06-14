"""
Voice Sessions Router — audit logs, audio cache, and analytics metrics
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Depends
from fastapi.responses import FileResponse
import sys
from services.auth_service import require_user, require_admin

from models.base import db_manager
from config import get_settings

# Dynamically link the agent folder to import speaker verifier code
agent_path = str(Path(__file__).parent.parent.parent / "agent")
if agent_path not in sys.path:
    sys.path.append(agent_path)

from voice.speaker_verifier import enrollment_calibration, extract_mfcc_features
from security.voice_security import sign_embedding, verify_signature, get_voice_secret, generate_audio_hash
from models.voice_profile import VoiceProfileModel, VoiceAuthLogModel, VoiceLockoutModel, VoiceReplayModel, VoiceChallengeModel, VoiceAuthSessionModel

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# Prepare audio cache directory
CACHE_DIR = Path(settings.upload_dir) / "voice_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/session", summary="Log a voice session and cache its audio")
async def save_voice_session(
    id: str = Form(...),
    session_id: Optional[str] = Form(None),
    started_at: str = Form(...),
    ended_at: Optional[str] = Form(None),
    wakeword: Optional[str] = Form(None),
    transcript: Optional[str] = Form(None),
    confidence: Optional[float] = Form(None),
    skill_id: Optional[str] = Form(None),
    status: str = Form("completed"),
    duration_ms: Optional[float] = Form(0.0),
    confirmation_required: Optional[int] = Form(0),
    interrupted: Optional[int] = Form(0),
    audio: Optional[UploadFile] = File(None),
    current_user: dict = Depends(require_user)
):
    """
    Log voice sessions (transcription, latency, confidence, skill, etc.)
    and save raw WAV audio for replay/debugging.
    """
    try:
        audio_path = None
        if audio:
            # Save audio to local cache directory named by session ID
            safe_name = f"{id}.wav"
            dest_path = CACHE_DIR / safe_name
            
            # Read and save file
            content = await audio.read()
            dest_path.write_bytes(content)
            audio_path = f"uploads/voice_cache/{safe_name}"
            logger.info("Cached voice session audio at %s (%d bytes)", audio_path, len(content))

        # Check if record already exists
        existing = await db_manager.fetch_one("SELECT id FROM voice_sessions WHERE id = ?", (id,))
        
        if existing:
            # Update existing log
            await db_manager.execute(
                """UPDATE voice_sessions
                   SET session_id = ?, ended_at = ?, transcript = ?, confidence = ?, 
                       status = ?, duration_ms = ?, audio_file = COALESCE(?, audio_file),
                       confirmation_required = ?, interrupted = ?
                   WHERE id = ?""",
                (
                    session_id, ended_at, transcript, confidence,
                    status, duration_ms, audio_path, confirmation_required, interrupted, id
                )
            )
            logger.info("Updated voice session audit log: %s", id)
        else:
            # Insert new log
            await db_manager.execute(
                """INSERT INTO voice_sessions
                   (id, session_id, started_at, ended_at, wakeword, transcript, confidence, 
                    skill_id, status, duration_ms, audio_file, confirmation_required, interrupted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    id, session_id, started_at, ended_at, wakeword, transcript, confidence,
                    skill_id, status, duration_ms, audio_path, confirmation_required, interrupted
                )
            )
            logger.info("Saved new voice session audit log: %s", id)

        return {"success": True, "id": id, "audio_file": audio_path}
    except Exception as e:
        logger.error("Failed to save voice session: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/sessions", summary="Get all voice sessions audit logs")
async def list_voice_sessions(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(require_user)
):
    """List historical voice sessions sorted by date."""
    try:
        rows = await db_manager.fetch_all(
            """SELECT * FROM voice_sessions 
               ORDER BY created_at DESC 
               LIMIT ? OFFSET ?""",
            (limit, offset)
        )
        return {"sessions": rows}
    except Exception as e:
        logger.error("Failed to list voice sessions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/{session_id}", summary="Fetch voice audio by session ID")
async def get_voice_audio(
    session_id: str,
    current_user: dict = Depends(require_user)
):
    """Retrieve raw WAV file corresponding to the logged session ID."""
    # Enforce ownership rules: standard users can only access their own recordings
    if current_user.get("role") != "admin":
        owner = await db_manager.fetch_one(
            "SELECT user_id FROM voice_auth_sessions WHERE id = ?", (session_id,)
        )
        if not owner:
            owner = await db_manager.fetch_one(
                "SELECT user_id FROM voice_auth_logs WHERE session_id = ?", (session_id,)
            )
        if not owner:
            # Deny access if database ownership mapping cannot be resolved
            raise HTTPException(status_code=403, detail="Not authorized to access this audio recording.")
        if owner["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to access this audio recording.")

    safe_name = f"{session_id}.wav"
    target_path = CACHE_DIR / safe_name
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
        
    return FileResponse(path=str(target_path), media_type="audio/wav", filename=safe_name)


@router.get("/metrics", summary="Get voice dashboard analytics metrics")
async def get_voice_metrics(current_user: dict = Depends(require_user)):
    """Retrieve aggregated stats for voice usage monitoring."""
    try:
        # Total sessions
        total_res = await db_manager.fetch_one("SELECT COUNT(*) as cnt FROM voice_sessions")
        total = total_res["cnt"] if total_res else 0

        # Avg confidence
        avg_res = await db_manager.fetch_one("SELECT AVG(confidence) as avg_conf FROM voice_sessions WHERE confidence IS NOT NULL")
        avg_conf = round(avg_res["avg_conf"], 3) if avg_res and avg_res["avg_conf"] is not None else 0.0

        # Failed sessions (where status is 'error')
        failed_res = await db_manager.fetch_one("SELECT COUNT(*) as cnt FROM voice_sessions WHERE status = 'error'")
        failed = failed_res["cnt"] if failed_res else 0

        # Wakeword hits
        hits_res = await db_manager.fetch_one("SELECT COUNT(*) as cnt FROM voice_sessions WHERE wakeword IS NOT NULL")
        hits = hits_res["cnt"] if hits_res else 0

        # Confirmation requests
        confirm_res = await db_manager.fetch_one("SELECT COUNT(*) as cnt FROM voice_sessions WHERE confirmation_required = 1")
        confirm_requests = confirm_res["cnt"] if confirm_res else 0

        # Rejected commands (user said "No" / status is 'cancelled')
        rejected_res = await db_manager.fetch_one("SELECT COUNT(*) as cnt FROM voice_sessions WHERE status = 'cancelled'")
        rejected_commands = rejected_res["cnt"] if rejected_res else 0

        # Interrupted commands
        interrupted_res = await db_manager.fetch_one("SELECT COUNT(*) as cnt FROM voice_sessions WHERE interrupted = 1")
        interrupted_commands = interrupted_res["cnt"] if interrupted_res else 0

        return {
            "total_sessions": total,
            "average_confidence": avg_conf,
            "failed_sessions": failed,
            "wakeword_hits": hits,
            "confirmation_requests": confirm_requests,
            "rejected_commands": rejected_commands,
            "interrupted_commands": interrupted_commands
        }
    except Exception as e:
        logger.error("Failed to compute voice metrics: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enroll", summary="Enroll a user's voice profile template")
async def enroll_voice_profile(
    profile_name: str = Form(...),
    user_id: str = Form(...),
    audio_files: list[UploadFile] = File(...),
    current_user: dict = Depends(require_user)
):
    """Enrolls dynamic speaker voice templates (at least 3 sample WAVs)."""
    # Enforce role bounds (Standard users can self-enroll, ADMIN can enroll anyone)
    if current_user.get("role") == "guest" or current_user.get("username") == "guest":
        raise HTTPException(status_code=403, detail="Guest accounts are blocked from biometrics enrollment.")

    if current_user["id"] != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to enroll profiles for other users.")

    if len(audio_files) < 3:
        raise HTTPException(status_code=400, detail="Biometric enrollment requires at least 3 audio samples.")

    # Read WAV buffers
    samples = []
    for f in audio_files:
        content = await f.read()
        samples.append(content)

    # Perform MFCC calibration checks
    try:
        calib = enrollment_calibration(samples)
    except Exception as e:
        logger.error("Enrollment calibration failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Biometric calibration failed: {str(e)}")

    # Compute template signature using HMAC-SHA256
    signature = sign_embedding(calib["embedding_vector"], get_voice_secret())

    # Build DB record data
    profile_data = {
        "user_id": user_id,
        "profile_name": profile_name,
        "embedding_vector": calib["embedding_vector"],
        "embedding_signature": signature,
        "adaptive_threshold": calib["adaptive_threshold"],
        "confirm_threshold": calib["confirm_threshold"],
        "enrollment_mean": calib["enrollment_mean"],
        "enrollment_std": calib["enrollment_std"],
        "status": "active"
    }

    # Save to SQLite
    profile = await VoiceProfileModel.create_profile(profile_data)

    # Log USER update in audit logs
    from models.audit_log import AuditLogModel, AuditAction, AuditCategory
    await AuditLogModel.log(
        action=AuditAction.VOICE_PROFILE_CREATED,
        category=AuditCategory.USER,
        user_id=current_user["id"],
        details={"profile_id": profile["id"], "profile_name": profile_name, "user_id": user_id}
    )

    from routes.stream import system_events_manager
    await system_events_manager.broadcast({"event": "voice_profile_updated", "user_id": user_id})

    return {"success": True, "profile": profile}


@router.get("/profiles", summary="List active profiles for authenticated user")
async def get_active_user_profiles(current_user: dict = Depends(require_user)):
    """Retrieve all active voice profile templates registered to the caller."""
    profiles = await VoiceProfileModel.get_all_by_user(current_user["id"])
    active_profiles = [p for p in profiles if p["status"] == "active"]
    return {"profiles": active_profiles}


@router.delete("/profiles/{id}", summary="Delete a registered voice profile")
async def delete_voice_profile(id: str, current_user: dict = Depends(require_user)):
    """Removes a voice profile template from the database."""
    profile = await VoiceProfileModel.get_profile(id)
    if not profile:
        raise HTTPException(status_code=404, detail="Biometric profile not found.")

    # Access security boundary check
    if profile["user_id"] != current_user["id"] and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this voice profile.")

    await VoiceProfileModel.delete_profile(id)

    # Log revocation in system audits
    from models.audit_log import AuditLogModel, AuditAction, AuditCategory
    await AuditLogModel.log(
        action=AuditAction.VOICE_PROFILE_REVOKED,
        category=AuditCategory.USER,
        user_id=current_user["id"],
        details={"profile_id": id, "reason": "deleted_by_user"}
    )

    from routes.stream import system_events_manager
    await system_events_manager.broadcast({"event": "voice_profile_updated", "user_id": profile["user_id"]})

    return {"success": True}


@router.get("/security/metrics", summary="Get speaker verification analytics metrics")
async def get_security_metrics(current_user: dict = Depends(require_user)):
    """Fetch security dashboard aggregates for the caller."""
    return await VoiceAuthLogModel.get_metrics(current_user["id"])


@router.post("/verify-attempt", summary="Log a speaker verification event")
async def log_verification_attempt(
    session_id: Optional[str] = Form(None),
    user_id: str = Form(...),
    confidence_score: float = Form(...),
    verification_status: str = Form(...),
    challenge_required: int = Form(0),
    current_user: dict = Depends(require_user)
):
    """Logs verification attempts and alerts security administrators on failures."""
    log_data = {
        "session_id": session_id,
        "user_id": user_id,
        "confidence_score": confidence_score,
        "verification_status": verification_status,
        "challenge_required": challenge_required
    }
    
    log = await VoiceAuthLogModel.create_log(log_data)
    
    # Trigger security warnings on critical biometric anomalies
    if verification_status in ("rejected", "replay_detected", "locked_out"):
        from models.audit_log import AuditLogModel, AuditAction, AuditCategory
        await AuditLogModel.log(
            action=AuditAction.SECURITY_ALERT,
            category=AuditCategory.SECURITY,
            user_id=user_id,
            details={
                "session_id": session_id,
                "verification_status": verification_status,
                "confidence_score": confidence_score
            }
        )

    return {"success": True, "log": log}


@router.get("/lockout-status", summary="Check current user's lockout status")
async def get_lockout_status(current_user: dict = Depends(require_user)):
    status = await VoiceLockoutModel.get_status(current_user["id"])
    is_locked = False
    if status.get("locked_until"):
        now = datetime.now(timezone.utc).isoformat()
        if status["locked_until"] > now:
            is_locked = True
    return {"locked": is_locked, "locked_until": status.get("locked_until")}


@router.post("/replay-check-and-store", summary="Atomic check and store of audio hash")
async def replay_check_and_store(
    audio_hash: str = Form(...),
    session_id: str = Form(...),
    current_user: dict = Depends(require_user)
):
    import sqlite3
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db_manager.execute(
            "INSERT INTO voice_replay_cache (id, audio_hash, created_at) VALUES (?, ?, ?)",
            (session_id, audio_hash, now)
        )
        return {"duplicate": False}
    except Exception as e:
        err_str = str(e)
        if "UNIQUE constraint failed" in err_str:
            session = await VoiceAuthSessionModel.get_session(session_id)
            details = {
                "auth_session_id": session_id,
                "user_id": current_user["id"],
                "audio_hash": audio_hash
            }
            if session:
                details.update({
                    "device_id": session.get("device_id"),
                    "command_scope": session.get("command_scope"),
                    "verification_source": session.get("verification_source")
                })
            from models.audit_log import AuditLogModel, AuditAction, AuditCategory
            await AuditLogModel.log(
                action=AuditAction.VOICE_REPLAY_BLOCKED,
                category=AuditCategory.SECURITY,
                user_id=current_user["id"],
                details=details
            )
            return {"duplicate": True}
        else:
            logger.error("Failed to run replay attack check: %s", e)
            raise HTTPException(status_code=500, detail=str(e))



@router.post("/auth-session", summary="Create a new voice auth session")
async def create_auth_session(
    device_id: str = Form(...),
    command_scope: str = Form(...),
    verification_source: str = Form("mfcc_fallback"),
    current_user: dict = Depends(require_user)
):
    session = await VoiceAuthSessionModel.create_session(
        user_id=current_user["id"],
        device_id=device_id,
        command_scope=command_scope,
        verification_source=verification_source
    )
    return {"success": True, "auth_session": session}


@router.post("/auth-session/verify-speaker", summary="Log and verify speaker credentials")
async def verify_speaker_session(
    auth_session_id: str = Form(...),
    confidence_score: float = Form(...),
    verification_status: str = Form(...),
    current_user: dict = Depends(require_user)
):
    session = await VoiceAuthSessionModel.get_session(auth_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Auth session not found or expired.")
        
    if session["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Unauthorized session access.")

    # Check if locked out
    lockout_status = await VoiceLockoutModel.get_status(current_user["id"])
    now_str = datetime.now(timezone.utc).isoformat()
    if lockout_status.get("locked_until") and lockout_status["locked_until"] > now_str:
        await VoiceAuthSessionModel.update_verification(auth_session_id, "failed")
        raise HTTPException(status_code=403, detail="குரல் அணுகல் தற்காலிகமாக முடக்கப்பட்டுள்ளது")

    # Update session status
    if verification_status == "authorized":
        await VoiceAuthSessionModel.update_verification(auth_session_id, "passed")
        await VoiceLockoutModel.clear_failures(current_user["id"])
        
        from models.audit_log import AuditLogModel, AuditAction, AuditCategory
        await AuditLogModel.log(
            action=AuditAction.VOICE_AUTH_SUCCESS,
            category=AuditCategory.SECURITY,
            user_id=current_user["id"],
            details={
                "auth_session_id": auth_session_id,
                "user_id": current_user["id"],
                "device_id": session["device_id"],
                "command_scope": session["command_scope"],
                "verification_source": session.get("verification_source"),
                "confidence": confidence_score
            }
        )
    elif verification_status == "confirm":
        await VoiceAuthSessionModel.update_verification(auth_session_id, "passed")
    else:
        await VoiceAuthSessionModel.update_verification(auth_session_id, "failed")
        lockout = await VoiceLockoutModel.increment_failure(current_user["id"])
        
        from models.audit_log import AuditLogModel, AuditAction, AuditCategory
        await AuditLogModel.log(
            action=AuditAction.VOICE_AUTH_FAILURE,
            category=AuditCategory.SECURITY,
            user_id=current_user["id"],
            details={
                "auth_session_id": auth_session_id,
                "user_id": current_user["id"],
                "device_id": session["device_id"],
                "command_scope": session["command_scope"],
                "verification_source": session.get("verification_source"),
                "confidence": confidence_score
            }
        )
        
        if lockout["failure_count"] >= 5:
            await AuditLogModel.log(
                action=AuditAction.VOICE_LOCKOUT_TRIGGERED,
                category=AuditCategory.SECURITY,
                user_id=current_user["id"],
                details={
                    "auth_session_id": auth_session_id,
                    "user_id": current_user["id"],
                    "device_id": session["device_id"],
                    "command_scope": session["command_scope"],
                    "verification_source": session.get("verification_source"),
                    "failure_count": lockout["failure_count"]
                }
            )
            await VoiceAuthLogModel.create_log({
                "session_id": auth_session_id,
                "user_id": current_user["id"],
                "confidence_score": confidence_score,
                "verification_status": "locked_out",
                "challenge_required": 0
            })
            raise HTTPException(status_code=403, detail="குரல் அணுகல் தற்காலிகமாக முடக்கப்பட்டுள்ளது")

    await VoiceAuthLogModel.create_log({
        "session_id": auth_session_id,
        "user_id": current_user["id"],
        "confidence_score": confidence_score,
        "verification_status": "authorized" if verification_status in ("authorized", "confirm") else "rejected",
        "challenge_required": 1 if session["command_scope"] != "chat" else 0
    })
    
    return {"success": True}


@router.post("/auth-session/challenge", summary="Generate a challenge for voice auth session")
async def create_session_challenge(
    auth_session_id: str = Form(...),
    digits: str = Form(...),
    current_user: dict = Depends(require_user)
):
    session = await VoiceAuthSessionModel.get_session(auth_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Auth session not found or expired.")
    if session["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Unauthorized session access.")
        
    challenge = await VoiceChallengeModel.create_challenge(current_user["id"], digits)
    return {"success": True, "challenge": challenge}


@router.post("/auth-session/verify-challenge", summary="Verify challenge digits for session")
async def verify_session_challenge(
    auth_session_id: str = Form(...),
    challenge_id: str = Form(...),
    digits: str = Form(...),
    current_user: dict = Depends(require_user)
):
    session = await VoiceAuthSessionModel.get_session(auth_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Auth session not found or expired.")
    if session["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Unauthorized session access.")

    is_valid = await VoiceChallengeModel.validate_challenge(challenge_id, digits)
    from models.audit_log import AuditLogModel, AuditAction, AuditCategory
    if is_valid:
        await VoiceAuthSessionModel.update_challenge(auth_session_id, "passed")
        await AuditLogModel.log(
            action=AuditAction.VOICE_CHALLENGE_SUCCESS,
            category=AuditCategory.SECURITY,
            user_id=current_user["id"],
            details={
                "auth_session_id": auth_session_id,
                "challenge_id": challenge_id,
                "user_id": current_user["id"],
                "device_id": session["device_id"],
                "command_scope": session["command_scope"],
                "verification_source": session.get("verification_source")
            }
        )
        return {"success": True}
    else:
        row = await db_manager.fetch_one("SELECT 1 FROM voice_challenges WHERE id = ?", (challenge_id,))
        if not row:
            await VoiceAuthSessionModel.update_challenge(auth_session_id, "failed")
            
        await AuditLogModel.log(
            action=AuditAction.VOICE_CHALLENGE_FAILURE,
            category=AuditCategory.SECURITY,
            user_id=current_user["id"],
            details={
                "auth_session_id": auth_session_id,
                "challenge_id": challenge_id,
                "user_id": current_user["id"],
                "device_id": session["device_id"],
                "command_scope": session["command_scope"],
                "verification_source": session.get("verification_source")
            }
        )
        return {"success": False}


@router.get("/attempts", summary="Get all voice verification attempt logs")
async def list_voice_auth_attempts(limit: int = 50, offset: int = 0, current_user: dict = Depends(require_user)):
    """List historical speaker verification attempts."""
    try:
        rows = await db_manager.fetch_all(
            """SELECT val.*, u.username as username FROM voice_auth_logs val
               LEFT JOIN users u ON val.user_id = u.id
               ORDER BY val.created_at DESC 
               LIMIT ? OFFSET ?""",
            (limit, offset)
        )
        return {"attempts": rows}
    except Exception as e:
        logger.error("Failed to list verification attempts: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse-command-trust", summary="Parse command and get its trust level")
async def parse_command_trust(
    message: str = Form(...),
    current_user: dict = Depends(require_user)
):
    from ai.command_parser import command_parser
    from models.command import CommandModel
    
    action = await command_parser.parse(message)
    trust_level = CommandModel.TRUST_MAP.get(action.tool, "safe").value
    return {"tool": action.tool, "trust_level": trust_level}


@router.post("/admin/cleanup", summary="Manually trigger cleanup of expired voice session data")
async def trigger_voice_cleanup(current_user: dict = Depends(require_admin)):
    """Trigger manual cleanup of expired sessions, challenges, and replay cache."""
    try:
        session_count = await VoiceAuthSessionModel.cleanup_expired(retention_days=7)
        challenge_count = await VoiceChallengeModel.cleanup_expired()
        replay_count = await VoiceReplayModel.cleanup_expired(hours=1)
        
        # Log manual cleanup in system audits
        from models.audit_log import AuditLogModel, AuditAction, AuditCategory
        await AuditLogModel.log(
            action=AuditAction.ADMIN,
            category=AuditCategory.SYSTEM,
            user_id=current_user["id"],
            details={
                "action": "manual_voice_cleanup",
                "purged": {
                    "auth_sessions": session_count,
                    "challenges": challenge_count,
                    "replay_hashes": replay_count
                }
            }
        )
        
        return {
            "success": True,
            "purged": {
                "auth_sessions": session_count,
                "challenges": challenge_count,
                "replay_hashes": replay_count
            }
        }
    except Exception as e:
        logger.error("Failed to execute manual voice cleanup: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

