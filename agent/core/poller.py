"""
Command Poller
--------------
Polls the VPS for pending commands.
"""

import asyncio
import logging
import httpx
from typing import List

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class CommandPoller:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = settings.vps_url
        self.headers = {"X-API-Key": self.api_key}

    async def poll(self) -> List[dict]:
        """Fetch pending commands from the server."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/api/commands/poll",
                    headers=self.headers,
                    params={"limit": 5},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    commands = resp.json()
                    if commands:
                        logger.info(f"Polled {len(commands)} pending commands")
                    return commands
                else:
                    logger.debug(f"Poll failed: {resp.status_code} {resp.text}")
        except httpx.RequestError as e:
            logger.debug(f"Poll request error: {e}")
        return []
