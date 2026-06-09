"""
Admin Route — system management endpoints
"""

import asyncio
from fastapi import APIRouter

from ai.rag_engine import rag_engine
from ai.sqlite_memory import sqlite_memory
from ai.ollama_client import ollama_client
from ai.memory_store import memory_store          # Task 3
from services.cache_service import cache_service
from services.upload_service import upload_service
from services.runtime_manager import runtime_manager  # Phase 4

router = APIRouter()


@router.get("/status", summary="System status overview")
async def system_status():
    """Full system health check for admin panel."""
    ollama_alive = await ollama_client.is_alive()
    try:
        models = await ollama_client.list_models() if ollama_alive else []
    except Exception:
        models = []

    return {
        "ollama": {"alive": ollama_alive, "models": models},
        "rag": rag_engine.stats(),
        "memory": {"active_sessions": await sqlite_memory.session_count()},
        "cache": cache_service.stats(),
        "files": upload_service.list_files(),
    }


@router.post("/retrain", summary="Re-ingest all uploaded files into RAG")
async def retrain():
    """Reset the RAG index and re-index all uploaded files."""
    rag_engine.reset()
    files = upload_service.list_files()
    loop = asyncio.get_event_loop()
    total = 0
    for f in files:
        count = await loop.run_in_executor(None, rag_engine.ingest_file, f["path"])
        total += count
    return {
        "message": f"Retrained on {len(files)} files, {total} total chunks.",
        "stats": rag_engine.stats(),
    }


@router.post("/clear-memory", summary="Clear all session memories")
async def clear_memory():
    await sqlite_memory.purge_expired()
    count = await sqlite_memory.session_count()
    return {"message": "Expired sessions purged.", "active": count}


@router.post("/clear-cache", summary="Clear LLM response cache")
async def clear_cache():
    cache_service.clear()
    return {"message": "Cache cleared."}


# ── Memory Admin Endpoints (Task 3) ───────────────────────────────────────────

@router.get("/memories", summary="View all memories across all users")
async def list_all_memories(limit: int = 200):
    """Admin: fetch all stored memory facts across every user."""
    memories = await memory_store.get_all_users_memories(limit=limit)
    stats = await memory_store.memory_stats()
    return {
        "stats": stats,
        "memories": memories,
    }


@router.delete("/memories/{user_id}", summary="Delete all memories for a user")
async def delete_user_memories(user_id: str):
    """Admin: wipe every memory fact stored for a specific user."""
    count = await memory_store.delete_all_facts(user_id)
    return {"message": f"Deleted {count} memories for user '{user_id}'.", "deleted": count}


@router.delete("/memories", summary="Purge ALL memories (danger!)")
async def purge_all_memories():
    """Admin: delete every memory fact in the database."""
    count = await memory_store.purge_all()
    return {"message": f"Purged all {count} memories.", "deleted": count}


@router.get("/memory-stats", summary="Memory system statistics")
async def memory_stats():
    """Admin: get total memory count, unique users, breakdown by category."""
    stats = await memory_store.memory_stats()
    session_count = await sqlite_memory.session_count()
    return {
        "memory_store": stats,
        "conversation_sessions": session_count,
    }


# ── Runtime Admin Endpoints (Phase 4) ─────────────────────────────────────────

@router.get("/runtime", summary="Runtime dashboard — full system status")
async def runtime_dashboard():
    """
    Admin: full Hybrid AI Runtime status for the dashboard.
    Returns mode, active runtime, model, failover count, and more.
    """
    rt = await runtime_manager.get_runtime()
    models = await runtime_manager.list_models()
    ollama_alive = rt["local_available"]
    try:
        local_models = await ollama_client.list_models() if ollama_alive else []
    except Exception:
        local_models = rt["local_models"]

    return {
        "runtime": {
            "mode":            rt["mode"],
            "active":          rt["runtime"],
            "local_available": rt["local_available"],
            "cloud_available": rt["cloud_available"],
            "active_model":    rt["active_model"],
            "failover_count":  rt["failover_count"],
        },
        "models": {
            "local": models["local"] or local_models,
            "cloud": models["cloud"],
        },
        "cache":  cache_service.stats(),
        "memory": {"active_sessions": await sqlite_memory.session_count()},
    }
