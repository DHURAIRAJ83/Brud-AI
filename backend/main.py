"""
Tamil AI Assistant — FastAPI Backend v3
Phase 3: Voice STT · Streaming SSE · SQLite Persistent Memory
Phase 4: Hybrid AI Runtime (Local ↔ Cloud ↔ Hybrid auto-failover)
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes import chat, upload, admin, rag, agent, metrics, tamil, stream, voice, audio, memory, runtime as runtime_routes
from ai.sqlite_memory import sqlite_memory
from ai.memory_store import memory_store          # Task 3
from services.cache_service import cache_service
from services.observability import obs_service
from services.security import SecurityMiddleware
from services.runtime_manager import runtime_manager        # Phase 4

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("tamil_ai")


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Tamil AI Assistant v3 starting…")
    cache_service.init()
    await sqlite_memory.init()          # Phase 3: persistent memory
    await memory_store.init()           # Task 3: typed persistent memory
    await runtime_manager.startup()     # Phase 4: Hybrid Runtime
    logger.info("✅ All systems initialized (SQLite memory + Hybrid Runtime active)")
    yield
    logger.info("🛑 Shutting down…")
    await runtime_manager.shutdown()    # Phase 4: cancel retry loop
    cache_service.clear()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Tamil AI Assistant",
    description=(
        "CPU-friendly Tamil + English AI platform. "
        "Phase 3: Voice STT (Whisper), Streaming SSE, SQLite Memory. "
        "Phase 4: Hybrid AI Runtime — Local ↔ Cloud auto-failover."
    ),
    version="4.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Security Middleware ───────────────────────────────────────────────────────
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
app.include_router(chat.router,          prefix="/api", tags=["Chat"])
app.include_router(stream.router,        prefix="/api", tags=["Streaming"])      # Phase 3
app.include_router(voice.router,         prefix="/api", tags=["Voice STT"])      # Phase 3
app.include_router(audio.router,         prefix="/api", tags=["Audio"])          # Phase 3 Audio AI
app.include_router(memory.router,        prefix="/api", tags=["Memory"])         # Task 3
app.include_router(upload.router,        prefix="/api", tags=["Upload"])
app.include_router(rag.router,           prefix="/api", tags=["RAG"])
app.include_router(agent.router,         prefix="/api", tags=["Agent"])
app.include_router(tamil.router,         prefix="/api", tags=["Tamil Intelligence"])
app.include_router(metrics.router,       prefix="/api", tags=["Observability"])
app.include_router(runtime_routes.router, prefix="/api", tags=["Runtime"])       # Phase 4
app.include_router(admin.router,         prefix="/api/admin", tags=["Admin"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", summary="Health check")
async def health():
    session_count = await sqlite_memory.session_count()
    turn_count    = await sqlite_memory.turn_count()
    runtime_status = await runtime_manager.get_runtime()
    return {
        "status": "ok",
        "service": "Tamil AI Assistant",
        "version": "4.0.0",
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
