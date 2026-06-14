"""
App Control Actions
-------------------
Actions for opening and closing applications.
"""

import os
import subprocess
import logging
from typing import Dict, Any

from actions.registry import action_registry
from utils.system_info import get_os_type

logger = logging.getLogger(__name__)

# Basic app paths/commands for Windows
WINDOWS_APPS = {
    "vscode": "code",
    "chrome": "start chrome",
    "notepad": "notepad",
    "explorer": "explorer",
    "calculator": "calc",
}

@action_registry.register("desktop.open_app")
async def open_app(params: Dict[str, Any]) -> dict:
    """Open an application."""
    app_name = params.get("app", "").lower()
    if not app_name:
        raise ValueError("App name is required")

    os_type = get_os_type()
    
    if os_type == "windows":
        cmd = WINDOWS_APPS.get(app_name, app_name)
        try:
            # shell=True is often needed for 'start' commands on Windows
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {
                "success": True,
                "tool": "desktop.open_app",
                "message": f"Successfully opened {app_name}",
                "data": {"app": app_name, "command": cmd}
            }
        except Exception as e:
            return {
                "success": False,
                "tool": "desktop.open_app",
                "error": f"Failed to start {app_name}: {e}"
            }
            
    else:
        return {
            "success": False,
            "tool": "desktop.open_app",
            "error": f"open_app not implemented for OS: {os_type}"
        }

@action_registry.register("desktop.close_app")
async def close_app(params: Dict[str, Any]) -> dict:
    """Close an application."""
    app_name = params.get("app", "").lower()
    if not app_name:
        raise ValueError("App name is required")

    os_type = get_os_type()
    
    if os_type == "windows":
        try:
            # Simple forceful kill by process name for now
            # In a robust implementation, use psutil to find and politely terminate
            process_name = f"{app_name}.exe"
            subprocess.run(["taskkill", "/F", "/IM", process_name], check=True, capture_output=True)
            return {
                "success": True,
                "tool": "desktop.close_app",
                "message": f"Successfully closed {app_name}",
                "data": {"app": app_name}
            }
        except subprocess.CalledProcessError:
            return {
                "success": False,
                "tool": "desktop.close_app",
                "error": f"Could not close {app_name}. Is it running?"
            }
            
    else:
        return {
            "success": False,
            "tool": "desktop.close_app",
            "error": f"close_app not implemented for OS: {os_type}"
        }
