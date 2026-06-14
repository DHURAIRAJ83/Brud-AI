"""
Audit Log Model — Security & Activity Tracking
-------------------------------------------------
Records all significant actions for security auditing.
Every command, device event, and security event is logged.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from models.base import db_manager

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────────────────

class AuditAction(str, Enum):
    # Device events
    DEVICE_REGISTERED = "device.registered"
    DEVICE_HEARTBEAT = "device.heartbeat"
    DEVICE_OFFLINE = "device.offline"
    DEVICE_UNREGISTERED = "device.unregistered"

    # Command events
    COMMAND_CREATED = "command.created"
    COMMAND_APPROVED = "command.approved"
    COMMAND_REJECTED = "command.rejected"
    COMMAND_EXECUTED = "command.executed"
    COMMAND_COMPLETED = "command.completed"
    COMMAND_FAILED = "command.failed"
    COMMAND_CANCELLED = "command.cancelled"

    # Security events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_RATE_LIMITED = "auth.rate_limited"
    SECURITY_ALERT = "security.alert"

    # Voice events
    VOICE_PROFILE_CREATED = "voice.profile_created"
    VOICE_PROFILE_REVOKED = "voice.profile_revoked"
    VOICE_AUTH_SUCCESS = "voice.auth_success"
    VOICE_AUTH_FAILURE = "voice.auth_failure"
    VOICE_REPLAY_BLOCKED = "voice.replay_blocked"
    VOICE_CHALLENGE_SUCCESS = "voice.challenge_success"
    VOICE_CHALLENGE_FAILURE = "voice.challenge_failure"
    VOICE_LOCKOUT_TRIGGERED = "voice.lockout_triggered"

    # User events
    USER_CREATED = "user.created"
    USER_DEACTIVATED = "user.deactivated"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"


class AuditCategory(str, Enum):
    DEVICE = "device"
    COMMAND = "command"
    SECURITY = "security"
    USER = "user"
    SYSTEM = "system"


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class AuditLogCreate(BaseModel):
    """Schema for creating an audit entry."""
    action: AuditAction
    category: AuditCategory = AuditCategory.SYSTEM
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    details: dict = Field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""


class AuditLogResponse(BaseModel):
    """API response for audit log entries."""
    id: str
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    action: str
    category: str = "system"
    details: dict = Field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    timestamp: str


# ── Database Operations ───────────────────────────────────────────────────────

class AuditLogModel:
    """Audit log operations — append-only for security."""

    @staticmethod
    async def log(
        action: AuditAction,
        category: AuditCategory = AuditCategory.SYSTEM,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> str:
        """Create an audit log entry. Returns log ID."""
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        await db_manager.execute(
            """INSERT INTO audit_logs
               (id, user_id, device_id, action, category, details,
                ip_address, user_agent, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                log_id, user_id, device_id,
                action.value, category.value,
                json.dumps(details or {}),
                ip_address, user_agent, now,
            ),
        )
        return log_id

    @staticmethod
    async def query(
        limit: int = 100,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        action: Optional[str] = None,
        category: Optional[str] = None,
        since: Optional[str] = None,
    ) -> list[dict]:
        """Query audit logs with optional filters."""
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if device_id:
            conditions.append("device_id = ?")
            params.append(device_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        rows = await db_manager.fetch_all(
            f"""SELECT * FROM audit_logs
                WHERE {where_clause}
                ORDER BY timestamp DESC LIMIT ?""",
            tuple(params),
        )
        for row in rows:
            row["details"] = json.loads(row.get("details", "{}"))
        return rows

    @staticmethod
    async def count_by_action(hours: int = 24) -> dict:
        """Count audit entries by action in the last N hours."""
        rows = await db_manager.fetch_all(
            """SELECT action, COUNT(*) as cnt
               FROM audit_logs
               WHERE timestamp >= datetime('now', '-' || ? || ' hours')
               GROUP BY action
               ORDER BY cnt DESC""",
            (str(hours),),
        )
        return {row["action"]: row["cnt"] for row in rows}

    @staticmethod
    async def recent_security_events(limit: int = 20) -> list[dict]:
        """Get recent security-related audit entries."""
        rows = await db_manager.fetch_all(
            """SELECT * FROM audit_logs
               WHERE category = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (AuditCategory.SECURITY.value, limit),
        )
        for row in rows:
            row["details"] = json.loads(row.get("details", "{}"))
        return rows

    @staticmethod
    async def cleanup(days: int = 90):
        """Delete audit logs older than N days."""
        await db_manager.execute(
            """DELETE FROM audit_logs
               WHERE timestamp < datetime('now', '-' || ? || ' days')""",
            (str(days),),
        )
        logger.info("Cleaned up audit logs older than %d days", days)
