"""
Command Model — Tool-Based Command Queue
-------------------------------------------
Stores commands parsed from natural language as tool-based actions.
Supports Trust Levels (SAFE/CAUTION/DANGEROUS) and approval workflow.

Schema: { "tool": "desktop.open_app", "params": {"app": "vscode"}, "device_type": "desktop" }
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

class CommandStatus(str, Enum):
    PENDING = "pending"             # Waiting for agent to pick up
    AWAITING_APPROVAL = "awaiting_approval"  # Needs user approval (CAUTION/DANGEROUS)
    APPROVED = "approved"           # Approved, ready for execution
    EXECUTING = "executing"         # Agent is executing
    COMPLETED = "completed"         # Successfully completed
    FAILED = "failed"               # Execution failed
    REJECTED = "rejected"           # User rejected the action
    TIMEOUT = "timeout"             # Agent didn't pick up in time
    CANCELLED = "cancelled"         # User cancelled


class TrustLevel(str, Enum):
    SAFE = "safe"                   # Auto-execute: open_app, search, list_files
    CAUTION = "caution"             # User approval: create_folder, git_commit
    DANGEROUS = "dangerous"         # Double confirmation: delete, run_script


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class CommandCreate(BaseModel):
    """Request schema for creating a command from chat."""
    device_id: str
    tool: str = Field(..., description="Tool name: desktop.open_app, files.list, etc.")
    params: dict = Field(default_factory=dict, description="Tool parameters")
    device_type: str = Field("desktop", description="desktop, mobile, tablet")
    priority: int = Field(3, ge=1, le=5, description="1=lowest, 5=highest")
    raw_input: str = Field("", description="Original user message")
    source_language: str = Field("en", description="ta, en, mixed")
    source: str = Field("chat", description="chat, voice, vs_code, etc.")
    voice_auth_session_id: Optional[str] = None


class CommandResponse(BaseModel):
    """Response schema for a command."""
    id: str
    device_id: str
    user_id: str
    tool: str
    params: dict
    device_type: str
    status: str
    trust_level: str
    priority: int
    approval_required: bool
    approved_by: Optional[str] = None
    raw_input: str
    source_language: str
    source: str
    created_at: str
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None


class CommandApproval(BaseModel):
    """Schema for approving/rejecting a command."""
    approved: bool = True
    approved_by: str = "admin"


# ── Database Operations ───────────────────────────────────────────────────────

class CommandModel:
    """Command queue CRUD operations."""

    # ── Trust level classification ─────────────────────────────────────────────
    TRUST_MAP: dict[str, TrustLevel] = {
        # SAFE — Auto-execute
        "desktop.open_app":     TrustLevel.SAFE,
        "desktop.list_apps":    TrustLevel.SAFE,
        "browser.open":         TrustLevel.SAFE,
        "browser.search":       TrustLevel.SAFE,
        "files.list":           TrustLevel.SAFE,
        "files.search":         TrustLevel.SAFE,
        "files.read":           TrustLevel.SAFE,
        "screen.capture":       TrustLevel.SAFE,
        "screen.active_window": TrustLevel.SAFE,
        "screen.region_capture": TrustLevel.SAFE,
        "screen.multi_monitor_capture": TrustLevel.SAFE,
        "screen.ocr":           TrustLevel.SAFE,
        "screen.read_error":    TrustLevel.SAFE,
        "screen.extract_text":  TrustLevel.SAFE,
        "process.list":         TrustLevel.SAFE,
        "vscode.open_file":     TrustLevel.SAFE,
        "vscode.search_code":   TrustLevel.SAFE,
        "vscode.create_project": TrustLevel.SAFE,
        "vscode.run_tests":     TrustLevel.SAFE,
        "coding.read_code":     TrustLevel.SAFE,
        "coding.run_tests":     TrustLevel.SAFE,
        "coding.explain_code":  TrustLevel.SAFE,
        "coding.search_symbol": TrustLevel.SAFE,
        "coding.analyze_project": TrustLevel.SAFE,

        # CAUTION — User approval
        "desktop.close_app":    TrustLevel.CAUTION,
        "files.create_folder":  TrustLevel.CAUTION,
        "files.rename":         TrustLevel.CAUTION,
        "files.move":           TrustLevel.CAUTION,
        "coding.create_project": TrustLevel.CAUTION,
        "coding.write_code":     TrustLevel.CAUTION,
        "coding.restore_backup": TrustLevel.CAUTION,
        "git.commit":           TrustLevel.CAUTION,

        # DANGEROUS — Double confirmation
        "files.delete":         TrustLevel.DANGEROUS,
        "process.kill":         TrustLevel.DANGEROUS,
        "script.execute":       TrustLevel.DANGEROUS,
        "system.shutdown":      TrustLevel.DANGEROUS,
        "system.restart":       TrustLevel.DANGEROUS,
        "git.push":             TrustLevel.DANGEROUS,
    }

    @staticmethod
    def classify_trust(tool: str) -> TrustLevel:
        """Determine trust level for a tool action."""
        return CommandModel.TRUST_MAP.get(tool, TrustLevel.CAUTION)

    # ── CRUD ───────────────────────────────────────────────────────────────────

    @staticmethod
    async def create(user_id: str, data: CommandCreate, voice_verified: bool = False) -> dict:
        """Create a new command in the queue."""
        command_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        trust_level = CommandModel.classify_trust(data.tool)

        # Determine if approval is required
        approval_required = trust_level in (TrustLevel.CAUTION, TrustLevel.DANGEROUS) and not voice_verified

        # Set initial status based on trust level
        if trust_level == TrustLevel.SAFE or voice_verified:
            status = CommandStatus.PENDING
        else:
            status = CommandStatus.AWAITING_APPROVAL

        await db_manager.execute(
            """INSERT INTO commands
               (id, device_id, user_id, tool, params, device_type, status,
                trust_level, priority, approval_required, raw_input,
                source_language, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                command_id, data.device_id, user_id,
                data.tool, json.dumps(data.params),
                data.device_type, status.value,
                trust_level.value, data.priority,
                int(approval_required),
                data.raw_input, data.source_language, getattr(data, "source", "chat"), now,
            ),
        )

        logger.info(
            "Command created: %s [%s] trust=%s status=%s",
            data.tool, command_id[:8], trust_level.value, status.value
        )
        return await CommandModel.get_by_id(command_id)

    @staticmethod
    async def get_by_id(command_id: str) -> Optional[dict]:
        """Get command by ID."""
        row = await db_manager.fetch_one(
            "SELECT * FROM commands WHERE id = ?", (command_id,)
        )
        if row:
            row["params"] = json.loads(row.get("params", "{}"))
            row["approval_required"] = bool(row.get("approval_required", 0))
        return row

    @staticmethod
    async def poll_pending(device_id: str, limit: int = 10) -> list[dict]:
        """
        Poll pending commands for a specific device.
        Returns commands that are PENDING (SAFE auto-approved)
        or APPROVED (CAUTION/DANGEROUS manually approved).
        Ordered by priority (high first), then creation time.
        """
        rows = await db_manager.fetch_all(
            """SELECT * FROM commands
               WHERE device_id = ?
               AND status IN (?, ?)
               ORDER BY priority DESC, created_at ASC
               LIMIT ?""",
            (device_id, CommandStatus.PENDING.value,
             CommandStatus.APPROVED.value, limit),
        )
        for row in rows:
            row["params"] = json.loads(row.get("params", "{}"))
            row["approval_required"] = bool(row.get("approval_required", 0))
        return rows

    @staticmethod
    async def get_awaiting_approval(user_id: str) -> list[dict]:
        """Get commands awaiting user approval."""
        rows = await db_manager.fetch_all(
            """SELECT * FROM commands
               WHERE user_id = ? AND status = ?
               ORDER BY created_at DESC""",
            (user_id, CommandStatus.AWAITING_APPROVAL.value),
        )
        for row in rows:
            row["params"] = json.loads(row.get("params", "{}"))
            row["approval_required"] = bool(row.get("approval_required", 0))
        return rows

    @staticmethod
    async def approve(command_id: str, approved_by: str) -> Optional[dict]:
        """Approve a command for execution."""
        now = datetime.now(timezone.utc).isoformat()
        await db_manager.execute(
            """UPDATE commands
               SET status = ?, approved_by = ?, approved_at = ?
               WHERE id = ? AND status = ?""",
            (CommandStatus.APPROVED.value, approved_by, now,
             command_id, CommandStatus.AWAITING_APPROVAL.value),
        )
        logger.info("Command approved: %s by %s", command_id[:8], approved_by)
        return await CommandModel.get_by_id(command_id)

    @staticmethod
    async def reject(command_id: str) -> Optional[dict]:
        """Reject a command."""
        await db_manager.execute(
            """UPDATE commands SET status = ? WHERE id = ? AND status = ?""",
            (CommandStatus.REJECTED.value, command_id,
             CommandStatus.AWAITING_APPROVAL.value),
        )
        logger.info("Command rejected: %s", command_id[:8])
        return await CommandModel.get_by_id(command_id)

    @staticmethod
    async def update_status(
        command_id: str,
        status: CommandStatus,
        executed_at: Optional[str] = None,
        completed_at: Optional[str] = None,
    ):
        """Update command status."""
        fields = ["status = ?"]
        params = [status.value]

        if executed_at:
            fields.append("executed_at = ?")
            params.append(executed_at)
        if completed_at:
            fields.append("completed_at = ?")
            params.append(completed_at)

        params.append(command_id)
        await db_manager.execute(
            f"UPDATE commands SET {', '.join(fields)} WHERE id = ?",
            tuple(params),
        )

    @staticmethod
    async def history(
        user_id: str,
        limit: int = 50,
        device_id: Optional[str] = None,
    ) -> list[dict]:
        """Get command history for a user."""
        if device_id:
            rows = await db_manager.fetch_all(
                """SELECT * FROM commands
                   WHERE user_id = ? AND device_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, device_id, limit),
            )
        else:
            rows = await db_manager.fetch_all(
                """SELECT * FROM commands
                   WHERE user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            )
        for row in rows:
            row["params"] = json.loads(row.get("params", "{}"))
            row["approval_required"] = bool(row.get("approval_required", 0))
        return rows

    @staticmethod
    async def cancel(command_id: str):
        """Cancel a command."""
        await db_manager.execute(
            """UPDATE commands SET status = ?
               WHERE id = ? AND status IN (?, ?, ?)""",
            (CommandStatus.CANCELLED.value, command_id,
             CommandStatus.PENDING.value,
             CommandStatus.AWAITING_APPROVAL.value,
             CommandStatus.APPROVED.value),
        )

    @staticmethod
    async def timeout_stale(timeout_minutes: int = 10):
        """Mark old pending/approved commands as timed out."""
        cutoff = datetime.now(timezone.utc).isoformat()
        await db_manager.execute(
            """UPDATE commands SET status = ?
               WHERE status IN (?, ?)
               AND datetime(created_at, '+' || ? || ' minutes') < datetime(?)""",
            (CommandStatus.TIMEOUT.value,
             CommandStatus.PENDING.value, CommandStatus.APPROVED.value,
             str(timeout_minutes), cutoff),
        )
