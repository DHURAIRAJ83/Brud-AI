"""
Desktop Agent — Main Entry Point
--------------------------------
Connects to the VPS, registers the device, and starts polling for commands.
"""

import asyncio
import logging
import os
import httpx

from config import get_settings
from core.poller import CommandPoller
from core.executor import ActionExecutor
from core.reporter import Reporter
from core.heartbeat import HeartbeatManager
from utils.system_info import get_system_info, get_os_type

# Import actions to register them
import actions.app_control
import actions.file_manager
import actions.web_control
import actions.screen_capture
import actions.ocr_engine
import actions.vscode_integration
import actions.coding_agent
import actions.git_control
import actions.voice_actions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("agent")
settings = get_settings()

async def register_device() -> str:
    """Register the device with the VPS and return the API key."""
    if settings.api_key:
        logger.info("Using configured API key.")
        return settings.api_key

    logger.info("Registering device with VPS...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.vps_url}/api/devices/register",
                headers={"X-User-Id": settings.user_id},
                json={
                    "device_name": settings.device_name,
                    "device_type": settings.device_type,
                    "os_type": get_os_type(),
                    "agent_version": settings.agent_version,
                    "system_info": get_system_info(),
                    # Capabilities will be updated on first heartbeat
                    "capabilities": []
                },
                timeout=10.0
            )
            resp.raise_for_status()
            data = resp.json()
            api_key = data["api_key"]
            logger.info(f"Successfully registered device. API Key: {api_key[:8]}...")
            
            # Save API key to .env so we don't re-register next time
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            with open(env_path, "a") as f:
                f.write(f"\nAPI_KEY={api_key}\n")
                
            return api_key
    except Exception as e:
        logger.error(f"Failed to register device: {e}")
        raise

async def main():
    logger.info("Starting Tamil AI Desktop Agent...")
    
    # 1. Register or load API key
    api_key = await register_device()
    settings.api_key = api_key  # Sync setting for dynamic actions
    device_id = "" # In a real implementation we'd fetch this from the API key if needed, or save it during registration.
    
    # Let's get the device info to get the ID
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.vps_url}/api/devices/heartbeat",
                headers={"X-API-Key": api_key},
                json={
                    "agent_version": settings.agent_version,
                    "system_info": get_system_info(),
                    "capabilities": []
                }
            )
            if resp.status_code == 200:
                device_id = resp.json()["id"]
    except Exception:
        pass

    # 2. Initialize components
    poller = CommandPoller(api_key)
    reporter = Reporter(api_key, device_id)
    executor = ActionExecutor(reporter)
    heartbeat = HeartbeatManager(api_key)

    # Start Voice OS manager
    try:
        from voice.voice_manager import voice_manager
        voice_manager.start()
    except Exception as e:
        logger.warning("Could not start Voice OS: %s", e)

    # 3. Start heartbeat in background
    asyncio.create_task(heartbeat.run_loop())

    # 4. Main polling loop
    logger.info("Agent ready. Waiting for commands...")
    try:
        while True:
            try:
                commands = await poller.poll()
                for command in commands:
                    # Execute concurrently so we don't block polling
                    asyncio.create_task(executor.execute(command))
                    
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")
                
            await asyncio.sleep(settings.poll_interval_seconds)
    finally:
        try:
            from voice.voice_manager import voice_manager
            voice_manager.stop()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped.")
