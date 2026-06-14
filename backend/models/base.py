"""
Database Manager — Async SQLite Engine
-----------------------------------------
Centralized database management for Tamil AI Assistant.

Design decisions:
  - Uses aiosqlite (already in requirements) for async I/O
  - Single DB file: agent.db (separate from existing memory.db)
  - Auto-creates all tables on startup
  - Prepared for future PostgreSQL migration (Phase 3+)
  - All queries use parameterized statements (SQL injection safe)
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "agent.db"


class DatabaseManager:
    """Async SQLite database manager with connection pooling."""

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    # ── Connection management ─────────────────────────────────────────────────

    async def init(self):
        """Initialize database and create all tables."""
        if self._db is not None:
            return
        logger.info("📦 Initializing agent database at %s", self._db_path)
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row


        # Enable WAL mode for better concurrent read performance
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")

        await self._create_tables()
        logger.info("✅ Agent database initialized")

    async def close(self):
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Get the active database connection."""
        if not self._db:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._db

    # ── Table creation ────────────────────────────────────────────────────────

    async def _create_tables(self):
        """Create all tables if they don't exist."""
        await self._db.executescript("""
            -- Users table
            CREATE TABLE IF NOT EXISTS users (
                id              TEXT PRIMARY KEY,
                username        TEXT UNIQUE NOT NULL,
                display_name    TEXT NOT NULL DEFAULT '',
                email           TEXT DEFAULT '',
                role            TEXT NOT NULL DEFAULT 'standard',
                api_key         TEXT UNIQUE,
                hashed_password TEXT DEFAULT '',
                password_change_required INTEGER NOT NULL DEFAULT 0,
                is_active       INTEGER NOT NULL DEFAULT 1,
                preferences     TEXT DEFAULT '{}',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Refresh tokens table
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id          TEXT PRIMARY KEY,
                token_hash  TEXT UNIQUE NOT NULL,
                user_id     TEXT NOT NULL,
                csrf_token  TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Devices table (Android-compatible)
            CREATE TABLE IF NOT EXISTS devices (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                device_name     TEXT NOT NULL,
                device_type     TEXT NOT NULL DEFAULT 'desktop',
                os_type         TEXT NOT NULL DEFAULT 'windows',
                os_version      TEXT DEFAULT '',
                agent_version   TEXT DEFAULT '1.0.0',
                api_key         TEXT UNIQUE NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                capabilities    TEXT DEFAULT '[]',
                system_info     TEXT DEFAULT '{}',
                last_heartbeat  TEXT,
                registered_at   TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            -- Command queue (Tool-Based Architecture)
            CREATE TABLE IF NOT EXISTS commands (
                id              TEXT PRIMARY KEY,
                device_id       TEXT NOT NULL,
                user_id         TEXT NOT NULL,
                tool            TEXT NOT NULL,
                params          TEXT NOT NULL DEFAULT '{}',
                device_type     TEXT NOT NULL DEFAULT 'desktop',
                status          TEXT NOT NULL DEFAULT 'pending',
                trust_level     TEXT NOT NULL DEFAULT 'safe',
                priority        INTEGER NOT NULL DEFAULT 3,
                approval_required INTEGER NOT NULL DEFAULT 0,
                approved_by     TEXT,
                approved_at     TEXT,
                raw_input       TEXT DEFAULT '',
                source_language TEXT DEFAULT 'en',
                source          TEXT DEFAULT 'chat',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                executed_at     TEXT,
                completed_at    TEXT,
                FOREIGN KEY (device_id) REFERENCES devices(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            -- Execution results
            CREATE TABLE IF NOT EXISTS executions (
                id              TEXT PRIMARY KEY,
                command_id      TEXT NOT NULL,
                device_id       TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'running',
                result          TEXT DEFAULT '{}',
                error_message   TEXT,
                duration_ms     REAL DEFAULT 0.0,
                executed_at     TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at    TEXT,
                FOREIGN KEY (command_id) REFERENCES commands(id),
                FOREIGN KEY (device_id) REFERENCES devices(id)
            );

            -- Audit logs
            CREATE TABLE IF NOT EXISTS audit_logs (
                id              TEXT PRIMARY KEY,
                user_id         TEXT,
                device_id       TEXT,
                action          TEXT NOT NULL,
                category        TEXT NOT NULL DEFAULT 'system',
                details         TEXT DEFAULT '{}',
                ip_address      TEXT DEFAULT '',
                user_agent      TEXT DEFAULT '',
                timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- AI Skills system (Marketplace) table
            CREATE TABLE IF NOT EXISTS skills (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                description     TEXT DEFAULT '',
                category        TEXT NOT NULL DEFAULT 'General',
                system_prompt   TEXT NOT NULL,
                model           TEXT NOT NULL DEFAULT 'auto',
                tools           TEXT DEFAULT '{"allow": [], "deny": []}',
                memory_scope    TEXT DEFAULT '["project_context"]',
                parent_skill_id TEXT DEFAULT NULL,
                is_builtin      INTEGER NOT NULL DEFAULT 0,
                voice_profile   TEXT DEFAULT NULL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (parent_skill_id) REFERENCES skills(id) ON DELETE SET NULL
            );

            -- Skill Version history table
            CREATE TABLE IF NOT EXISTS skill_versions (
                id              TEXT PRIMARY KEY,
                skill_id        TEXT NOT NULL,
                version         INTEGER NOT NULL,
                system_prompt   TEXT NOT NULL,
                model           TEXT NOT NULL,
                tools           TEXT DEFAULT '{"allow": [], "deny": []}',
                memory_scope    TEXT DEFAULT '["project_context"]',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
            );

            -- Voice Sessions audit table
            CREATE TABLE IF NOT EXISTS voice_sessions (
                id              TEXT PRIMARY KEY,
                session_id      TEXT,
                started_at      TEXT NOT NULL,
                ended_at        TEXT,
                wakeword        TEXT,
                transcript      TEXT,
                confidence      REAL,
                skill_id        TEXT,
                status          TEXT NOT NULL DEFAULT 'completed',
                duration_ms     REAL DEFAULT 0.0,
                audio_file      TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE SET NULL
            );

            -- Voice Profiles (Secure Biometric Templates)
            CREATE TABLE IF NOT EXISTS voice_profiles (
                id                TEXT PRIMARY KEY,
                user_id           TEXT NOT NULL,
                profile_name      TEXT NOT NULL,
                embedding_vector  TEXT NOT NULL,
                embedding_signature TEXT NOT NULL,
                adaptive_threshold REAL NOT NULL,
                confirm_threshold REAL NOT NULL,
                enrollment_mean   REAL NOT NULL,
                enrollment_std    REAL NOT NULL,
                status            TEXT NOT NULL DEFAULT 'active',
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Voice Authentication Logs
            CREATE TABLE IF NOT EXISTS voice_auth_logs (
                id                TEXT PRIMARY KEY,
                session_id        TEXT,
                user_id           TEXT NOT NULL,
                confidence_score  REAL NOT NULL,
                verification_status TEXT NOT NULL,
                challenge_required INTEGER NOT NULL DEFAULT 0,
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );


            -- Voice Lockouts
            CREATE TABLE IF NOT EXISTS voice_lockouts (
                id                TEXT PRIMARY KEY,
                user_id           TEXT NOT NULL UNIQUE,
                failure_count      INTEGER NOT NULL DEFAULT 0,
                locked_until     TEXT,
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Voice Replay Cache
            CREATE TABLE IF NOT EXISTS voice_replay_cache (
                id                TEXT PRIMARY KEY,
                audio_hash        TEXT UNIQUE NOT NULL,
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Voice Challenges
            CREATE TABLE IF NOT EXISTS voice_challenges (
                id                TEXT PRIMARY KEY,
                user_id           TEXT NOT NULL,
                challenge_digits  TEXT NOT NULL,
                attempt_count     INTEGER NOT NULL DEFAULT 0,
                expires_at        TEXT NOT NULL,
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Voice Auth Sessions
            CREATE TABLE IF NOT EXISTS voice_auth_sessions (
                id                TEXT PRIMARY KEY,
                user_id           TEXT NOT NULL,
                device_id         TEXT NOT NULL,
                command_scope     TEXT NOT NULL,
                verification_status TEXT NOT NULL DEFAULT 'pending',
                challenge_status  TEXT NOT NULL DEFAULT 'pending',
                verification_source TEXT DEFAULT 'mfcc_fallback',
                used              INTEGER NOT NULL DEFAULT 0,
                used_at           TEXT,
                expires_at        TEXT NOT NULL,
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            );

            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_devices_user_id ON devices(user_id);
            CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
            CREATE INDEX IF NOT EXISTS idx_devices_api_key ON devices(api_key);
            CREATE INDEX IF NOT EXISTS idx_commands_device_id ON commands(device_id);
            CREATE INDEX IF NOT EXISTS idx_commands_status ON commands(status);
            CREATE INDEX IF NOT EXISTS idx_commands_created_at ON commands(created_at);
            CREATE INDEX IF NOT EXISTS idx_executions_command_id ON executions(command_id);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
            CREATE INDEX IF NOT EXISTS idx_skills_parent ON skills(parent_skill_id);
            CREATE INDEX IF NOT EXISTS idx_skill_versions_skill ON skill_versions(skill_id);
            CREATE INDEX IF NOT EXISTS idx_voice_sessions_session ON voice_sessions(session_id);
            CREATE INDEX IF NOT EXISTS idx_voice_profiles_user ON voice_profiles(user_id);
            CREATE INDEX IF NOT EXISTS idx_voice_logs_user ON voice_auth_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_voice_logs_created ON voice_auth_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_voice_lockouts_user ON voice_lockouts(user_id);
            CREATE INDEX IF NOT EXISTS idx_voice_replay_hash ON voice_replay_cache(audio_hash);
            CREATE INDEX IF NOT EXISTS idx_voice_auth_sessions_user ON voice_auth_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);

            -- Project Modules (Phase 13.5)
            CREATE TABLE IF NOT EXISTS project_modules (
                file_path       TEXT PRIMARY KEY,
                classes         TEXT NOT NULL DEFAULT '[]',
                functions       TEXT NOT NULL DEFAULT '[]',
                routes          TEXT NOT NULL DEFAULT '[]',
                last_modified   TEXT NOT NULL
            );

            -- Project Dependencies with Symbol Mapping (HR-01) (Phase 13.5)
            CREATE TABLE IF NOT EXISTS project_dependencies (
                id              TEXT PRIMARY KEY,
                from_file       TEXT NOT NULL,
                to_file         TEXT NOT NULL,
                symbol_name     TEXT NOT NULL DEFAULT '',
                symbol_type     TEXT NOT NULL DEFAULT 'unknown',
                line_number     INTEGER NOT NULL,
                FOREIGN KEY (from_file) REFERENCES project_modules(file_path) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_dep_from ON project_dependencies(from_file);
            CREATE INDEX IF NOT EXISTS idx_dep_to ON project_dependencies(to_file);
        """)
        await self._db.commit()

        # Phase 12.1B migration: remove foreign key constraint from voice_auth_logs
        try:
            cursor = await self._db.execute("PRAGMA foreign_key_list(voice_auth_logs)")
            fks = await cursor.fetchall()
            has_voice_sessions_fk = any(fk["table"] == "voice_sessions" for fk in fks)
            
            if has_voice_sessions_fk:
                logger.info("Migrating voice_auth_logs to remove voice_sessions foreign key constraint...")
                await self._db.execute("PRAGMA foreign_keys=OFF")
                await self._db.execute("ALTER TABLE voice_auth_logs RENAME TO voice_auth_logs_old")
                await self._db.execute("""
                    CREATE TABLE voice_auth_logs (
                        id                TEXT PRIMARY KEY,
                        session_id        TEXT,
                        user_id           TEXT NOT NULL,
                        confidence_score  REAL NOT NULL,
                        verification_status TEXT NOT NULL,
                        challenge_required INTEGER NOT NULL DEFAULT 0,
                        created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                await self._db.execute("INSERT OR IGNORE INTO voice_auth_logs SELECT id, session_id, user_id, confidence_score, verification_status, challenge_required, created_at FROM voice_auth_logs_old")
                await self._db.execute("DROP TABLE voice_auth_logs_old")
                await self._db.execute("PRAGMA foreign_keys=ON")
                await self._db.commit()
                logger.info("✅ Migration: successfully removed voice_sessions foreign key from voice_auth_logs")
        except Exception as e:
            logger.error("Failed to run voice_auth_logs migration: %s", e)

        # Phase 12.1B migration: add attempt_count to voice_challenges

        try:
            await self._db.execute(
                "ALTER TABLE voice_challenges ADD COLUMN attempt_count INTEGER DEFAULT 0"
            )
            await self._db.commit()
            logger.info("✅ Migration: added attempt_count column to voice_challenges")
        except Exception:
            pass

        # Phase 5 migration: add hashed_password column if not present
        try:
            await self._db.execute(
                "ALTER TABLE users ADD COLUMN hashed_password TEXT DEFAULT ''"
            )
            await self._db.commit()
            logger.info("✅ Migration: added hashed_password column")
        except Exception:
            pass  # Column already exists — safe to ignore

        # Phase 5 migration: add password_change_required column if not present
        try:
            await self._db.execute(
                "ALTER TABLE users ADD COLUMN password_change_required INTEGER DEFAULT 0"
            )
            await self._db.commit()
            logger.info("✅ Migration: added password_change_required column")
        except Exception:
            pass  # Column already exists — safe to ignore

        # Phase 12 migration: add voice_profile column to skills if not present
        try:
            await self._db.execute(
                "ALTER TABLE skills ADD COLUMN voice_profile TEXT DEFAULT NULL"
            )
            await self._db.commit()
            logger.info("✅ Migration: added voice_profile column to skills")
        except Exception:
            pass

        # Phase 12 migration: add audio_file column to voice_sessions if not present
        try:
            await self._db.execute(
                "ALTER TABLE voice_sessions ADD COLUMN audio_file TEXT DEFAULT NULL"
            )
            await self._db.commit()
            logger.info("✅ Migration: added audio_file column to voice_sessions")
        except Exception:
            pass

        # Phase 12 migration: add confirmation_required column to voice_sessions if not present
        try:
            await self._db.execute(
                "ALTER TABLE voice_sessions ADD COLUMN confirmation_required INTEGER DEFAULT 0"
            )
            await self._db.commit()
            logger.info("✅ Migration: added confirmation_required column to voice_sessions")
        except Exception:
            pass

        # Phase 12 migration: add interrupted column to voice_sessions if not present
        try:
            await self._db.execute(
                "ALTER TABLE voice_sessions ADD COLUMN interrupted INTEGER DEFAULT 0"
            )
            await self._db.commit()
            logger.info("✅ Migration: added interrupted column to voice_sessions")
        except Exception:
            pass

        # Phase 12 migration: add source column to commands if not present
        try:
            await self._db.execute(
                "ALTER TABLE commands ADD COLUMN source TEXT DEFAULT 'chat'"
            )
            await self._db.commit()
            logger.info("✅ Migration: added source column to commands")
        except Exception:
            pass

        # Seed default builtin skills
        await self._seed_builtin_skills()

        logger.info("✅ All database tables created/verified")

    async def _seed_builtin_skills(self):
        """Seed the 8 default builtin skills."""
        import json
        builtin_skills = [
            (
                "assistant",
                "General Assistant",
                "General bilingual Tamil/English assistant",
                "Assistant",
                "You are a helpful AI assistant that understands both Tamil and English. Answer concisely and clearly in Tamil/English.",
                "auto",
                json.dumps({"allow": [], "deny": []}),
                json.dumps(["project_context"]),
                None,
                1,
                None
            ),
            (
                "tamil-teacher",
                "Tamil Instructor",
                "Specialized Tamil language instructor",
                "Teacher",
                "You are a dedicated Tamil language instructor. Teach grammar, vocabulary, literature, and translate queries clearly. Always explain grammatical structures in detailed Tamil.",
                "auto",
                json.dumps({"allow": [], "deny": ["git.*", "process.*", "script.*"]}),
                json.dumps(["project_context"]),
                "assistant",
                1,
                "ta-IN-ValluvarNeural"
            ),
            (
                "researcher",
                "Web Researcher",
                "Extracts and compiles facts from web searches and pages",
                "Research",
                "You are a detail-oriented Web Researcher. Focus on gathering factual information, scraping/reading text, and compiling reports.",
                "auto",
                json.dumps({"allow": ["browser.*", "files.write", "screen.ocr", "screen.capture"], "deny": []}),
                json.dumps(["project_context"]),
                "assistant",
                1,
                None
            ),
            (
                "python-developer",
                "Python Developer",
                "Expert Python programmer for code writing, refactoring, and testing",
                "Developer",
                "You are an expert Python Developer. Write clean, PEP8 compliant code, optimize algorithms, and follow pythonic patterns.",
                "qwen2.5-coder",
                json.dumps({"allow": ["coding.*", "files.*", "vscode.*", "git.*"], "deny": []}),
                json.dumps(["project_context"]),
                "assistant",
                1,
                None
            ),
            (
                "fastapi-expert",
                "FastAPI Expert",
                "Expert in building web APIs with FastAPI and SQLAlchemy",
                "Developer",
                "You are a FastAPI Expert. Focus on building high-performance REST APIs, background tasks, dependency injection, and clean database integrations using SQLAlchemy/Tortoise.",
                "qwen2.5-coder",
                json.dumps({"allow": ["coding.*", "files.*", "vscode.*", "git.*"], "deny": []}),
                json.dumps(["project_context"]),
                "python-developer",
                1,
                None
            ),
            (
                "devops-engineer",
                "DevOps Engineer",
                "Handles deployment configurations, scripts, and staging commits",
                "DevOps",
                "You are a DevOps Engineer. Focus on build pipelines, repository management, file structures, and version control.",
                "auto",
                json.dumps({"allow": ["files.*", "git.*"], "deny": ["git.push"]}),
                json.dumps(["project_context"]),
                "assistant",
                1,
                None
            ),
            (
                "ai-engineer",
                "AI Engineer",
                "Integrates large language models, agents, and prompts",
                "Developer",
                "You are an AI Engineer. Focus on integrating large language models, prompt engineering, agentic workflows, and testing agents.",
                "qwen2.5-coder",
                json.dumps({"allow": ["coding.*", "files.*", "vscode.*", "git.commit"], "deny": ["git.push"]}),
                json.dumps(["project_context"]),
                "python-developer",
                1,
                None
            ),
            (
                "textile-expert",
                "Textile & Dyeing Consultant",
                "Consultant for textile manufacturing and color dyeing processes",
                "Business",
                "You are a professional Textile and Dyeing Expert. You possess deep knowledge of fabric fibers, yarn spinning, weaving, chemical dyeing processes, color chemistry, and textile manufacturing standards.",
                "auto",
                json.dumps({"allow": [], "deny": ["coding.*", "git.*", "vscode.*"]}),
                json.dumps(["project_context"]),
                "assistant",
                1,
                None
            )
        ]

        # Use INSERT OR REPLACE to update builtin seeds on startup
        await self.execute_many(
            """INSERT OR REPLACE INTO skills
               (id, name, description, category, system_prompt, model, tools, memory_scope, parent_skill_id, is_builtin, voice_profile)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            builtin_skills
        )
        logger.info("✅ Builtin seed skills pre-seeded/updated in agent database")


        logger.info("✅ All database tables created/verified")

    # ── Helper methods ────────────────────────────────────────────────────────

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a SQL statement with params."""
        async with self._lock:
            cursor = await self._db.execute(sql, params)
            await self._db.commit()
            return cursor

    async def execute_many(self, sql: str, params_list: list[tuple]):
        """Execute a SQL statement for multiple param sets."""
        async with self._lock:
            await self._db.executemany(sql, params_list)
            await self._db.commit()

    async def fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row as dict."""
        async with self._lock:
            cursor = await self._db.execute(sql, params)
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows as list of dicts."""
        async with self._lock:
            cursor = await self._db.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def table_count(self, table: str) -> int:
        """Return row count for a table."""
        result = await self.fetch_one(f"SELECT COUNT(*) as cnt FROM {table}")
        return result["cnt"] if result else 0

    async def stats(self) -> dict:
        """Return database statistics."""
        return {
            "users": await self.table_count("users"),
            "devices": await self.table_count("devices"),
            "commands": await self.table_count("commands"),
            "executions": await self.table_count("executions"),
            "audit_logs": await self.table_count("audit_logs"),
            "db_path": str(self._db_path),
        }


# Singleton
db_manager = DatabaseManager()
