"""
Action Registry
---------------
Maps tool names (e.g., "desktop.open_app") to handler functions.
"""

import logging
from typing import Callable, Coroutine, Any, Dict, Optional

logger = logging.getLogger(__name__)

class ActionRegistry:
    def __init__(self):
        self._handlers: Dict[str, Callable[[dict], Coroutine[Any, Any, dict]]] = {}
        self._capabilities = set()

    def register(self, tool_name: str):
        """Decorator to register an action handler."""
        def wrapper(func):
            self._handlers[tool_name] = func
            self._capabilities.add(tool_name)
            logger.info(f"Registered action handler: {tool_name}")
            return func
        return wrapper

    def get_handler(self, tool_name: str) -> Optional[Callable[[dict], Coroutine[Any, Any, dict]]]:
        return self._handlers.get(tool_name)

    def get_capabilities(self) -> list[str]:
        return list(self._capabilities)

action_registry = ActionRegistry()
