"""
Device Model — Registration, Heartbeat, Capabilities
-------------------------------------------------------
Manages desktop/mobile agent device registration.
Android-compatible schema from Day 1.
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

class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    PENDING = "pending"         # Registered but never connected


class OSType(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID = "android"
    IOS = "ios"
    VSCODE = "vscode"


class DeviceType(str, Enum):
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    SERVER = "server"
    VSCODE = "vscode"


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class DeviceRegister(BaseModel):
    """Request schema for device registration."""
    device_name: str = Field(..., min_length=1, max_length=100)
    device_type: DeviceType = DeviceType.DESKTOP
    os_type: OSType = OSType.WINDOWS
    os_version: str = Field("", max_length=50)
    agent_version: str = Field("1.0.0", max_length=20)
    capabilities: list[str] = Field(
        default_factory=lambda: [
            "desktop.open_app", "desktop.close_app",
            "browser.open", "browser.search",
            "files.list", "files.search", "files.read",
        ]
    )
    system_info: dict = Field(default_factory=dict)


class DeviceResponse(BaseModel):
    """Response schema for device info."""
    id: str
    user_id: str
    device_name: str
    device_type: str
    os_type: str
    os_version: str
    agent_version: str
    api_key: str
    status: str
    capabilities: list[str]
    system_info: dict
    last_heartbeat: Optional[str] = None
    registered_at: str


class DeviceHeartbeat(BaseModel):
    """Heartbeat payload from agent."""
    agent_version: str = "1.0.0"
    system_info: dict = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)


# ── Database Operations ───────────────────────────────────────────────────────

class DeviceModel:
    """Device CRUD operations."""

    @staticmethod
    async def register(user_id: str, data: DeviceRegister) -> dict:
        """Register a new device and return its info with API key."""
        device_id = str(uuid.uuid4())
        api_key = f"rdv_{uuid.uuid4().hex[:32]}"
        now = datetime.now(timezone.utc).isoformat()

        await db_manager.execute(
            """INSERT INTO devices
               (id, user_id, device_name, device_type, os_type, os_version,
                agent_version, api_key, status, capabilities, system_info,
                registered_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                device_id, user_id, data.device_name,
                data.device_type.value, data.os_type.value,
                data.os_version, data.agent_version,
                api_key, DeviceStatus.PENDING.value,
                json.dumps(data.capabilities),
                json.dumps(data.system_info),
                now, now,
            ),
        )

        logger.info(
            "Registered device: %s (%s/%s) for user %s",
            data.device_name, data.device_type.value, data.os_type.value, user_id
        )
        return await DeviceModel.get_by_id(device_id)

    @staticmethod
    async def get_by_id(device_id: str) -> Optional[dict]:
        """Get device by ID."""
        row = await db_manager.fetch_one(
            "SELECT * FROM devices WHERE id = ?", (device_id,)
        )
        if row:
            row["capabilities"] = json.loads(row.get("capabilities", "[]"))
            row["system_info"] = json.loads(row.get("system_info", "{}"))
        return row

    @staticmethod
    async def get_by_api_key(api_key: str) -> Optional[dict]:
        """Get device by its unique API key."""
        row = await db_manager.fetch_one(
            "SELECT * FROM devices WHERE api_key = ?", (api_key,)
        )
        if row:
            row["capabilities"] = json.loads(row.get("capabilities", "[]"))
            row["system_info"] = json.loads(row.get("system_info", "{}"))
        return row

    @staticmethod
    async def list_by_user(user_id: str) -> list[dict]:
        """List all devices for a user."""
        rows = await db_manager.fetch_all(
            "SELECT * FROM devices WHERE user_id = ? ORDER BY registered_at DESC",
            (user_id,),
        )
        for row in rows:
            row["capabilities"] = json.loads(row.get("capabilities", "[]"))
            row["system_info"] = json.loads(row.get("system_info", "{}"))
        return rows

    @staticmethod
    async def list_online() -> list[dict]:
        """List all online devices."""
        rows = await db_manager.fetch_all(
            "SELECT * FROM devices WHERE status = ?",
            (DeviceStatus.ONLINE.value,),
        )
        for row in rows:
            row["capabilities"] = json.loads(row.get("capabilities", "[]"))
            row["system_info"] = json.loads(row.get("system_info", "{}"))
        return rows

    @staticmethod
    async def heartbeat(device_id: str, data: DeviceHeartbeat) -> dict:
        """Update device heartbeat — marks as online."""
        now = datetime.now(timezone.utc).isoformat()
        await db_manager.execute(
            """UPDATE devices
               SET status = ?, last_heartbeat = ?, agent_version = ?,
                   system_info = ?, capabilities = ?, updated_at = ?
               WHERE id = ?""",
            (
                DeviceStatus.ONLINE.value, now, data.agent_version,
                json.dumps(data.system_info),
                json.dumps(data.capabilities) if data.capabilities else None,
                now, device_id,
            ),
        )
        return await DeviceModel.get_by_id(device_id)

    @staticmethod
    async def set_status(device_id: str, status: DeviceStatus):
        """Update device status."""
        now = datetime.now(timezone.utc).isoformat()
        await db_manager.execute(
            "UPDATE devices SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, now, device_id),
        )

    @staticmethod
    async def unregister(device_id: str):
        """Delete a device."""
        await db_manager.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        logger.info("Unregistered device: %s", device_id)

    @staticmethod
    async def check_stale_devices(timeout_minutes: int = 5):
        """Mark devices as offline if no heartbeat in timeout_minutes."""
        cutoff = datetime.now(timezone.utc).isoformat()
        # SQLite datetime comparison: mark as offline if heartbeat is too old
        await db_manager.execute(
            """UPDATE devices
               SET status = ?
               WHERE status = ?
               AND last_heartbeat IS NOT NULL
               AND datetime(last_heartbeat, '+' || ? || ' minutes') < datetime(?)""",
            (DeviceStatus.OFFLINE.value, DeviceStatus.ONLINE.value,
             str(timeout_minutes), cutoff),
        )

    @staticmethod
    async def has_capability(device_id: str, tool: str) -> bool:
        """Check if a device supports a specific tool."""
        device = await DeviceModel.get_by_id(device_id)
        if not device:
            return False
        return tool in device.get("capabilities", [])
