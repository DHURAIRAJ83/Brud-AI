"""
Memory System
-------------
Stores the last N conversation turns per session_id.
Optionally extracts and persists key user facts.

Design decisions:
- In-memory dict (fast, CPU-zero overhead)
- TTL-based expiry prevents unbounded growth
- Context formatted for Ollama prompt injection
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class Turn:
    role: str       # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


class SessionMemory:
    """Manages conversation history for a single session."""

    SESSION_TTL = 1800  # 30 minutes inactivity → expire

    def __init__(self, max_turns: int):
        self.max_turns = max_turns
        self._turns: deque[Turn] = deque(maxlen=max_turns * 2)  # store pairs
        self._facts: dict[str, str] = {}
        self.last_active = time.time()

    def add(self, role: str, content: str):
        self._turns.append(Turn(role=role, content=content))
        self.last_active = time.time()

    def build_context(self) -> str:
        """Format history for prompt injection."""
        lines = []
        for turn in self._turns:
            prefix = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{prefix}: {turn.content}")
        return "\n".join(lines)

    def add_fact(self, key: str, value: str):
        self._facts[key] = value

    def get_facts_str(self) -> str:
        if not self._facts:
            return ""
        return "Known facts: " + "; ".join(f"{k}={v}" for k, v in self._facts.items())

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > self.SESSION_TTL

    def clear(self):
        self._turns.clear()
        self._facts.clear()


class MemorySystem:
    """Global registry of per-session memories."""

    def __init__(self):
        self._sessions: dict[str, SessionMemory] = {}
        self._max_turns = settings.memory_max_turns

    def _get_or_create(self, session_id: str) -> SessionMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(self._max_turns)
            logger.debug("New session: %s", session_id)
        return self._sessions[session_id]

    def add_turn(self, session_id: str, role: str, content: str):
        mem = self._get_or_create(session_id)
        mem.add(role, content)

    def get_context(self, session_id: str) -> str:
        if session_id not in self._sessions:
            return ""
        return self._sessions[session_id].build_context()

    def get_facts(self, session_id: str) -> str:
        if session_id not in self._sessions:
            return ""
        return self._sessions[session_id].get_facts_str()

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id].clear()

    def purge_expired(self):
        """Remove sessions that have been inactive beyond TTL."""
        expired = [sid for sid, mem in self._sessions.items() if mem.is_expired()]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info("Purged %d expired sessions", len(expired))

    def session_count(self) -> int:
        return len(self._sessions)


# Singleton
memory_system = MemorySystem()
