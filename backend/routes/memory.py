"""
Memory Routes — TASK 3 Persistent Memory System
================================================
REST API endpoints for per-user memory management.

Endpoints:
  GET    /api/memory/{user_id}               — list all memories
  POST   /api/memory/{user_id}               — manually save a fact
  DELETE /api/memory/{user_id}/{fact_id}     — delete one fact
  DELETE /api/memory/{user_id}               — delete all facts for user
  GET    /api/memory/{user_id}/search?q=...  — keyword search
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from ai.memory_store import memory_store, VALID_CATEGORIES, CATEGORY_USER_FACT

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class SaveMemoryRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=100, description="Memory key / label")
    value: str = Field(..., min_length=1, max_length=2000, description="Memory value")
    category: str = Field(
        default=CATEGORY_USER_FACT,
        description="user_fact | preference | long_term_context",
    )
    tags: Optional[list[str]] = Field(default=None, description="Optional tags")


class MemoryResponse(BaseModel):
    id: int
    category: str
    key: str
    value: str
    source: str
    confidence: float
    created_at: float
    updated_at: float
    tags: list[str]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/memory/{user_id}", summary="List all memories for a user")
async def list_memories(
    user_id: str,
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """
    Return all stored memories for the given user_id.
    Optionally filter by category: user_fact | preference | long_term_context
    """
    cats = [category] if category and category in VALID_CATEGORIES else None
    facts = await memory_store.get_all_facts(user_id, cats)
    return {
        "user_id": user_id,
        "total": len(facts),
        "memories": facts,
    }


@router.post("/memory/{user_id}", summary="Manually save a memory fact")
async def save_memory(user_id: str, body: SaveMemoryRequest):
    """
    Manually store a fact, preference, or long-term context for the user.
    """
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}"
        )
    fact_id = await memory_store.save_fact(
        user_id=user_id,
        key=body.key,
        value=body.value,
        category=body.category,
        source="manual",
        confidence=1.0,
        tags=body.tags,
    )
    return {
        "message": "Memory saved.",
        "id": fact_id,
        "user_id": user_id,
        "category": body.category,
        "key": body.key,
        "value": body.value,
    }


@router.delete("/memory/{user_id}/{fact_id}", summary="Delete a specific memory fact")
async def delete_memory(user_id: str, fact_id: int):
    """Delete a single memory fact by its ID."""
    deleted = await memory_store.delete_fact(user_id, fact_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Memory fact {fact_id} not found for user {user_id}."
        )
    return {"message": f"Memory {fact_id} deleted.", "user_id": user_id}


@router.delete("/memory/{user_id}", summary="Delete ALL memories for a user")
async def delete_all_memories(user_id: str):
    """Wipe all stored memories for the given user."""
    count = await memory_store.delete_all_facts(user_id)
    return {"message": f"Deleted {count} memories.", "user_id": user_id, "deleted": count}


@router.get("/memory/{user_id}/search", summary="Search memories by keyword")
async def search_memories(
    user_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
):
    """
    Full-text search over stored memory keys and values for this user.
    Uses SQLite FTS5 with LIKE fallback.
    """
    results = await memory_store.search_memory(user_id, q)
    return {
        "user_id": user_id,
        "query": q,
        "total": len(results),
        "results": results,
    }
