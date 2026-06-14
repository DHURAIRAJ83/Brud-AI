"""
Project Context Manager
-----------------------
Tracks the active workspace file, line, and symbol synchronized from VS Code.
Enforces context expiration (HR-02) and maps implicit query references.
"""

import time
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

IMPLICIT_REF_PATTERN = re.compile(
    r"\b(this|that|current|active)\s+(file|api|class|method|route|function|code|symbol|api|route|endpoint)\b",
    re.IGNORECASE
)

class ProjectContextManager:
    """Manages active file, cursor position, active symbol and expiration of the context."""
    
    def __init__(self):
        self.active_file: Optional[str] = None
        self.cursor_line: Optional[int] = None
        self.active_symbol: Optional[str] = None
        self.updated_at: float = 0.0

    def set_context(self, active_file: Optional[str], cursor_line: Optional[int], active_symbol: Optional[str]):
        """Updates the active workspace context and resets the expiration timer."""
        self.active_file = active_file
        self.cursor_line = cursor_line
        self.active_symbol = active_symbol
        self.updated_at = time.time()
        logger.info(
            "Updated workspace context: file=%s, symbol=%s, line=%s",
            active_file, active_symbol, cursor_line
        )

    def get_context(self) -> Dict[str, Any]:
        """Retrieves the active workspace context. Enforces the 300s expiration rule (HR-02)."""
        if self.updated_at > 0 and (time.time() - self.updated_at > 300):
            logger.info("Workspace context expired (older than 300 seconds). Invalidate/Clear context.")
            self.clear_context()
            
        return {
            "active_file": self.active_file,
            "cursor_line": self.cursor_line,
            "active_symbol": self.active_symbol,
            "updated_at": self.updated_at
        }

    def clear_context(self):
        """Manually clears the active workspace context."""
        self.active_file = None
        self.cursor_line = None
        self.active_symbol = None
        self.updated_at = 0.0

    def has_implicit_references(self, query: str) -> bool:
        """Checks if a user query contains implicit workspace references like 'this file' or 'that API'."""
        return bool(IMPLICIT_REF_PATTERN.search(query))

    def resolve_implicit_query(self, query: str) -> Dict[str, Any]:
        """
        If the query has implicit references, returns the current non-expired context.
        Otherwise, returns empty dict.
        """
        if not self.has_implicit_references(query):
            return {}
            
        ctx = self.get_context()
        if ctx["active_file"]:
            return ctx
        return {}


# Singleton instance
project_context_manager = ProjectContextManager()
