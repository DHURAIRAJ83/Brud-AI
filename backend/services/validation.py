"""
Startup Health & Environment Validation
----------------------------------------
Verifies system health, DB write access, and that all required packages
and security settings are present before launching the application.
"""

import logging
import datetime
from config import get_settings
from models.base import db_manager

logger = logging.getLogger(__name__)

def validate_environment():
    """Verify environment configuration and critical dependencies on startup."""
    settings = get_settings()
    logger.info("Running environment health check...")

    # 1. Check App Env & Security configuration
    if settings.app_env == "production":
        if not settings.secret_key:
            raise RuntimeError("SECRET_KEY is required in production environment.")
        if settings.secret_key == "tamil-ai-phase5-secret-change-in-production":
            raise RuntimeError("Default development SECRET_KEY cannot be used in production.")
        if not settings.security_enabled:
            raise RuntimeError("SECURITY_ENABLED cannot be False in production environment.")
        if not settings.admin_initial_password:
            raise RuntimeError("ADMIN_INITIAL_PASSWORD is required in production environment.")

    # 2. Check Critical Imports
    try:
        import langdetect
        logger.info("✓ langdetect imported successfully.")
    except ImportError as e:
        raise RuntimeError(f"Missing dependency 'langdetect'. Run pip install langdetect. Error: {e}")

    try:
        import sentence_transformers
        logger.info("✓ sentence_transformers imported successfully.")
    except ImportError as e:
        raise RuntimeError(f"Missing dependency 'sentence_transformers'. Error: {e}")

    try:
        import faiss
        logger.info("✓ faiss imported successfully.")
    except ImportError as e:
        raise RuntimeError(f"Missing dependency 'faiss'. Error: {e}")

async def validate_db_writable():
    """Verify the database is writable by running a probe transaction."""
    try:
        # Check write capability on default table
        await db_manager.execute(
            "CREATE TABLE IF NOT EXISTS startup_probe (id INTEGER PRIMARY KEY, ts TEXT)"
        )
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await db_manager.execute(
            "INSERT INTO startup_probe (ts) VALUES (?)", (now,)
        )
        await db_manager.execute("DROP TABLE startup_probe")
        logger.info("✓ Database writable validation passed.")
    except Exception as e:
        raise RuntimeError(f"Database writable check failed: {e}")
