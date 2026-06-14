"""
Tamil AI Assistant — FastAPI Backend v5
Phase 3: Voice STT · Streaming SSE · SQLite Persistent Memory
Phase 4: Hybrid AI Runtime (Local ↔ Cloud ↔ Hybrid auto-failover)
Phase 5: Multi-User Auth (JWT) · WebSocket Chat · Conversation History · Analytics v2
"""

import logging
import time
import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
settings = get_settings()

from routes import chat, upload, admin, rag, agent, metrics, tamil, stream, voice, audio, memory, runtime as runtime_routes, vision, vscode, voice_sessions as voice_sessions_routes
from routes import auth as auth_routes
from routes import conversations as conversations_routes
from routes import plugins as plugins_routes
from routes import finetune as finetune_routes
from routes import skills as skills_routes
from ai.sqlite_memory import sqlite_memory
from ai.memory_store import memory_store          # Task 3
from services.cache_service import cache_service
from services.observability import obs_service
from services.security import SecurityMiddleware
from services.runtime_manager import runtime_manager        # Phase 4
from models.base import db_manager                          # Desktop Agent DB
from models.user import UserModel                           # Default User
from services.validation import validate_environment, validate_db_writable

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_json_logging():
    json_formatter = JsonFormatter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(json_formatter)
    
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "tamil_ai"]:
        log = logging.getLogger(logger_name)
        for handler in log.handlers:
            handler.setFormatter(json_formatter)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("tamil_ai")

# ── Background Device Cleanup ─────────────────────────────────────────────────
device_cleanup_task = None

async def device_cleanup_loop():
    logger.info("Starting background device status monitor loop...")
    from services.device_service import device_service
    while True:
        try:
            await device_service.check_stale_devices()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in device status monitor background loop: %s", e)
        await asyncio.sleep(15)  # Run every 15 seconds


# ── Background Voice Session Cleanup ──────────────────────────────────────────
voice_cleanup_task = None

async def voice_cleanup_loop():
    logger.info("Starting background voice sessions cleanup loop...")
    while True:
        try:
            from models.voice_profile import VoiceAuthSessionModel, VoiceChallengeModel, VoiceReplayModel
            session_count = await VoiceAuthSessionModel.cleanup_expired(retention_days=7)
            challenge_count = await VoiceChallengeModel.cleanup_expired()
            replay_count = await VoiceReplayModel.cleanup_expired(hours=1)
            if session_count > 0 or challenge_count > 0 or replay_count > 0:
                logger.info(
                    "Purged expired voice authentication records: %d sessions, %d challenges, %d replay hashes",
                    session_count, challenge_count, replay_count
                )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in voice sessions cleanup background loop: %s", e)
        await asyncio.sleep(900)  # Run every 15 minutes (900 seconds)


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global device_cleanup_task, voice_cleanup_task
    if settings.log_format_json or settings.app_env == "production":
        setup_json_logging()

    logger.info("🚀 Tamil AI Assistant v3 starting…")
    
    # Run critical environment and dependency validation
    validate_environment()
    
    cache_service.init()
    await sqlite_memory.init()          # Phase 3: persistent memory
    await memory_store.init()           # Task 3: typed persistent memory
    await runtime_manager.startup()     # Phase 4: Hybrid Runtime
    await db_manager.init()             # Desktop Agent DB Initialization
    
    # Verify DB writable after DB init
    await validate_db_writable()
    
    await UserModel.ensure_default_user() # Create default user

    # Start background device cleanup
    device_cleanup_task = asyncio.create_task(device_cleanup_loop())
    # Start background voice sessions cleanup
    voice_cleanup_task = asyncio.create_task(voice_cleanup_loop())

    logger.info("✅ All systems initialized (SQLite memory + Hybrid Runtime + Device Monitor active)")
    yield
    logger.info("🛑 Shutting down…")

    # Cancel background device cleanup
    if device_cleanup_task:
        device_cleanup_task.cancel()
        try:
            await device_cleanup_task
        except asyncio.CancelledError:
            pass

    # Cancel background voice sessions cleanup
    if voice_cleanup_task:
        voice_cleanup_task.cancel()
        try:
            await voice_cleanup_task
        except asyncio.CancelledError:
            pass

    await runtime_manager.shutdown()    # Phase 4: cancel retry loop
    await db_manager.close()            # Desktop Agent DB close
    cache_service.clear()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Tamil AI Assistant",
    description=(
        "CPU-friendly Tamil + English AI platform. "
        "Phase 3: Voice STT (Whisper), Streaming SSE, SQLite Memory. "
        "Phase 4: Hybrid AI Runtime — Local ↔ Cloud auto-failover."
    ),
    version="5.0.0",
    lifespan=lifespan,
)

# Determine allowed origins
origins = []
if settings.app_env == "production":
    origins = ["https://rudran.ai", "https://chat.rudran.ai", "https://dashboard.rudran.ai"]
    if settings.cors_allowed_origins:
        for o in settings.cors_allowed_origins.split(","):
            val = o.strip()
            if val:
                origins.append(val)
