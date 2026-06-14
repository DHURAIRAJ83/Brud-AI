"""
Voice Profile & Biometrics Models
---------------------------------
Database access layers for voice templates, verification logs, challenges, lockouts, and replay cache.
"""

import json
import logging
import uuid
import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from models.base import db_manager
from models.audit_log import AuditLogModel, AuditAction, AuditCategory
from security.voice_security import verify_signature, get_voice_secret

logger = logging.getLogger(__name__)


class VerificationSource(str, Enum):
    ONNX_ECAPA = "onnx_ecapa"
    MFCC_FALLBACK = "mfcc_fallback"
    MANUAL_OVERRIDE = "manual_override"


class VoiceProfileModel:
    """Operations for secure voice biometrics templates."""

    @staticmethod
    async def create_profile(data: dict) -> dict:
        """Create a new signed voice profile template."""
        profile_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        await db_manager.execute(
            """INSERT INTO voice_profiles (
                id, user_id, profile_name, embedding_vector, embedding_signature,
                adaptive_threshold, confirm_threshold, enrollment_mean, enrollment_std,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id,
                data["user_id"],
                data["profile_name"],
                json.dumps(data["embedding_vector"]),
                data["embedding_signature"],
                data["adaptive_threshold"],
                data["confirm_threshold"],
                data["enrollment_mean"],
                data["enrollment_std"],
                data.get("status", "active"),
                now,
                now
            )
        )
        logger.info("Created voice profile %s for user %s", data["profile_name"], data["user_id"])
        return await VoiceProfileModel.get_profile(profile_id)

    @staticmethod
    async def get_profile(profile_id: str) -> Optional[dict]:
        """Fetch voice profile by ID and verify cryptographic signature integrity."""
        row = await db_manager.fetch_one(
            "SELECT * FROM voice_profiles WHERE id = ?", (profile_id,)
        )
        if not row:
            return None

        # Convert Row object to dictionary to allow key updates
        profile_dict = dict(row)
        vector_list = json.loads(profile_dict["embedding_vector"])

        # Cryptographic tamper verification check
        is_valid = verify_signature(
            vector_list,
            profile_dict["embedding_signature"],
            get_voice_secret()
        )

        if not is_valid:
            logger.critical("TAMPER DETECTED: Voice profile %s embedding signature mismatch!", profile_id)
            # Auto-revoke compromised template
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            await db_manager.execute(
                "UPDATE voice_profiles SET status = 'compromised', updated_at = ? WHERE id = ?",
                (now, profile_id)
            )
            # Log security alert event
            await AuditLogModel.log(
                action=AuditAction.SECURITY_ALERT,
                category=AuditCategory.SECURITY,
                user_id=profile_dict["user_id"],
                details={"profile_id": profile_id, "reason": "compromised_tampering"}
            )
            raise ValueError("Biometric template signature validation failed. Profile has been auto-revoked.")

        return profile_dict

    @staticmethod
    async def get_active_profile(user_id: str) -> Optional[dict]:
        """Fetch the latest active voice profile for a user and verify signature."""
        row = await db_manager.fetch_one(
            "SELECT * FROM voice_profiles WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        if not row:
            return None

        # Delegate validation to get_profile to ensure signature verification
        return await VoiceProfileModel.get_profile(row["id"])

    @staticmethod
    async def get_all_by_user(user_id: str) -> List[dict]:
        """Get list of all voice profiles for a user, verifying signatures."""
        rows = await db_manager.fetch_all(
            "SELECT id FROM voice_profiles WHERE user_id = ?", (user_id,)
        )
        profiles = []
        for r in rows:
            try:
                prof = await VoiceProfileModel.get_profile(r["id"])
                if prof:
                    profiles.append(prof)
            except ValueError:
                # Tampered templates are auto-revoked and skipped
                pass
        return profiles

    @staticmethod
    async def revoke_profile(profile_id: str, reason: str) -> bool:
        """Revoke user profile template."""
        profile = await db_manager.fetch_one(
            "SELECT id, user_id FROM voice_profiles WHERE id = ?", (profile_id,)
        )
        if not profile:
            return False

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await db_manager.execute(
            "UPDATE voice_profiles SET status = 'revoked', updated_at = ? WHERE id = ?",
            (now, profile_id)
        )

        await AuditLogModel.log(
            action=AuditAction.VOICE_PROFILE_REVOKED,
            category=AuditCategory.USER,
            user_id=profile["user_id"],
            details={"profile_id": profile_id, "reason": reason}
        )
        logger.info("Revoked voice profile %s. Reason: %s", profile_id, reason)
        return True

    @staticmethod
    async def delete_profile(profile_id: str) -> bool:
        """Hard delete voice profile."""
        await db_manager.execute(
            "DELETE FROM voice_profiles WHERE id = ?", (profile_id,)
        )
        logger.info("Deleted voice profile %s from DB", profile_id)
        return True


class VoiceAuthLogModel:
    """Operations for recording speaker verification attempts."""

    @staticmethod
    async def create_log(data: dict) -> dict:
        """Insert a verification attempt log."""
        log_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        await db_manager.execute(
            """INSERT INTO voice_auth_logs (
                id, session_id, user_id, confidence_score,
                verification_status, challenge_required, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                log_id,
                data.get("session_id"),
                data["user_id"],
                data["confidence_score"],
                data["verification_status"],
                data.get("challenge_required", 0),
                now
            )
        )
        return {
            "id": log_id,
            "user_id": data["user_id"],
            "verification_status": data["verification_status"],
            "created_at": now
        }

    @staticmethod
    async def get_metrics(user_id: str) -> dict:
        """Query aggregate speaker verification safety metrics."""
        total_res = await db_manager.fetch_one(
            "SELECT COUNT(*) as cnt FROM voice_auth_logs WHERE user_id = ?", (user_id,)
        )
        total = total_res["cnt"] if total_res else 0

        success_res = await db_manager.fetch_one(
            """SELECT COUNT(*) as cnt FROM voice_auth_logs 
               WHERE user_id = ? AND verification_status IN ('authorized', 'confirmed')""",
            (user_id,)
        )
        success = success_res["cnt"] if success_res else 0

        rejected_res = await db_manager.fetch_one(
            "SELECT COUNT(*) as cnt FROM voice_auth_logs WHERE user_id = ? AND verification_status = 'rejected'",
            (user_id,)
        )
        rejected = rejected_res["cnt"] if rejected_res else 0

        replay_res = await db_manager.fetch_one(
            "SELECT COUNT(*) as cnt FROM voice_auth_logs WHERE user_id = ? AND verification_status = 'replay_detected'",
            (user_id,)
        )
        replay_count = replay_res["cnt"] if replay_res else 0

        # Fetch lockout count
        lockout_res = await db_manager.fetch_one(
            "SELECT COUNT(*) as cnt FROM voice_auth_logs WHERE user_id = ? AND verification_status = 'locked_out'",
            (user_id,)
        )
        lockout_count = lockout_res["cnt"] if lockout_res else 0

        success_rate = round(success / total, 3) if total > 0 else 1.0
        failure_rate = round((rejected + replay_count + lockout_count) / total, 3) if total > 0 else 0.0

        # Get last verification time
        last_res = await db_manager.fetch_one(
            "SELECT created_at FROM voice_auth_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        last_time = last_res["created_at"] if last_res else None

        # Enrolled profiles count
        profiles_res = await db_manager.fetch_one(
            "SELECT COUNT(*) as cnt FROM voice_profiles WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        profiles_count = profiles_res["cnt"] if profiles_res else 0

        return {
            "enrolled_profiles_count": profiles_count,
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "failed_attempts": rejected + replay_count + lockout_count,
            "lockout_count": lockout_count,
            "replay_attack_count": replay_count,
            "last_verification_time": last_time
        }


class VoiceLockoutModel:
    """Operations for user rate-limiting lockout protections."""

    @staticmethod
    async def get_status(user_id: str) -> dict:
        """Get lockout data for a user."""
        row = await db_manager.fetch_one(
            "SELECT * FROM voice_lockouts WHERE user_id = ?", (user_id,)
        )
        if not row:
            return {"user_id": user_id, "failure_count": 0, "locked_until": None}
        return dict(row)

    @staticmethod
    async def increment_failure(user_id: str) -> dict:
        """Increment consecutive failures, trigger exponential lockouts if threshold exceeded."""
        status = await VoiceLockoutModel.get_status(user_id)
        new_count = status["failure_count"] + 1
        locked_until = None

        if new_count >= 5:
            # 5th attempt = 5m lock, 6-9th = 15m lock, 10+ = 60m lock
            now = datetime.datetime.now(datetime.timezone.utc)
            if new_count == 5:
                delta_min = 5
            elif new_count < 10:
                delta_min = 15
            else:
                delta_min = 60
            
            locked_until = (now + datetime.timedelta(minutes=delta_min)).isoformat()

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Update in SQLite using INSERT OR REPLACE
        await db_manager.execute(
            """INSERT OR REPLACE INTO voice_lockouts (id, user_id, failure_count, locked_until, created_at, updated_at)
               VALUES (
                   COALESCE((SELECT id FROM voice_lockouts WHERE user_id = ?), ?),
                   ?, ?, ?,
                   COALESCE((SELECT created_at FROM voice_lockouts WHERE user_id = ?), ?),
                   ?
               )""",
            (user_id, str(uuid.uuid4()), user_id, new_count, locked_until, user_id, now_str, now_str)
        )

        return {
            "user_id": user_id,
            "failure_count": new_count,
            "locked_until": locked_until
        }

    @staticmethod
    async def clear_failures(user_id: str) -> bool:
        """Reset failed counts back to zero."""
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await db_manager.execute(
            """INSERT OR REPLACE INTO voice_lockouts (id, user_id, failure_count, locked_until, created_at, updated_at)
               VALUES (
                   COALESCE((SELECT id FROM voice_lockouts WHERE user_id = ?), ?),
                   ?, 0, NULL,
                   COALESCE((SELECT created_at FROM voice_lockouts WHERE user_id = ?), ?),
                   ?
               )""",
            (user_id, str(uuid.uuid4()), user_id, user_id, now_str, now_str)
        )
        return True


class VoiceReplayModel:
    """Operations for sliding window deduplication cache."""

    @staticmethod
    async def hash_exists(audio_hash: str) -> bool:
        """Check if audio hash is already cached."""
        row = await db_manager.fetch_one(
            "SELECT 1 FROM voice_replay_cache WHERE audio_hash = ?", (audio_hash,)
        )
        return row is not None

    @staticmethod
    async def store_hash(audio_hash: str, session_id: str) -> bool:
        """Cache an audio hash."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            await db_manager.execute(
                "INSERT INTO voice_replay_cache (id, audio_hash, created_at) VALUES (?, ?, ?)",
                (session_id, audio_hash, now)
            )
            return True
        except Exception:
            return False

    @staticmethod
    async def cleanup_expired(hours: int = 1) -> int:
        """Delete hashes older than N hours."""
        # Calculate cut-off ISO string
        cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).isoformat()
        # Fetch rows to get deleted count
        rows = await db_manager.fetch_all(
            "SELECT id FROM voice_replay_cache WHERE created_at < ?", (cutoff,)
        )
        count = len(rows)
        if count > 0:
            await db_manager.execute(
                "DELETE FROM voice_replay_cache WHERE created_at < ?", (cutoff,)
            )
        return count


class VoiceChallengeModel:
    """Operations for challenge-response liveness check logs."""

    @staticmethod
    async def create_challenge(user_id: str, digits: str, expires_in_sec: int = 60) -> dict:
        """Write dynamic challenge sequence to table."""
        challenge_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = (now + datetime.timedelta(seconds=expires_in_sec)).isoformat()

        await db_manager.execute(
            """INSERT INTO voice_challenges (id, user_id, challenge_digits, attempt_count, expires_at, created_at)
               VALUES (?, ?, ?, 0, ?, ?)""",
            (challenge_id, user_id, digits, expires_at, now.isoformat())
        )
        return {
            "id": challenge_id,
            "user_id": user_id,
            "challenge_digits": digits,
            "expires_at": expires_at
        }

    @staticmethod
    async def validate_challenge(challenge_id: str, digits: str) -> bool:
        """Verify dynamic challenge details, enforcing max 3 attempts."""
        row = await db_manager.fetch_one(
            "SELECT * FROM voice_challenges WHERE id = ?", (challenge_id,)
        )
        if not row:
            return False

        # Expiration check
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if row["expires_at"] < now:
            return False

        # Increment attempts
        new_attempts = row["attempt_count"] + 1
        await db_manager.execute(
            "UPDATE voice_challenges SET attempt_count = ? WHERE id = ?",
            (new_attempts, challenge_id)
        )

        if new_attempts > 3:
            # Over threshold, delete challenge and fail
            await VoiceChallengeModel.delete_challenge(challenge_id)
            return False

        success = row["challenge_digits"].replace(" ", "") == digits.replace(" ", "")
        if success:
            await VoiceChallengeModel.delete_challenge(challenge_id)
        return success


    @staticmethod
    async def delete_challenge(challenge_id: str) -> bool:
        """Remove a challenge record after use."""
        await db_manager.execute(
            "DELETE FROM voice_challenges WHERE id = ?", (challenge_id,)
        )
        return True

    @staticmethod
    async def cleanup_expired() -> int:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rows = await db_manager.fetch_all(
            "SELECT id FROM voice_challenges WHERE expires_at < ?", (now,)
        )
        count = len(rows)
        if count > 0:
            await db_manager.execute(
                "DELETE FROM voice_challenges WHERE expires_at < ?", (now,)
            )
        return count


class VoiceAuthSessionModel:
    """Operations for secure, device-bound, command-scoped voice auth sessions."""

    @staticmethod
    async def create_session(user_id: str, device_id: str, command_scope: str, verification_source: str = 'mfcc_fallback', expires_in_sec: int = 60) -> dict:
        session_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = (now + datetime.timedelta(seconds=expires_in_sec)).isoformat()
        now_str = now.isoformat()

        await db_manager.execute(
            """INSERT INTO voice_auth_sessions (
                id, user_id, device_id, command_scope, verification_status,
                challenge_status, verification_source, used, expires_at, created_at
            ) VALUES (?, ?, ?, ?, 'pending', 'pending', ?, 0, ?, ?)""",
            (session_id, user_id, device_id, command_scope, verification_source, expires_at, now_str)
        )
        logger.info("Created voice auth session %s for user %s, scope: %s", session_id, user_id, command_scope)
        return await VoiceAuthSessionModel.get_session(session_id)

    @staticmethod
    async def get_session(session_id: str) -> Optional[dict]:
        row = await db_manager.fetch_one(
            "SELECT * FROM voice_auth_sessions WHERE id = ?", (session_id,)
        )
        if not row:
            return None
        
        # Expiration check
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if row["expires_at"] < now:
            return None
            
        return dict(row)

    @staticmethod
    async def update_verification(session_id: str, status: str) -> bool:
        await db_manager.execute(
            "UPDATE voice_auth_sessions SET verification_status = ? WHERE id = ?",
            (status, session_id)
        )
        return True

    @staticmethod
    async def update_challenge(session_id: str, status: str) -> bool:
        await db_manager.execute(
            "UPDATE voice_auth_sessions SET challenge_status = ? WHERE id = ?",
            (status, session_id)
        )
        return True

    @staticmethod
    async def mark_used(session_id: str) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor = await db_manager.execute(
            "UPDATE voice_auth_sessions SET used = 1, used_at = ? WHERE id = ? AND used = 0",
            (now, session_id)
        )
        return cursor.rowcount == 1

    @staticmethod
    async def cleanup_expired(retention_days: int = 7) -> int:
        cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)).isoformat()
        rows = await db_manager.fetch_all(
            "SELECT id FROM voice_auth_sessions WHERE expires_at < ?", (cutoff,)
        )
        count = len(rows)
        if count > 0:
            await db_manager.execute(
                "DELETE FROM voice_auth_sessions WHERE expires_at < ?", (cutoff,)
            )
        return count
