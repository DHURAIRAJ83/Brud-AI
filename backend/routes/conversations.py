"""
Conversations Route — Phase 5: /api/conversations/*
------------------------------------------------------
GET    /api/conversations                     → list sessions for a user
GET    /api/conversations/{session_id}         → full message history
DELETE /api/conversations/{session_id}         → delete a session
GET    /api/conversations/{session_id}/export  → export as JSON
GET    /api/conversations/search               → search messages by content
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ai.sqlite_memory import sqlite_memory
from services.auth_service import get_current_user

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_preview(turns: list[dict]) -> str:
    """Return first user message as session preview text."""
    for t in turns:
        if t.get("role") == "user":
            content = t.get("content", "")
            return content[:80] + ("…" if len(content) > 80 else "")
    return "(empty)"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/conversations", summary="List all conversation sessions")
async def list_conversations(
    limit: int = Query(50, ge=1, le=200),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Return all sessions with message count and preview."""
    sessions = await sqlite_memory.list_sessions(limit=limit)
    result = []
    for sid in sessions:
        turns = await sqlite_memory.get_turns(sid)
        result.append({
            "session_id": sid,
            "message_count": len(turns),
            "preview": _session_preview(turns),
            "started_at": turns[0].get("timestamp") if turns else None,
            "last_at":    turns[-1].get("timestamp") if turns else None,
        })
    # Sort newest-first
    result.sort(key=lambda x: x["last_at"] or "", reverse=True)
    return {"sessions": result, "total": len(result)}


@router.get("/conversations/search", summary="Search messages across all conversations")
async def search_conversations(
    q: str = Query(..., min_length=1),
    limit: int = Query(30, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Full-text search across all conversation messages."""
    matches = await sqlite_memory.search_turns(q, limit=limit)
    return {"query": q, "results": matches, "count": len(matches)}


@router.get("/conversations/{session_id}", summary="Get full conversation history")
async def get_conversation(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Return all turns for a specific session."""
    turns = await sqlite_memory.get_turns(session_id)
    if not turns:
        return {"session_id": session_id, "turns": [], "message_count": 0}
    return {
        "session_id": session_id,
        "turns": turns,
        "message_count": len(turns),
        "started_at": turns[0].get("timestamp"),
        "last_at": turns[-1].get("timestamp"),
        "preview": _session_preview(turns),
    }


@router.delete("/conversations/{session_id}", summary="Delete a conversation session")
async def delete_conversation(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Delete all turns for a session."""
    deleted = await sqlite_memory.delete_session(session_id)
    return {"message": f"Session {session_id} deleted.", "deleted_turns": deleted}


@router.get("/conversations/{session_id}/export", summary="Export conversation as JSON")
async def export_conversation(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Export conversation history as a downloadable JSON file."""
    turns = await sqlite_memory.get_turns(session_id)
    export_data = {
        "session_id": session_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "message_count": len(turns),
        "turns": turns,
    }
    content = json.dumps(export_data, ensure_ascii=False, indent=2)
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="conversation_{session_id[:8]}.json"'
        },
    )
