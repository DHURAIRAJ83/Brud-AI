"""
SQLite Persistent Memory — Phase 3
-------------------------------------
Replaces the in-memory dict with aiosqlite.
Sessions and conversation turns survive backend restarts.

Schema:
  sessions(session_id, created_at, last_active, facts_json)
  turns(id, session_id, role, content, timestamp)

Backwards compatible: same public API as MemorySystem.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import aiosqlite

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DB_PATH = Path(getattr(settings, "memory_db_path", "./memory.db"))
SESSION_TTL = 1800          # 30 min inactivity → expire
MAX_TURNS_IN_CONTEXT = 10   # Last N turn-pairs to include in prompt


class SQLiteMemory:
    """
    Async SQLite-backed conversation memory.

    Drop-in replacement for the old in-memory MemorySystem.
    All methods are async.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._initialized = False

    # ── Schema setup ──────────────────────────────────────────────────────────
    async def init(self):
        """Create tables if they don't exist. Call on app startup."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id  TEXT PRIMARY KEY,
                    created_at  REAL NOT NULL,
                    last_active REAL NOT NULL,
                    facts_json  TEXT DEFAULT '{}',
                    active_skill_id TEXT DEFAULT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    timestamp   REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, timestamp)"
            )
            await db.commit()
            
            # Migration check: if active_skill_id is not yet in sessions table
            try:
                await db.execute("ALTER TABLE sessions ADD COLUMN active_skill_id TEXT DEFAULT NULL")
                await db.commit()
                logger.info("✅ SQLite memory migration: added active_skill_id to sessions")
            except Exception:
                pass
                
        self._initialized = True
        logger.info("✅ SQLite memory initialized at %s", self.db_path)

    # ── Session management ─────────────────────────────────────────────────────
    async def _ensure_session(self, db, session_id: str):
        now = time.time()
        await db.execute("""
            INSERT OR IGNORE INTO sessions(session_id, created_at, last_active, facts_json)
            VALUES (?, ?, ?, '{}')
        """, (session_id, now, now))
        await db.execute(
            "UPDATE sessions SET last_active=? WHERE session_id=?",
            (now, session_id)
        )

    async def get_active_skill(self, session_id: str) -> Optional[str]:
        """Get the active skill ID for a session."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT active_skill_id FROM sessions WHERE session_id = ?",
                (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if row:
            return row[0]
        return None

    async def set_active_skill(self, session_id: str, skill_id: Optional[str]):
        """Set the active skill ID for a session."""
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_session(db, session_id)
            await db.execute(
                "UPDATE sessions SET active_skill_id = ? WHERE session_id = ?",
                (skill_id, session_id)
            )
            await db.commit()


    # ── Add a turn ────────────────────────────────────────────────────────────
    async def add_turn(self, session_id: str, role: str, content: str):
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_session(db, session_id)
            await db.execute(
                "INSERT INTO turns(session_id, role, content, timestamp) VALUES(?,?,?,?)",
                (session_id, role, content, time.time())
            )
            await db.commit()

    # ── Get context for prompt ────────────────────────────────────────────────
    async def get_context(self, session_id: str) -> str:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT role, content FROM turns
                WHERE session_id=?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, MAX_TURNS_IN_CONTEXT * 2)) as cursor:
                rows = await cursor.fetchall()

        if not rows:
            return ""
        lines = []
        for role, content in reversed(rows):
            prefix = "User" if role == "user" else "Assistant"
            lines.append(f"{prefix}: {content}")
        return "\n".join(lines)

    # ── Facts ────────────────────────────────────────────────────────────────
    async def get_facts(self, session_id: str) -> str:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT facts_json FROM sessions WHERE session_id=?",
                (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return ""
        facts = json.loads(row[0] or "{}")
        if not facts:
            return ""
        return "Known facts: " + "; ".join(f"{k}={v}" for k, v in facts.items())

    async def set_fact(self, session_id: str, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_session(db, session_id)
            async with db.execute(
                "SELECT facts_json FROM sessions WHERE session_id=?",
                (session_id,)
            ) as c:
                row = await c.fetchone()
            facts = json.loads(row[0] if row else "{}")
            facts[key] = value
            await db.execute(
                "UPDATE sessions SET facts_json=? WHERE session_id=?",
                (json.dumps(facts, ensure_ascii=False), session_id)
            )
            await db.commit()

    # ── Clear / purge ─────────────────────────────────────────────────────────
    async def clear_session(self, session_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM turns WHERE session_id=?", (session_id,))
            await db.execute(
                "UPDATE sessions SET facts_json='{}', last_active=? WHERE session_id=?",
                (time.time(), session_id)
            )
            await db.commit()
        logger.info("Cleared session: %s", session_id)

    async def purge_expired(self):
        cutoff = time.time() - SESSION_TTL
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT session_id FROM sessions WHERE last_active < ?", (cutoff,)
            ) as c:
                expired = [r[0] for r in await c.fetchall()]
            if expired:
                await db.execute(
                    f"DELETE FROM turns WHERE session_id IN ({','.join('?'*len(expired))})",
                    expired
                )
                await db.execute(
                    f"DELETE FROM sessions WHERE session_id IN ({','.join('?'*len(expired))})",
                    expired
                )
                await db.commit()
                logger.info("Purged %d expired sessions", len(expired))

    # ── Stats ────────────────────────────────────────────────────────────────
    async def session_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM sessions") as c:
                return (await c.fetchone())[0]

    async def turn_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM turns") as c:
                return (await c.fetchone())[0]

    async def get_all_sessions(self, limit: int = 50) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT s.session_id, s.created_at, s.last_active,
                       COUNT(t.id) as turn_count
                FROM sessions s
                LEFT JOIN turns t ON t.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.last_active DESC
                LIMIT ?
            """, (limit,)) as c:
                rows = await c.fetchall()
        return [
            {
                "session_id": r[0],
                "created_at": r[1],
                "last_active": r[2],
                "turn_count": r[3],
            }
            for r in rows
        ]

    # ── Phase 5: Conversation History API ────────────────────────────────────

    async def list_sessions(self, limit: int = 50) -> list[str]:
        """Return list of session IDs ordered by most recent activity."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT session_id FROM sessions ORDER BY last_active DESC LIMIT ?",
                (limit,),
            ) as c:
                rows = await c.fetchall()
        return [r[0] for r in rows]

    async def get_turns(self, session_id: str) -> list[dict]:
        """Return all turns for a session as list of dicts with ISO timestamps."""
        import datetime as _dt
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role, content, timestamp FROM turns WHERE session_id=? ORDER BY timestamp ASC",
                (session_id,),
            ) as c:
                rows = await c.fetchall()
        return [
            {
                "role": r[0],
                "content": r[1],
                "timestamp": _dt.datetime.fromtimestamp(r[2], tz=_dt.timezone.utc).isoformat(),
            }
            for r in rows
        ]

    async def delete_session(self, session_id: str) -> int:
        """Delete all turns and session record. Returns number of turns deleted."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM turns WHERE session_id=?", (session_id,)
            ) as c:
                count = (await c.fetchone())[0]
            await db.execute("DELETE FROM turns WHERE session_id=?", (session_id,))
            await db.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            await db.commit()
        logger.info("Deleted session %s (%d turns)", session_id, count)
        return count

    async def search_turns(self, query: str, limit: int = 30) -> list[dict]:
        """Full-text search across all turn content (case-insensitive LIKE)."""
        import datetime as _dt
        pattern = f"%{query}%"
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT session_id, role, content, timestamp
                   FROM turns
                   WHERE content LIKE ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (pattern, limit),
            ) as c:
                rows = await c.fetchall()
        return [
            {
                "session_id": r[0],
                "role": r[1],
                "content": r[2],
                "timestamp": _dt.datetime.fromtimestamp(r[3], tz=_dt.timezone.utc).isoformat(),
            }
            for r in rows
        ]


# Singleton
sqlite_memory = SQLiteMemory()
