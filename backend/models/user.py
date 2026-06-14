"""
User Model — Pydantic schemas + SQLite operations
----------------------------------------------------
Manages user accounts, roles, and API keys.
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

class UserRole(str, Enum):
    ADMIN = "admin"
    STANDARD = "standard"
    LIMITED = "limited"


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    display_name: str = Field("", max_length=100)
    email: str = Field("", max_length=200)
    role: UserRole = UserRole.STANDARD


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    role: str
    is_active: bool
    api_key: Optional[str] = None
    preferences: dict = {}
    password_change_required: bool = False
    created_at: str
    updated_at: str


# ── Database Operations ───────────────────────────────────────────────────────

class UserModel:
    """User CRUD operations."""

    @staticmethod
    async def create(data: UserCreate) -> dict:
        """Create a new user with auto-generated ID and API key."""
        user_id = str(uuid.uuid4())
        api_key = f"rudran_{uuid.uuid4().hex[:24]}"
        now = datetime.now(timezone.utc).isoformat()

        await db_manager.execute(
            """INSERT INTO users (id, username, display_name, email, role, api_key, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, data.username, data.display_name, data.email,
             data.role.value, api_key, now, now),
        )

        logger.info("Created user: %s (role=%s)", data.username, data.role.value)
        return await UserModel.get_by_id(user_id)

    @staticmethod
    async def get_by_id(user_id: str) -> Optional[dict]:
        """Get user by ID."""
        row = await db_manager.fetch_one(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        if row:
            row["preferences"] = json.loads(row.get("preferences", "{}"))
            row["is_active"] = bool(row.get("is_active", 1))
            row["password_change_required"] = bool(row.get("password_change_required", 0))
        return row

    @staticmethod
    async def get_by_api_key(api_key: str) -> Optional[dict]:
        """Get user by API key."""
        row = await db_manager.fetch_one(
            "SELECT * FROM users WHERE api_key = ? AND is_active = 1", (api_key,)
        )
        if row:
            row["preferences"] = json.loads(row.get("preferences", "{}"))
            row["is_active"] = bool(row.get("is_active", 1))
            row["password_change_required"] = bool(row.get("password_change_required", 0))
        return row

    @staticmethod
    async def get_by_username(username: str) -> Optional[dict]:
        """Get user by username."""
        row = await db_manager.fetch_one(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        if row:
            row["preferences"] = json.loads(row.get("preferences", "{}"))
            row["is_active"] = bool(row.get("is_active", 1))
            row["password_change_required"] = bool(row.get("password_change_required", 0))
        return row

    @staticmethod
    async def list_all() -> list[dict]:
        """List all users."""
        rows = await db_manager.fetch_all(
            "SELECT id, username, display_name, role, is_active, created_at FROM users ORDER BY created_at DESC"
        )
        for row in rows:
            row["is_active"] = bool(row.get("is_active", 1))
        return rows

    @staticmethod
    async def update_preferences(user_id: str, preferences: dict):
        """Update user preferences."""
        now = datetime.now(timezone.utc).isoformat()
        await db_manager.execute(
            "UPDATE users SET preferences = ?, updated_at = ? WHERE id = ?",
            (json.dumps(preferences), now, user_id),
        )

    @staticmethod
    async def deactivate(user_id: str):
        """Deactivate a user."""
        now = datetime.now(timezone.utc).isoformat()
        await db_manager.execute(
            "UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?",
            (now, user_id),
        )

    @staticmethod
    async def ensure_default_user() -> dict:
        """Create a default admin user if none exists."""
        existing = await db_manager.fetch_one("SELECT id FROM users LIMIT 1")
        if existing:
            return await UserModel.get_by_id(existing["id"])

        from config import get_settings
        from services.auth_service import hash_password
        settings = get_settings()

        api_key = settings.admin_api_key or f"rudran_{uuid.uuid4().hex[:24]}"
        admin_pass = settings.admin_initial_password or "admin123"
        hashed = hash_password(admin_pass)

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        logger.info("Creating default admin user with username 'admin'...")
        await db_manager.execute(
            """INSERT INTO users (id, username, display_name, email, role, api_key, hashed_password, password_change_required, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'admin', ?, ?, 1, ?, ?)""",
            (user_id, "admin", "Rudran Admin", "", api_key, hashed, now, now)
        )
        return await UserModel.get_by_id(user_id)
