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


# ── Dashboard & Device Metrics (Phase D) ──────────────────────────────────────

from pydantic import BaseModel
from models.base import db_manager

class DashboardMetricsResponse(BaseModel):
    total_commands: int
    failed_commands: int
    success_rate_percent: float
    avg_execution_time_ms: float
    online_devices: int
    offline_devices: int
    pending_commands: int
    commands_today: int
    most_used_tool: str
    last_active_device: str

@router.get("/dashboard/metrics", summary="Dashboard metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics():
    """Admin: Get system metrics for the dashboard UI."""
    # Executions stats
    exec_stats = await db_manager.fetch_one(
        """SELECT 
            COUNT(*) as total_exec,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_exec,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed_exec,
            AVG(duration_ms) as avg_duration
           FROM executions"""
    )
    
    total = exec_stats["total_exec"] if exec_stats and exec_stats["total_exec"] else 0
    failed = exec_stats["failed_exec"] if exec_stats and exec_stats["failed_exec"] else 0
    success = exec_stats["success_exec"] if exec_stats and exec_stats["success_exec"] else 0
    avg_time = exec_stats["avg_duration"] if exec_stats and exec_stats["avg_duration"] else 0.0
    
    success_rate = (success / total * 100) if total > 0 else 0.0
    
    # Commands stats
    cmd_stats = await db_manager.fetch_one(
        "SELECT COUNT(*) as pending FROM commands WHERE status = 'pending'"
    )
    pending = cmd_stats["pending"] if cmd_stats else 0
    
    # Device stats
    device_stats = await db_manager.fetch_one(
        """SELECT 
            SUM(CASE WHEN status = 'online' AND datetime(last_heartbeat, '+60 seconds') >= datetime('now') THEN 1 ELSE 0 END) as online_count,
            SUM(CASE WHEN status != 'online' OR datetime(last_heartbeat, '+60 seconds') < datetime('now') OR last_heartbeat IS NULL THEN 1 ELSE 0 END) as offline_count
           FROM devices"""
    )
    
    online = device_stats["online_count"] if device_stats and device_stats["online_count"] else 0
    offline = device_stats["offline_count"] if device_stats and device_stats["offline_count"] else 0
    
    today_stats = await db_manager.fetch_one(
        "SELECT COUNT(*) as today FROM commands WHERE date(created_at) = date('now')"
    )
    commands_today = today_stats["today"] if today_stats else 0
    
    tool_stats = await db_manager.fetch_one(
        "SELECT tool FROM commands GROUP BY tool ORDER BY COUNT(*) DESC LIMIT 1"
    )
    most_used = tool_stats["tool"] if tool_stats and tool_stats["tool"] else "None"
    
    device_act = await db_manager.fetch_one(
        "SELECT device_name FROM devices WHERE last_heartbeat IS NOT NULL ORDER BY last_heartbeat DESC LIMIT 1"
    )
    last_active = device_act["device_name"] if device_act and device_act["device_name"] else "None"

    return DashboardMetricsResponse(
        total_commands=total,
        failed_commands=failed,
        success_rate_percent=round(success_rate, 2),
        avg_execution_time_ms=round(avg_time, 2),
        online_devices=online,
        offline_devices=offline,
        pending_commands=pending,
        commands_today=commands_today,
        most_used_tool=most_used,
        last_active_device=last_active
    )

import psutil
import time

BOOT_TIME = time.time() - (86400 * 5) # mock 5 days uptime fallback

def get_disk_usage_percent() -> float:
    for path in ['.', '/', 'C:\\']:
        try:
            return psutil.disk_usage(path).percent
        except Exception:
            continue
    return 0.0

def get_cpu_percent() -> float:
    try:
        return psutil.cpu_percent(interval=None) or 0.0
    except Exception:
        return 0.0

def get_ram_percent() -> float:
    try:
        return psutil.virtual_memory().percent
    except Exception:
        return 0.0

def get_uptime_seconds() -> int:
    try:
        return int(time.time() - psutil.boot_time())
    except Exception:
        return int(time.time() - BOOT_TIME)

@router.get("/system/health", summary="System Health Metrics")
async def get_system_health():
    """Admin: Get queue and VPS health metrics."""
    # Queue Health
    q_stats = await db_manager.fetch_one(
        """SELECT 
            SUM(CASE WHEN status = 'pending' OR status = 'approved' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
           FROM commands"""
    )
    
    # Queue Analytics: Wait and Execution times
    wait_stats = await db_manager.fetch_one(
        """SELECT 
            AVG((julianday(executed_at) - julianday(created_at)) * 86400) as avg_wait_s
           FROM commands 
           WHERE executed_at IS NOT NULL 
             AND created_at >= datetime('now', '-24 hours')"""
    )
    avg_wait = wait_stats["avg_wait_s"] if wait_stats and wait_stats["avg_wait_s"] is not None else 0.0

    exec_stats = await db_manager.fetch_one(
        """SELECT 
            AVG((julianday(completed_at) - julianday(executed_at)) * 86400) as avg_exec_s
           FROM commands 
           WHERE completed_at IS NOT NULL 
             AND executed_at IS NOT NULL
             AND created_at >= datetime('now', '-24 hours')"""
    )
    avg_exec = exec_stats["avg_exec_s"] if exec_stats and exec_stats["avg_exec_s"] is not None else 0.0

    # Failure Tracing
    failures = await db_manager.fetch_all(
        """SELECT c.id, c.tool, c.raw_input, e.error_message, e.completed_at
           FROM commands c
           JOIN executions e ON c.id = e.command_id
           WHERE e.status = 'error' OR c.status = 'failed'
           ORDER BY e.completed_at DESC
           LIMIT 5"""
    )
    failure_list = [
        {
            "command_id": f["id"],
            "tool": f["tool"],
            "input": f["raw_input"],
            "error": f["error_message"] or "Unknown error",
            "time": f["completed_at"]
        }
        for f in failures
    ]

    return {
        "queue": {
            "pending": q_stats["pending"] if q_stats and q_stats["pending"] else 0,
            "failed": q_stats["failed"] if q_stats and q_stats["failed"] else 0,
            "completed": q_stats["completed"] if q_stats and q_stats["completed"] else 0,
            "avg_wait_seconds": round(avg_wait, 1),
            "avg_execution_seconds": round(avg_exec, 1),
            "recent_failures": failure_list
        },
        "vps": {
            "cpu_percent": get_cpu_percent(),
            "ram_percent": get_ram_percent(),
            "disk_percent": get_disk_usage_percent(),
            "uptime_seconds": get_uptime_seconds()
        }
    }
