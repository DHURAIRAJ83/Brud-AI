"""
Browser Control Actions
-----------------------
Provides browser automation with URL security.
Allowed: http://, https://
Blocked: file://, javascript:, data:
"""

import webbrowser
import logging
from typing import Dict, Any
from urllib.parse import urlparse, quote_plus

from actions.registry import action_registry

logger = logging.getLogger(__name__)

def _is_safe_url(url: str) -> bool:
    """Validate URL scheme for security."""
    try:
        # Default to https if no scheme
        if not url.startswith(('http://', 'https://', 'file://', 'javascript:', 'data:')):
            url = f"https://{url}"
            
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")
    except Exception:
        return False

def _ensure_scheme(url: str) -> str:
    """Ensure URL has a valid scheme."""
    if not url.startswith(('http://', 'https://')):
        return f"https://{url}"
    return url

@action_registry.register("browser.open")
async def open_browser(params: Dict[str, Any]) -> dict:
    """Open a URL in the default browser."""
    try:
        url = params.get("url", "https://google.com")
        
        if not _is_safe_url(url):
            return {
                "success": False,
                "tool": "browser.open",
                "error": f"URL scheme not allowed. Only http/https are permitted: {url}"
            }
            
        safe_url = _ensure_scheme(url)
        
        # open_new_tab returns True if successful
        success = webbrowser.open_new_tab(safe_url)
        
        if success:
            return {
                "success": True,
                "tool": "browser.open",
                "message": f"Successfully opened {safe_url}",
                "data": {"url": safe_url}
            }
        else:
            return {
                "success": False,
                "tool": "browser.open",
                "error": "Failed to launch web browser"
            }
            
    except Exception as e:
        return {
            "success": False,
            "tool": "browser.open",
            "error": str(e)
        }

@action_registry.register("browser.search")
async def search_browser(params: Dict[str, Any]) -> dict:
    """Perform a web search in the default browser."""
    try:
        query = params.get("query", "")
        if not query:
            return {
                "success": False,
                "tool": "browser.search",
                "error": "Query parameter is required"
            }
            
        engine = params.get("engine", "google").lower()
        
        if engine == "youtube":
            url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        elif engine == "bing":
            url = f"https://www.bing.com/search?q={quote_plus(query)}"
        else: # default to google
            url = f"https://www.google.com/search?q={quote_plus(query)}"
            
        success = webbrowser.open_new_tab(url)
        
        if success:
            return {
                "success": True,
                "tool": "browser.search",
                "message": f"Successfully searched '{query}' on {engine}",
                "data": {"url": url, "query": query, "engine": engine}
            }
        else:
            return {
                "success": False,
                "tool": "browser.search",
                "error": "Failed to launch web browser"
            }
            
    except Exception as e:
        return {
            "success": False,
            "tool": "browser.search",
            "error": str(e)
        }
