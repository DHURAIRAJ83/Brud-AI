"""
System Information Utilities
----------------------------
Collects OS and hardware info for the agent heartbeat.
"""

import platform
import psutil

def get_system_info() -> dict:
    """Gather basic system and hardware info."""
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": psutil.cpu_count(logical=True),
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "python_version": platform.python_version()
    }

def get_os_type() -> str:
    """Return normalized OS type."""
    os_name = platform.system().lower()
    if os_name == "darwin":
        return "macos"
    return os_name
