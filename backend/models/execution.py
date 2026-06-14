"""
Execution Model — Command Execution Results
----------------------------------------------
Tracks the outcome of each command executed by a desktop/mobile agent.
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

class ExecutionStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    PARTIAL = "partial"         # Some steps succeeded, some failed


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class ExecutionCreate(BaseModel):
    """Agent reports starting execution."""
    command_id: str
    device_id: str


class ExecutionResult(BaseModel):
    """Agent reports execution result."""
    execution_id: str
    status: ExecutionStatus
    result: dict = Field(default_factory=dict)
    error_message: Optional[str] = None
    duration_ms: float = 0.0


class ExecutionResponse(BaseModel):
    """API response for execution info."""
    id: str
    command_id: str
    device_id: str
    status: str
    result: dict
    error_message: Optional[str] = None
    duration_ms: float
    executed_at: str
    completed_at: Optional[str] = None


# ── Database Operations ───────────────────────────────────────────────────────

class ExecutionModel:
    """Execution result CRUD operations."""

    @staticmethod
    async def create(data: ExecutionCreate) -> dict:
        """Record the start of an execution."""
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        await db_manager.execute(
            """INSERT INTO executions
               (id, command_id, device_id, status, executed_at)
               VALUES (?, ?, ?, ?, ?)""",
            (execution_id, data.command_id, data.device_id,
             ExecutionStatus.RUNNING.value, now),
        )

        logger.info(
            "Execution started: %s for command %s",
            execution_id[:8], data.command_id[:8]
        )
        return await ExecutionModel.get_by_id(execution_id)

    @staticmethod
    async def complete(data: ExecutionResult) -> Optional[dict]:
        """Record execution completion with result."""
        now = datetime.now(timezone.utc).isoformat()

        await db_manager.execute(
            """UPDATE executions
               SET status = ?, result = ?, error_message = ?,
                   duration_ms = ?, completed_at = ?
               WHERE id = ?""",
            (
                data.status.value,
                json.dumps(data.result),
                data.error_message,
                data.duration_ms,
                now,
                data.execution_id,
            ),
        )

        logger.info(
            "Execution completed: %s status=%s (%.0fms)",
            data.execution_id[:8], data.status.value, data.duration_ms
        )
        return await ExecutionModel.get_by_id(data.execution_id)

    @staticmethod
    async def get_by_id(execution_id: str) -> Optional[dict]:
        """Get execution by ID."""
        row = await db_manager.fetch_one(
            "SELECT * FROM executions WHERE id = ?", (execution_id,)
        )
        if row:
            row["result"] = json.loads(row.get("result", "{}"))
        return row

    @staticmethod
    async def get_by_command(command_id: str) -> Optional[dict]:
        """Get execution result for a command."""
        row = await db_manager.fetch_one(
            "SELECT * FROM executions WHERE command_id = ? ORDER BY executed_at DESC LIMIT 1",
            (command_id,),
        )
        if row:
            row["result"] = json.loads(row.get("result", "{}"))
        return row

    @staticmethod
    async def list_by_device(
        device_id: str,
        limit: int = 50,
        status: Optional[ExecutionStatus] = None,
    ) -> list[dict]:
        """List executions for a device."""
        if status:
            rows = await db_manager.fetch_all(
                """SELECT * FROM executions
                   WHERE device_id = ? AND status = ?
                   ORDER BY executed_at DESC LIMIT ?""",
                (device_id, status.value, limit),
            )
        else:
            rows = await db_manager.fetch_all(
                """SELECT * FROM executions
                   WHERE device_id = ?
                   ORDER BY executed_at DESC LIMIT ?""",
                (device_id, limit),
            )
        for row in rows:
            row["result"] = json.loads(row.get("result", "{}"))
        return rows

    @staticmethod
    async def stats(device_id: Optional[str] = None) -> dict:
        """Get execution statistics."""
        if device_id:
            base = "SELECT status, COUNT(*) as cnt FROM executions WHERE device_id = ? GROUP BY status"
            rows = await db_manager.fetch_all(base, (device_id,))
        else:
            rows = await db_manager.fetch_all(
                "SELECT status, COUNT(*) as cnt FROM executions GROUP BY status"
            )
        return {row["status"]: row["cnt"] for row in rows}
