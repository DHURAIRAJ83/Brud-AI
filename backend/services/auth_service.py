"""
Auth Service — Phase 5: Multi-User Authentication
---------------------------------------------------
Provides:
  - bcrypt password hashing / verification
  - JWT access token generation / verification
  - Token-based user lookup dependency for FastAPI routes
"""

import logging
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from models.base import db_manager

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
from config import get_settings
_settings = get_settings()
SECRET_KEY = _settings.secret_key
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be configured in environment (.env).")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 30 minutes
REFRESH_TOKEN_EXPIRE_DAYS = 30    # 30 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── DB-backed auth operations ─────────────────────────────────────────────────

class AuthService:
    """Handles registration, login, and token verification."""

    async def register(self, username: str, password: str, email: str = "", display_name: str = "") -> dict:
        """Create a new user with hashed password. Raises HTTPException on conflict."""
        existing = await db_manager.fetch_one(
            "SELECT id FROM users WHERE username = ?", (username,)
        )
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken.")

        hashed = hash_password(password)
        import uuid
        from datetime import datetime, timezone
        user_id = str(uuid.uuid4())
        api_key = f"rudran_{uuid.uuid4().hex[:24]}"
        now = datetime.now(timezone.utc).isoformat()

        await db_manager.execute(
            """INSERT INTO users
               (id, username, display_name, email, role, api_key, hashed_password, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'standard', ?, ?, ?, ?)""",
            (user_id, username, display_name or username, email, api_key, hashed, now, now),
        )
        logger.info("Registered new user: %s", username)
        return await self._get_user(user_id)

    async def login(self, username: str, password: str) -> dict:
        """Verify credentials and return JWT access token."""
        row = await db_manager.fetch_one(
            "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
        )
        if not row:
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        hashed = row.get("hashed_password", "")
        if not hashed or not verify_password(password, hashed):
            raise HTTPException(status_code=401, detail="Invalid username or password.")

        token = create_access_token({"sub": row["id"], "username": row["username"]})
        logger.info("User logged in: %s", username)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": row["id"],
                "username": row["username"],
                "display_name": row.get("display_name", ""),
                "email": row.get("email", ""),
                "role": row.get("role", "standard"),
                "password_change_required": bool(row.get("password_change_required", 0)),
            },
        }

    async def _get_user(self, user_id: str) -> Optional[dict]:
        row = await db_manager.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if row:
            row.pop("hashed_password", None)
        return row

    def hash_refresh_token(self, token: str) -> str:
        """Compute the SHA-256 hash of a token string."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def create_refresh_token(self, user_id: str) -> tuple[str, str]:
        """Generate a secure refresh token and CSRF token, store hashed refresh token + CSRF in DB, and return both plain values."""
        plain_token = secrets.token_hex(32)
        csrf_token = secrets.token_hex(32)
        token_hash = self.hash_refresh_token(plain_token)
        
        import uuid
        now = datetime.now(timezone.utc).isoformat()
        expires = (datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).isoformat()
        
        await db_manager.execute(
            """INSERT INTO refresh_tokens (id, token_hash, user_id, csrf_token, expires_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), token_hash, user_id, csrf_token, expires, now)
        )
        return plain_token, csrf_token

    async def verify_refresh_token(self, token: str, csrf_token: str) -> Optional[dict]:
        """Hash the plain token and verify it against active database records with CSRF validation."""
        token_hash = self.hash_refresh_token(token)
        row = await db_manager.fetch_one(
            "SELECT * FROM refresh_tokens WHERE token_hash = ?", (token_hash,)
        )
        if not row:
            return None
            
        if row.get("csrf_token") != csrf_token:
            return None
            
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            await db_manager.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
            return None
            
        return await self._get_user(row["user_id"])

    async def revoke_refresh_token(self, token: str):
        """Revoke a refresh token by deleting its hash from the database."""
        token_hash = self.hash_refresh_token(token)
        await db_manager.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))

    async def get_current_user(self, token: Optional[str]) -> Optional[dict]:
        """Decode JWT and return user dict, or None if invalid/missing."""
        if not token:
            return None
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            if not user_id:
                return None
            return await self._get_user(user_id)
        except JWTError:
            return None


# ── FastAPI dependencies ──────────────────────────────────────────────────────

auth_service = AuthService()


from fastapi.security import APIKeyHeader
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    api_key: Optional[str] = Depends(api_key_header)
) -> Optional[dict]:
    """Optional auth dependency — returns None if no token or api_key (guest mode)."""
    if _settings.app_env == "production" and not _settings.security_enabled:
        raise RuntimeError("SECURITY_ENABLED cannot be False in production environment.")

    if not _settings.security_enabled:
        return {
            "id": "admin-user-123",
            "username": "admin",
            "role": "admin",
            "display_name": "Admin",
            "email": "admin@example.com"
        }

    if api_key:
        from models.user import UserModel
        user = await UserModel.get_by_api_key(api_key)
        if user:
            return user
            
    return await auth_service.get_current_user(token)


async def require_user(
    token: Optional[str] = Depends(oauth2_scheme),
    api_key: Optional[str] = Depends(api_key_header)
) -> dict:
    """Strict auth dependency — raises 401 if not authenticated."""
    user = await get_current_user(token, api_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    token: Optional[str] = Depends(oauth2_scheme),
    api_key: Optional[str] = Depends(api_key_header)
) -> dict:
    """Admin-only dependency."""
    user = await require_user(token, api_key)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