else:
    origins = [
        "http://72.61.238.200",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://172.18.128.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://172.18.128.1:5173",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://172.18.128.1:3001",
    ]
    if settings.cors_allowed_origins:
        for o in settings.cors_allowed_origins.split(","):
            val = o.strip()
            if val:
                origins.append(val)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security Middleware ───────────────────────────────────────────────────────
# (Runs after CORSMiddleware since CORSMiddleware is registered first)
app.add_middleware(SecurityMiddleware)


# ── Request timing + observability middleware ─────────────────────────────────
@app.middleware("http")
async def observe_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{elapsed_ms:.1f}ms"
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_routes.router,         prefix="/api", tags=["Auth"])           # Phase 5
app.include_router(conversations_routes.router, prefix="/api", tags=["Conversations"]) # Phase 5
app.include_router(chat.router,          prefix="/api", tags=["Chat"])
app.include_router(stream.router,        prefix="/api", tags=["Streaming"])      # Phase 3
app.include_router(voice.router,         prefix="/api", tags=["Voice STT"])      # Phase 3
app.include_router(audio.router,         prefix="/api", tags=["Audio"])          # Phase 3 Audio AI
app.include_router(voice_sessions_routes.router, prefix="/api/voice", tags=["Voice Sessions"])
app.include_router(memory.router,        prefix="/api", tags=["Memory"])         # Task 3
app.include_router(upload.router,        prefix="/api", tags=["Upload"])
app.include_router(rag.router,           prefix="/api", tags=["RAG"])
app.include_router(agent.router,         prefix="/api", tags=["Agent"])
app.include_router(tamil.router,         prefix="/api", tags=["Tamil Intelligence"])
app.include_router(metrics.router,       prefix="/api", tags=["Observability"])
app.include_router(runtime_routes.router, prefix="/api", tags=["Runtime"])       # Phase 4
app.include_router(skills_routes.router,  prefix="/api/skills", tags=["Skills Marketplace"])
app.include_router(vision.router,        prefix="/api", tags=["Vision"])
app.include_router(vscode.router,        prefix="/api", tags=["VS Code Extension"])
from fastapi import Depends
from services.auth_service import require_admin, require_user

admin_deps = [Depends(require_admin)]
user_deps = [Depends(require_user)]

app.include_router(admin.router,         prefix="/api/v1/admin", tags=["Admin"], dependencies=admin_deps)
app.include_router(admin.router,         prefix="/api/admin", tags=["Admin legacy/frontend"], dependencies=admin_deps)
app.include_router(plugins_routes.router, prefix="/api/v1/admin/plugins", tags=["Plugins Admin"], dependencies=admin_deps)
app.include_router(plugins_routes.router, prefix="/api/admin/plugins", tags=["Plugins Legacy/Frontend"], dependencies=admin_deps)
app.include_router(finetune_routes.router, prefix="/api/v1/admin/finetune", tags=["Fine-tuning Admin"], dependencies=admin_deps)
app.include_router(finetune_routes.router, prefix="/api/admin/finetune", tags=["Fine-tuning Legacy/Frontend"], dependencies=admin_deps)

# ── Desktop Agent Routes ──────────────────────────────────────────────────────
from routes import devices, commands, audit
app.include_router(devices.router,       prefix="/api/v1/devices", tags=["Devices"], dependencies=user_deps)
app.include_router(commands.router,      prefix="/api/v1/commands", tags=["Commands"], dependencies=user_deps)
app.include_router(audit.router,         prefix="/api/v1/audit", tags=["Audit Logs"], dependencies=user_deps)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", summary="Health check")
async def health():
    session_count = await sqlite_memory.session_count()
    turn_count    = await sqlite_memory.turn_count()
    runtime_status = await runtime_manager.get_runtime()
    return {
        "status": "ok",
        "service": "Tamil AI Assistant",
        "version": "5.0.0",
        "features": [
            "multi-step-agent", "smart-model-routing",
            "tanglish-normalization", "rag",
            "sqlite-persistent-memory",          # Phase 3
            "streaming-sse",                     # Phase 3
            "voice-stt-whisper",                 # Phase 3
            "hybrid-ai-runtime",                 # Phase 4
            "auto-failover-local-cloud",          # Phase 4
            "plugin-system", "observability",
            "api-security", "monetization",
        ],
        "runtime": {
            "mode":            runtime_status["mode"],
            "active":          runtime_status["runtime"],
            "local_available": runtime_status["local_available"],
            "cloud_available": runtime_status["cloud_available"],
            "active_model":    runtime_status["active_model"],
        },
        "memory": {
            "backend": "sqlite",
            "sessions": session_count,
            "total_turns": turn_count,
        },
    }


@app.get("/", summary="Root")
async def root():
    return {
        "message": "Tamil AI Assistant v2 is running.",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/api/metrics",
    }


# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
