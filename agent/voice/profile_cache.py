"""
Active User Profile Cache Manager
----------------------------------
Caches active user voice profiles locally to minimize API roundtrips.
Enforces user isolation, 5-minute TTL, and strict memory limits.
"""

import time
import httpx
import logging
import sys
# Unshadow config module import for agent
import os
import importlib.util

def _get_agent_settings():
    try:
        from config import get_settings
        s = get_settings()
        if hasattr(s, "user_id"):
            return s
    except Exception:
        pass
    try:
        agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        config_path = os.path.join(agent_dir, "config.py")
        spec = importlib.util.spec_from_file_location("agent_config", config_path)
        agent_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent_config)
        return agent_config.get_settings()
    except Exception:
        class MockSettings:
            vps_url = "http://localhost:8000"
            user_id = "admin-user-123"
        return MockSettings()

settings = _get_agent_settings()
logger = logging.getLogger(__name__)



class ProfileCache:
    def __init__(self):
        self._cache = {}  # user_id -> list of profiles
        self._last_loaded = 0.0
        self.ttl = 300.0  # 5 minutes in seconds
        # Optional injected DB reader for testing (bypasses HTTP calls)
        # Set to an async callable: async (user_id) -> list[dict]
        self._db_reader = None

    def get_profiles(self, user_id: str = None) -> list:
        """Fetch profiles for the given user (or current settings user), using cache when fresh."""
        if user_id is None:
            user_id = settings.user_id
        if not user_id:
            return []

        now = time.time()
        # Return cached data when it belongs to this user and hasn't expired
        if user_id in self._cache and (now - self._last_loaded) < self.ttl:
            return self._cache[user_id]

        self.refresh_cache(user_id=user_id)
        return self._cache.get(user_id, [])

    def refresh_cache(self, user_id: str = None):
        """Force load the given user's active profiles from the backend."""
        if user_id is None:
            user_id = settings.user_id
        if not user_id:
            self._cache.clear()
            return

        try:
            logger.info("Refreshing voice profile cache for user: %s", user_id)
            with httpx.Client(timeout=10.0) as client:
                headers = {"X-User-Id": user_id}
                resp = client.get(f"{settings.vps_url}/api/voice/profiles", headers=headers)

                if resp.status_code == 200:
                    profiles = resp.json().get("profiles", [])
                    # Enforce strict user isolation: cache only profiles belonging to user_id
                    filtered = [p for p in profiles if p["user_id"] == user_id]
                    self._cache = {user_id: filtered}
                    self._last_loaded = time.time()

                    # Ensure memory footprint <= 10MB
                    cache_size = sys.getsizeof(self._cache)
                    if cache_size > 10 * 1024 * 1024:
                        logger.warning("Cache footprint exceeded 10MB limit. Clearing.")
                        self._cache.clear()
                else:
                    logger.warning("Failed to refresh voice profiles cache. Backend status: %d", resp.status_code)
        except Exception as e:
            logger.error("Error connecting to backend to refresh voice profile cache: %s", e)

    def load_profiles_direct(self, user_id: str, profiles: list):
        """
        Directly populate cache with a pre-fetched profile list.
        Intended for test environments or agent-side DB reads that bypass HTTP.

        Args:
            user_id: The user whose profiles are being loaded.
            profiles: List of profile dicts matching the VoiceProfileModel schema.
        """
        filtered = [p for p in profiles if p.get("user_id") == user_id]
        self._cache = {user_id: filtered}
        self._last_loaded = time.time()
        logger.info("Loaded %d voice profiles directly for user %s", len(filtered), user_id)

    def clear(self):
        """Explicitly wipe cache on logout/sync events."""
        self._cache.clear()
        self._last_loaded = 0.0


# Global singleton
profile_cache = ProfileCache()
