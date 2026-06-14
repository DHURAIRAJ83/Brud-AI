"""
Device Heartbeat
----------------
Periodically sends heartbeat to the VPS to stay online.
"""

import asyncio
import logging
import httpx

from config import get_settings
from utils.system_info import get_system_info
from actions.registry import action_registry

logger = logging.getLogger(__name__)
settings = get_settings()

class HeartbeatManager:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = settings.vps_url
        self.headers = {"X-API-Key": self.api_key}
        self.interval = settings.heartbeat_interval_seconds

    async def _send_heartbeat(self):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/api/devices/heartbeat",
                    headers=self.headers,
                    json={
                        "agent_version": settings.agent_version,
                        "system_info": get_system_info(),
                        "capabilities": action_registry.get_capabilities()
                    },
                    timeout=5.0
                )
                if resp.status_code != 200:
                    logger.debug(f"Heartbeat failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.debug(f"Heartbeat request error: {e}")

    async def run_loop(self):
        """Run the heartbeat loop."""
        logger.info(f"Starting heartbeat loop (interval: {self.interval}s)")
        while True:
            await self._send_heartbeat()
            await asyncio.sleep(self.interval)
