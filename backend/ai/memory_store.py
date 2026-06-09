"""
memory_store.py — Persistent Memory System (TASK 3)
=====================================================
Typed, SQLite-backed memory store with:
  - Three memory categories: user_fact | preference | long_term_context
  - Full CRUD: save_fact, retrieve_facts, delete_fact, search_memory
  - Auto-extraction from user messages (regex patterns)
  - Prompt injection helper

Schema (memories table):
  id, user_id, category, key, value, source, confidence,
  created_at, updated_at, tags
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import aiosqlite

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DB_PATH = Path(getattr(settings, "memory_db_path", "./memory.db"))

# ── Memory categories ──────────────────────────────────────────────────────────
CATEGORY_USER_FACT       = "user_fact"         # "My name is …"
CATEGORY_PREFERENCE      = "preference"        # "Reply in Tamil"
CATEGORY_LONG_TERM       = "long_term_context" # general long-term facts

VALID_CATEGORIES = {CATEGORY_USER_FACT, CATEGORY_PREFERENCE, CATEGORY_LONG_TERM}

# ── Regex extraction patterns ──────────────────────────────────────────────────
# Each tuple: (category, key, regex_pattern, group_index)
EXTRACTION_PATTERNS: list[tuple[str, str, str, int]] = [
    # Name
    (CATEGORY_USER_FACT, "name",
     r"(?:my name is|i am|call me|என் பெயர்|நான்)\s+([A-Za-z஀-௿]+(?:\s+[A-Za-z஀-௿]+)?)",
     1),
    # Age
    (CATEGORY_USER_FACT, "age",
     r"(?:i am|i'm|my age is|வயது)\s+(\d{1,3})\s*(?:years?|வயது)?",
     1),
    # Occupation / job
    (CATEGORY_USER_FACT, "occupation",
     r"(?:i(?:'m| am)(?: a)?|i work as(?: a)?|என்(?:னுடைய)? தொழில்)\s+([A-Za-z஀-௿\s]+?)(?:\.|,|$)",
     1),
    # Location / city
    (CATEGORY_USER_FACT, "location",
     r"(?:i live in|i am from|i'm from|என் ஊர்|வசிக்கிறேன்)\s+([A-Za-z஀-௿\s,]+?)(?:\.|,|$)",
     1),

    # Language preference
    (CATEGORY_PREFERENCE, "reply_language",
     r"(?:reply|respond|answer|பதில்|பேசு|சொல்)\s+(?:in|to)?\s*(tamil|english|tanglish|தமிழ்|ஆங்கிலம்)",
     1),
    # Formality preference
    (CATEGORY_PREFERENCE, "formality",
     r"(?:be|use|keep it|வை)\s+(formal|informal|casual|friendly|professional)",
     1),
    # Response length preference
    (CATEGORY_PREFERENCE, "response_length",
     r"(?:give me|keep|use|make it)\s+(short|brief|long|detailed|concise)\s+(?:answers?|responses?|replies?)?",
     1),

    # Long-term context — interests
    (CATEGORY_LONG_TERM, "interest",
     r"(?:i (?:like|love|enjoy|am interested in)|என(?:க்)?(?: பிடிக்கும்| விரும்புகிறேன்))\s+([A-Za-z஀-௿\s]+?)(?:\.|,|$)",
     1),
    # Long-term context — goals
    (CATEGORY_LONG_TERM, "goal",
     r"(?:i want to|i'm trying to|my goal is|என் இலக்கு)\s+([A-Za-z஀-௿\s]+?)(?:\.|,|$)",
     1),
]


class MemoryStore:
    """
    Persistent typed memory store backed by SQLite.

    Usage:
        await memory_store.init()                   # on startup
        await memory_store.extract_and_save(uid, msg)  # per user message
        facts_str = await memory_store.retrieve_facts(uid)  # for prompt
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    # ── Schema ─────────────────────────────────────────────────────────────────
    async def init(self):
        """Create the memories table and FTS index if not present."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     TEXT    NOT NULL,
                    category    TEXT    NOT NULL DEFAULT 'user_fact',
                    key         TEXT    NOT NULL,
                    value       TEXT    NOT NULL,
                    source      TEXT    NOT NULL DEFAULT 'auto_extracted',
                    confidence  REAL    NOT NULL DEFAULT 1.0,
                    created_at  REAL    NOT NULL,
                    updated_at  REAL    NOT NULL,
                    tags        TEXT    NOT NULL DEFAULT '[]'
                )
            """)
            # Composite index for fast per-user lookups
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_user ON memories(user_id, category)"
            )
            # FTS5 virtual table for full-text search
            await db.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    user_id,
                    key,
                    value,
                    content='memories',
                    content_rowid='id'
                )
            """)
            # Triggers to keep FTS in sync
            await db.execute("""
                CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, user_id, key, value)
                    VALUES (new.id, new.user_id, new.key, new.value);
                END
            """)
            await db.execute("""
                CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, user_id, key, value)
                    VALUES('delete', old.id, old.user_id, old.key, old.value);
                END
            """)
            await db.execute("""
                CREATE TRIGGER IF NOT EXISTS mem_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, user_id, key, value)
                    VALUES('delete', old.id, old.user_id, old.key, old.value);
                    INSERT INTO memories_fts(rowid, user_id, key, value)
                    VALUES (new.id, new.user_id, new.key, new.value);
                END
            """)
            await db.commit()
        logger.info("✅ MemoryStore initialized at %s", self.db_path)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def save_fact(
        self,
        user_id: str,
        key: str,
        value: str,
        category: str = CATEGORY_USER_FACT,
        source: str = "manual",
        confidence: float = 1.0,
        tags: Optional[list[str]] = None,
    ) -> int:
        """
        Upsert a memory fact. If a fact with the same user_id+category+key
        already exists it is updated, otherwise a new row is inserted.
        Returns the row id.
        """
        if category not in VALID_CATEGORIES:
            category = CATEGORY_USER_FACT
        now = time.time()
        tags_json = json.dumps(tags or [], ensure_ascii=False)

        async with aiosqlite.connect(self.db_path) as db:
            # Check for existing
            async with db.execute(
                "SELECT id FROM memories WHERE user_id=? AND category=? AND key=?",
                (user_id, category, key),
            ) as cur:
                row = await cur.fetchone()

            if row:
                fact_id = row[0]
                await db.execute(
                    "UPDATE memories SET value=?, source=?, confidence=?, updated_at=?, tags=? "
                    "WHERE id=?",
                    (value, source, confidence, now, tags_json, fact_id),
                )
            else:
                async with db.execute(
                    "INSERT INTO memories(user_id, category, key, value, source, confidence, "
                    "created_at, updated_at, tags) VALUES(?,?,?,?,?,?,?,?,?)",
                    (user_id, category, key, value, source, confidence, now, now, tags_json),
                ) as cur:
                    fact_id = cur.lastrowid

            await db.commit()

        logger.debug("Memory saved: [%s] %s/%s=%s (id=%s)", user_id, category, key, value, fact_id)
        return fact_id

    async def retrieve_facts(
        self,
        user_id: str,
        categories: Optional[list[str]] = None,
    ) -> str:
        """
        Retrieve all stored facts for a user and format them for prompt injection.
        Returns a formatted multi-line string or empty string if no facts.
        """
        cats = categories or list(VALID_CATEGORIES)
        placeholders = ",".join("?" * len(cats))

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f"SELECT category, key, value FROM memories "
                f"WHERE user_id=? AND category IN ({placeholders}) "
                f"ORDER BY category, key",
                (user_id, *cats),
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            return ""

        sections: dict[str, list[str]] = {
            CATEGORY_USER_FACT: [],
            CATEGORY_PREFERENCE: [],
            CATEGORY_LONG_TERM: [],
        }
        for category, key, value in rows:
            if category in sections:
                sections[category].append(f"  • {key}: {value}")

        parts = []
        if sections[CATEGORY_USER_FACT]:
            parts.append("User Facts:\n" + "\n".join(sections[CATEGORY_USER_FACT]))
        if sections[CATEGORY_PREFERENCE]:
            parts.append("User Preferences:\n" + "\n".join(sections[CATEGORY_PREFERENCE]))
        if sections[CATEGORY_LONG_TERM]:
            parts.append("Long-term Context:\n" + "\n".join(sections[CATEGORY_LONG_TERM]))

        return "\n\n".join(parts)

    async def get_all_facts(
        self, user_id: str, categories: Optional[list[str]] = None
    ) -> list[dict]:
        """Return raw list of fact dicts for a user (used by API)."""
        cats = categories or list(VALID_CATEGORIES)
        placeholders = ",".join("?" * len(cats))
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f"SELECT id, category, key, value, source, confidence, created_at, updated_at, tags "
                f"FROM memories WHERE user_id=? AND category IN ({placeholders}) "
                f"ORDER BY updated_at DESC",
                (user_id, *cats),
            ) as cur:
                rows = await cur.fetchall()
        return [
            {
                "id": r[0], "category": r[1], "key": r[2], "value": r[3],
                "source": r[4], "confidence": r[5],
                "created_at": r[6], "updated_at": r[7],
                "tags": json.loads(r[8] or "[]"),
            }
            for r in rows
        ]

    async def delete_fact(self, user_id: str, fact_id: int) -> bool:
        """Delete a specific fact. Returns True if a row was deleted."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "DELETE FROM memories WHERE id=? AND user_id=?", (fact_id, user_id)
            ) as cur:
                deleted = cur.rowcount > 0
            await db.commit()
        return deleted

    async def delete_all_facts(self, user_id: str) -> int:
        """Delete all memories for a user. Returns count deleted."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "DELETE FROM memories WHERE user_id=?", (user_id,)
            ) as cur:
                count = cur.rowcount
            await db.commit()
        logger.info("Deleted %d memories for user %s", count, user_id)
        return count

    async def search_memory(self, user_id: str, query: str) -> list[dict]:
        """
        Full-text search over key+value for a specific user.
        Falls back to LIKE search if FTS fails.
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # FTS5 MATCH search
                async with db.execute(
                    """
                    SELECT m.id, m.category, m.key, m.value, m.source, m.confidence,
                           m.created_at, m.updated_at, m.tags
                    FROM memories m
                    JOIN memories_fts fts ON fts.rowid = m.id
                    WHERE fts.user_id = ? AND memories_fts MATCH ?
                    ORDER BY rank
                    LIMIT 20
                    """,
                    (user_id, query),
                ) as cur:
                    rows = await cur.fetchall()
        except Exception:
            # FTS fallback: simple LIKE
            like = f"%{query}%"
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT id, category, key, value, source, confidence, created_at, updated_at, tags "
                    "FROM memories WHERE user_id=? AND (key LIKE ? OR value LIKE ?)",
                    (user_id, like, like),
                ) as cur:
                    rows = await cur.fetchall()

        return [
            {
                "id": r[0], "category": r[1], "key": r[2], "value": r[3],
                "source": r[4], "confidence": r[5],
                "created_at": r[6], "updated_at": r[7],
                "tags": json.loads(r[8] or "[]"),
            }
            for r in rows
        ]

    # ── Auto-extraction ────────────────────────────────────────────────────────

    async def extract_and_save(self, user_id: str, message: str) -> list[dict]:
        """
        Scan a user message for extractable facts using regex patterns.
        Saves any discovered facts and returns list of saved items.
        """
        saved = []
        msg_lower = message.lower().strip()

        for (category, key, pattern, group_idx) in EXTRACTION_PATTERNS:
            try:
                match = re.search(pattern, msg_lower, re.IGNORECASE | re.UNICODE)
                if match:
                    value = match.group(group_idx).strip().rstrip(".,;")
                    if len(value) >= 2:  # Skip single-char noise
                        fact_id = await self.save_fact(
                            user_id=user_id,
                            key=key,
                            value=value,
                            category=category,
                            source="auto_extracted",
                            confidence=0.85,
                        )
                        saved.append({"id": fact_id, "category": category, "key": key, "value": value})
                        logger.info("Auto-extracted [%s]: %s=%s", category, key, value)
            except Exception as exc:
                logger.debug("Extraction error for pattern %s: %s", key, exc)

        return saved

    # ── Admin helpers ──────────────────────────────────────────────────────────

    async def get_all_users_memories(self, limit: int = 200) -> list[dict]:
        """Admin: fetch all memories across all users."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id, user_id, category, key, value, source, confidence, "
                "created_at, updated_at, tags "
                "FROM memories ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ) as cur:
                rows = await cur.fetchall()
        return [
            {
                "id": r[0], "user_id": r[1], "category": r[2], "key": r[3],
                "value": r[4], "source": r[5], "confidence": r[6],
                "created_at": r[7], "updated_at": r[8],
                "tags": json.loads(r[9] or "[]"),
            }
            for r in rows
        ]

    async def memory_stats(self) -> dict:
        """Admin: total memories, breakdown by category."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM memories") as cur:
                total = (await cur.fetchone())[0]
            async with db.execute(
                "SELECT category, COUNT(*) FROM memories GROUP BY category"
            ) as cur:
                by_category = dict(await cur.fetchall())
            async with db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM memories"
            ) as cur:
                unique_users = (await cur.fetchone())[0]
        return {
            "total": total,
            "unique_users": unique_users,
            "by_category": by_category,
        }

    async def purge_all(self) -> int:
        """Admin: delete ALL memories."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("DELETE FROM memories") as cur:
                count = cur.rowcount
            await db.commit()
        logger.warning("🗑️  Purged ALL %d memories", count)
        return count


# Singleton
memory_store = MemoryStore()
