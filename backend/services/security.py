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
from collections import defaultdict, deque
from typing import Optional

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
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


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
    """Sliding window rate limiter per API key."""

    def __init__(self):
        # key → deque of timestamps (within last 60s)
        self._windows: dict[str, deque] = defaultdict(lambda: deque())

    def is_allowed(self, key: str, tier: str) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.
        Returns (allowed, metadata).
        """
        limit = RATE_LIMITS.get(tier, RATE_LIMITS["standard"])
        now = time.time()
        window = self._windows[key]

        # Drop timestamps older than 60 seconds
        while window and (now - window[0]) > 60:
            window.popleft()

        current_count = len(window)
        remaining = max(0, limit - current_count)
        reset_in = int(60 - (now - window[0])) if window else 60

        if current_count >= limit:
            return False, {
                "limit": limit,
                "remaining": 0,
                "reset_in_seconds": reset_in,
                "tier": tier,
            }

        window.append(now)
        return True, {
            "limit": limit,
            "remaining": remaining - 1,
            "reset_in_seconds": reset_in,
            "tier": tier,
        }


# Singletons
api_key_manager = ApiKeyManager()
rate_limiter = RateLimiter()


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for API key auth + rate limiting.
    Adds X-Rate-Limit-* headers to all responses.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip security for public paths
        if not getattr(settings, "security_enabled", False):
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Extract API key
        api_key = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
        )

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "API key required. Add X-API-Key header or ?api_key= param.",
                    "docs": "/docs",
                },
            )

        # Validate key
        tier = api_key_manager.validate(api_key)
        if not tier:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid or revoked API key."},
            )

        # Rate limit check
        allowed, rl_meta = rate_limiter.is_allowed(api_key, tier)
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
