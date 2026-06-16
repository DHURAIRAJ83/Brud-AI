"""
API Security Layer — Key Authentication + Rate Limiting
---------------------------------------------------------
Middleware-based security with zero external dependencies.

Features:
  - API key validation via X-API-Key header or ?api_key= query param
  - Per-key rate limiting (sliding window)
  - Usage tracking per key
  - Admin bypass key
  - Configurable limits per key tier

Usage:
  Set API_KEYS in .env:
    API_KEYS=key1:standard,key2:admin,key3:standard

  Add header to requests:
    X-API-Key: key1

  Or query param:
    POST /api/chat?api_key=key1

  Set SECURITY_ENABLED=false in .env to disable for local dev.
"""

import logging
import time
from collections import defaultdict
from typing import Optional
import uuid
import asyncio

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Rate limit windows (requests per minute) ──────────────────────────────────
RATE_LIMITS = {
    "admin":    1000,   # Essentially unlimited
    "standard": 60,     # 1 request/second average
    "limited":  10,     # For trial/demo users
}

# Public endpoints that don't require auth
PUBLIC_PATHS = {
    "/",
    "",
    "/health",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/api/auth/logout"
}


class ApiKeyManager:
    """Manages API keys, tiers, and usage."""

    def __init__(self):
        self._keys: dict[str, str] = {}  # key → tier
        self._usage: dict[str, int] = defaultdict(int)
        self._load_keys()

    def _load_keys(self):
        """Load API keys from settings. Format: 'key1:tier,key2:tier'"""
        raw = getattr(settings, "api_keys", "")
        if not raw:
            # Auto-generate a dev key when none configured
            self._keys["dev-local-key-12345"] = "admin"
            logger.warning(
                "No API_KEYS configured. Using dev key: dev-local-key-12345"
            )
            return

        for pair in raw.split(","):
            pair = pair.strip()
            if ":" in pair:
                key, tier = pair.split(":", 1)
                self._keys[key.strip()] = tier.strip()
            elif pair:
                self._keys[pair] = "standard"

        logger.info("Loaded %d API key(s)", len(self._keys))

    def validate(self, key: str) -> Optional[str]:
        """Return tier if valid, None if invalid."""
        return self._keys.get(key)

    def record_usage(self, key: str):
        self._usage[key] += 1

    def get_usage(self) -> dict:
        return dict(self._usage)

    def add_key(self, key: str, tier: str = "standard"):
        self._keys[key] = tier

    def revoke_key(self, key: str):
        self._keys.pop(key, None)


