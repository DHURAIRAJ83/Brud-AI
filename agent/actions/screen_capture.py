"""
Screen Capture Actions
-----------------------
MSS-based screen capture module supporting full screenshots, 
foreground active window bounds, custom region crops, and multi-monitor grids.
"""

import logging
import os
import sys
import mss
from mss.tools import to_png
from datetime import datetime
from typing import Dict, Any

from actions.registry import action_registry

logger = logging.getLogger(__name__)

# Make sure screenshots folder exists
os.makedirs("screenshots", exist_ok=True)

def get_active_window_rect() -> dict:
    """Gets window bounding rect and title on Windows; fallbacks on other platforms."""
    if sys.platform == "win32":
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd)
                rect = win32gui.GetWindowRect(hwnd)
                return {
                    "title": title,
                    "left": rect[0],
                    "top": rect[1],
                    "width": max(0, rect[2] - rect[0]),
                    "height": max(0, rect[3] - rect[1]),
                }
        except Exception as e:
            logger.warning("Failed to get active window rect on Windows: %s", e)
    return {
        "title": "Primary Screen",
        "left": 0,
        "top": 0,
        "width": 1920,
        "height": 1080
    }

@action_registry.register("screen.capture")
async def capture_screen(params: Dict[str, Any]) -> dict:
    """Capture the full screen using mss."""
    try:
        filename = f"screenshots/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        with mss.mss() as sct:
            # grab monitor 0: combined unified monitors
            sct_img = sct.grab(sct.monitors[0])
            to_png(sct_img.rgb, sct_img.size, output=filename)
            
        logger.info("Captured full screenshot: %s", filename)
        return {
            "success": True,
            "tool": "screen.capture",
            "message": "Successfully captured full screen",
            "data": {
                "image_path": os.path.abspath(filename),
                "width": sct_img.size.width,
                "height": sct_img.size.height,
            }
        }
    except Exception as e:
        logger.error("Failed to capture screen: %s", e)
        return {
            "success": False,
            "tool": "screen.capture",
            "error": str(e)
        }

@action_registry.register("screen.active_window")
async def capture_active_window(params: Dict[str, Any]) -> dict:
    """Capture the active foreground window only."""
    try:
        filename = f"screenshots/active_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        rect = get_active_window_rect()
        
        with mss.mss() as sct:
            unified = sct.monitors[0]
            # Bind bounds
            left = max(unified["left"], rect["left"])
            top = max(unified["top"], rect["top"])
            width = min(unified["width"], rect["width"])
            height = min(unified["height"], rect["height"])
            
            if width > 0 and height > 0:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                sct_img = sct.grab(monitor)
                to_png(sct_img.rgb, sct_img.size, output=filename)
            else:
                sct_img = sct.grab(sct.monitors[1])
                to_png(sct_img.rgb, sct_img.size, output=filename)
                
        logger.info("Captured active window: %s", filename)
        return {
            "success": True,
            "tool": "screen.active_window",
            "message": f"Successfully captured active window: {rect['title']}",
            "data": {
                "image_path": os.path.abspath(filename),
                "title": rect["title"],
                "width": sct_img.size.width,
                "height": sct_img.size.height,
            }
        }
    except Exception as e:
        logger.error("Failed to capture active window: %s", e)
        return {
            "success": False,
            "tool": "screen.active_window",
            "error": str(e)
        }

@action_registry.register("screen.region_capture")
async def capture_region(params: Dict[str, Any]) -> dict:
    """Capture a specific region bounding box {x, y, w, h}."""
    try:
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))
        w = int(params.get("w", 100))
        h = int(params.get("h", 100))
        
        filename = f"screenshots/region_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        with mss.mss() as sct:
            monitor = {"left": x, "top": y, "width": w, "height": h}
            sct_img = sct.grab(monitor)
            to_png(sct_img.rgb, sct_img.size, output=filename)
            
        logger.info("Captured region {%d, %d, %d, %d}: %s", x, y, w, h, filename)
        return {
            "success": True,
            "tool": "screen.region_capture",
            "message": f"Successfully captured region at x={x}, y={y}",
            "data": {
                "image_path": os.path.abspath(filename),
                "x": x, "y": y, "w": w, "h": h,
                "width": sct_img.size.width,
                "height": sct_img.size.height,
            }
        }
    except Exception as e:
        logger.error("Failed to capture region: %s", e)
        return {
            "success": False,
            "tool": "screen.region_capture",
            "error": str(e)
        }

@action_registry.register("screen.multi_monitor_capture")
async def capture_multi_monitor(params: Dict[str, Any]) -> dict:
    """Capture screenshots for each active monitor separately."""
    try:
        results = []
        with mss.mss() as sct:
            for i, monitor in enumerate(sct.monitors[1:], start=1):
                filename = f"screenshots/monitor_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                sct_img = sct.grab(monitor)
                to_png(sct_img.rgb, sct_img.size, output=filename)
                results.append({
                    "monitor_index": i,
                    "image_path": os.path.abspath(filename),
                    "width": sct_img.size.width,
                    "height": sct_img.size.height,
                })
                
        logger.info("Captured %d monitors", len(results))
        return {
            "success": True,
            "tool": "screen.multi_monitor_capture",
            "message": f"Successfully captured {len(results)} monitor(s)",
            "data": {
                "monitors": results
            }
        }
    except Exception as e:
        logger.error("Failed multi monitor capture: %s", e)
        return {
            "success": False,
            "tool": "screen.multi_monitor_capture",
            "error": str(e)
        }
