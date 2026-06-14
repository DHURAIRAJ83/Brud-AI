"""
Result Reporter
---------------
Reports execution start and results back to the VPS.
"""

import logging
import httpx
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class Reporter:
    def __init__(self, api_key: str, device_id: str):
        self.api_key = api_key
        self.device_id = device_id
        self.base_url = settings.vps_url
        self.headers = {"X-API-Key": self.api_key}

    async def report_start(self, command_id: str) -> Optional[str]:
        """Report that execution has started. Returns execution_id."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/api/commands/execution/start",
                    headers=self.headers,
                    json={
                        "command_id": command_id,
                        "device_id": self.device_id
                    },
                    timeout=5.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["id"]
                else:
                    logger.error(f"Failed to report start: {resp.text}")
        except Exception as e:
            logger.error(f"Error reporting start: {e}")
        return None

    async def report_result(self, execution_id: str, status: str, result: dict, error: str = None, duration_ms: float = 0.0):
        """Report execution result."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/api/commands/execution/result",
                    headers=self.headers,
                    json={
                        "execution_id": execution_id,
                        "status": status,
                        "result": result,
                        "error_message": error,
                        "duration_ms": duration_ms
                    },
                    timeout=5.0
                )
                if resp.status_code != 200:
                    logger.error(f"Failed to report result: {resp.text}")
        except Exception as e:
            logger.error(f"Error reporting result: {e}")