class RateLimiter:
    """SQLite-backed sliding window rate limiter per API key or IP address."""

    def __init__(self):
        self._last_cleanup = 0.0

    async def is_allowed(self, key: str, tier: str) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.
        Returns (allowed, metadata).
        """
        from models.base import db_manager
        
        limit = RATE_LIMITS.get(tier, RATE_LIMITS["standard"])
        now = time.time()
        
        # Periodic cleanup (throttle to once every 5 mins)
        if now - self._last_cleanup > 300:
            asyncio.create_task(self._cleanup(now))
            self._last_cleanup = now
            
        # Get or create rate limit record
        row = await db_manager.fetch_one("SELECT * FROM rate_limits WHERE key_or_ip = ?", (key,))
        
        if not row:
            # Create new record
            record_id = str(uuid.uuid4())
            await db_manager.execute(
                "INSERT INTO rate_limits (id, key_or_ip, tier, window_start, request_count) VALUES (?, ?, ?, ?, ?)",
                (record_id, key, tier, now, 1)
            )
            return True, {
                "limit": limit,
                "remaining": limit - 1,
                "reset_in_seconds": 60,
                "tier": tier,
            }
            
        # Check window
        window_start = row["window_start"]
        request_count = row["request_count"]
        
        if now - window_start > 60:
            # Reset window
            await db_manager.execute(
                "UPDATE rate_limits SET window_start = ?, request_count = 1, updated_at = datetime('now') WHERE key_or_ip = ?",
                (now, key)
            )
            return True, {
                "limit": limit,
                "remaining": limit - 1,
                "reset_in_seconds": 60,
                "tier": tier,
            }
            
        # Check limit
        if request_count >= limit:
            reset_in = int(60 - (now - window_start))
            logger.warning("Rate limit exceeded for %s (tier: %s). Limit: %d", key, tier, limit)
            return False, {
                "limit": limit,
                "remaining": 0,
                "reset_in_seconds": max(0, reset_in),
                "tier": tier,
            }
            
        # Increment count
        await db_manager.execute(
            "UPDATE rate_limits SET request_count = request_count + 1, updated_at = datetime('now') WHERE key_or_ip = ?",
            (key,)
        )
        reset_in = int(60 - (now - window_start))
        return True, {
            "limit": limit,
            "remaining": limit - (request_count + 1),
            "reset_in_seconds": max(0, reset_in),
            "tier": tier,
        }

    async def _cleanup(self, now: float):
        """Clean up old rate limits to keep database small."""
        try:
            from models.base import db_manager
            # Delete records older than 5 minutes (300 seconds)
            cutoff = now - 300
            await db_manager.execute("DELETE FROM rate_limits WHERE window_start < ?", (cutoff,))
        except Exception as e:
            logger.error("Rate limiter cleanup failed: %s", e)


# Singletons
api_key_manager = ApiKeyManager()
rate_limiter = RateLimiter()


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for API key auth + rate limiting.
    Allows authenticated users with valid JWT access tokens to pass without an API key.
    Adds X-Rate-Limit-* headers to all responses.
    """

    async def dispatch(self, request: Request, call_next):
        # ── Always pass through OPTIONS (CORS preflight) ──────────────────────
        if request.method == "OPTIONS":
            return await call_next(request)

        # ── Setup Real IP for logging and IP-based rate limit ───────────────
        client_ip = request.client.host if request.client else "unknown"
        real_ip = request.headers.get("X-Forwarded-For", request.headers.get("X-Real-IP", client_ip))
        if real_ip and "," in real_ip:
            real_ip = real_ip.split(",")[0].strip()
            
        is_loopback = real_ip in ("127.0.0.1", "::1", "testclient", "localhost")

        # Skip security for public paths
        if not getattr(settings, "security_enabled", False):
            return await call_next(request)

        path = request.url.path
        normalized_path = path.rstrip("/") if path != "/" else path
        if normalized_path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            if not is_loopback:
                # Apply IP-based rate limit for public endpoints
                allowed, rl_meta = await rate_limiter.is_allowed(real_ip, "standard")
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        headers={
                            "X-Rate-Limit-Limit": str(rl_meta["limit"]),
                            "X-Rate-Limit-Remaining": "0",
                            "X-Rate-Limit-Reset": str(rl_meta["reset_in_seconds"]),
                            "Retry-After": str(rl_meta["reset_in_seconds"]),
                        },
                        content={
                            "detail": f"Rate limit exceeded for IP. {rl_meta['limit']} requests/minute.",
                            "reset_in_seconds": rl_meta["reset_in_seconds"],
                        },
                    )
            return await call_next(request)

        # ── Try JWT Bearer Authentication First ───────────────────────────────
        auth_header = request.headers.get("Authorization")
        user = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                from services.auth_service import decode_token
                from models.user import UserModel
                payload = decode_token(token)
                user_id = payload.get("sub")
                if user_id:
                    user = await UserModel.get_by_id(user_id)
            except Exception as e:
                logger.warning("JWT token validation failed for IP %s: %s", real_ip, e)

        if user:
            # User is successfully authenticated via JWT. Rate limit based on user ID and role.
            role = user.get("role", "standard")
            allowed, rl_meta = await rate_limiter.is_allowed(user["id"], role)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    headers={
                        "X-Rate-Limit-Limit": str(rl_meta["limit"]),
                        "X-Rate-Limit-Remaining": "0",
                        "X-Rate-Limit-Reset": str(rl_meta["reset_in_seconds"]),
                        "Retry-After": str(rl_meta["reset_in_seconds"]),
                    },
                    content={
                        "detail": f"Rate limit exceeded. {rl_meta['limit']} requests/minute for '{role}' tier.",
                        "reset_in_seconds": rl_meta["reset_in_seconds"],
                    },
                )

            # Store user context details in request state for downstream dependencies
            request.state.api_key = user.get("api_key")
            request.state.tier = role

            response = await call_next(request)

            # Add rate limit headers
            response.headers["X-Rate-Limit-Limit"] = str(rl_meta["limit"])
            response.headers["X-Rate-Limit-Remaining"] = str(rl_meta["remaining"])
            response.headers["X-Rate-Limit-Reset"] = str(rl_meta["reset_in_seconds"])
            response.headers["X-API-Tier"] = role

            return response

        # ── Fallback to API Key Authentication ────────────────────────────────
        api_key = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
        )

        if not api_key:
            logger.warning("Missing API key or JWT token from IP: %s", real_ip)
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "API key or valid bearer token required. Add X-API-Key header or Authorization: Bearer <token>.",
                    "docs": "/docs",
                },
            )

        # Validate key
        tier = api_key_manager.validate(api_key)
        if not tier:
            logger.warning("Invalid API key used from IP: %s", real_ip)
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid or revoked API key."},
            )

        # Rate limit check
        allowed, rl_meta = await rate_limiter.is_allowed(api_key, tier)
        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={
                    "X-Rate-Limit-Limit": str(rl_meta["limit"]),
                    "X-Rate-Limit-Remaining": "0",
                    "X-Rate-Limit-Reset": str(rl_meta["reset_in_seconds"]),
                    "Retry-After": str(rl_meta["reset_in_seconds"]),
                },
                content={
                    "detail": f"Rate limit exceeded. {rl_meta['limit']} requests/minute for '{tier}' tier.",
                    "reset_in_seconds": rl_meta["reset_in_seconds"],
                },
            )

        # Record usage and proceed
        api_key_manager.record_usage(api_key)
        request.state.api_key = api_key
        request.state.tier = tier

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-Rate-Limit-Limit"] = str(rl_meta["limit"])
        response.headers["X-Rate-Limit-Remaining"] = str(rl_meta["remaining"])
        response.headers["X-Rate-Limit-Reset"] = str(rl_meta["reset_in_seconds"])
        response.headers["X-API-Tier"] = tier

        return response
