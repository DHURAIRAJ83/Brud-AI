"""
Model Fine-Tuning and Curation Routes
-------------------------------------
GET  /api/v1/admin/finetune/sessions → list all user sessions with turn counts
POST /api/v1/admin/finetune/curate   → compile/curate instruct dataset (Alpaca/ShareGPT)
POST /api/v1/admin/finetune/create-model → compile Modelfile & trigger ollama create
"""

import re
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.sqlite_memory import sqlite_memory
from ai.ollama_client import ollama_client

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CurateRequest(BaseModel):
    session_ids: List[str] = Field(..., min_length=1)
    format: str = Field("alpaca", description="alpaca or sharegpt")
    censor_words: Optional[List[str]] = None


class CreateModelRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    base_model: str = Field(..., min_length=2)
    system_prompt: str = Field(..., min_length=1)
    temperature: Optional[float] = 0.7


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_preview(turns: list[dict]) -> str:
    """Return first user message as session preview text."""
    for t in turns:
        if t.get("role") == "user":
            content = t.get("content", "")
            return content[:80] + ("…" if len(content) > 80 else "")
    return "(empty)"


def _censor_text(text: str, censor_list: Optional[List[str]]) -> str:
    if not censor_list or not text:
        return text
    for word in censor_list:
        if not word.strip():
            continue
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        text = pattern.sub("[CENSORED]", text)
    return text


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/sessions", summary="Get sessions for dataset curation")
async def list_finetune_sessions():
    """List all stored user conversations with their turn counts and preview."""
    sessions = await sqlite_memory.list_sessions(limit=100)
    result = []
    for sid in sessions:
        turns = await sqlite_memory.get_turns(sid)
        result.append({
            "session_id": sid,
            "message_count": len(turns),
            "preview": _session_preview(turns),
            "started_at": turns[0].get("timestamp") if turns else None,
        })
    return {"sessions": result}


@router.post("/curate", summary="Export selected sessions to training dataset")
async def curate_dataset(body: CurateRequest):
    """
    Compile conversation turns from specified session IDs into a training format.
    Supports Alpaca instruct dataset format or ShareGPT conversation format.
    """
    fmt = body.format.lower()
    if fmt not in ("alpaca", "sharegpt"):
        raise HTTPException(status_code=400, detail="Format must be either 'alpaca' or 'sharegpt'.")

    curated = []
    total_turns_processed = 0

    for sid in body.session_ids:
        turns = await sqlite_memory.get_turns(sid)
        if not turns:
            continue

        total_turns_processed += len(turns)

        # Apply censoring to turns
        censored_turns = []
        for t in turns:
            censored_turns.append({
                "role": t.get("role"),
                "content": _censor_text(t.get("content", ""), body.censor_words)
            })

        if fmt == "alpaca":
            # Group consecutive user-assistant pairs
            for i in range(len(censored_turns) - 1):
                if censored_turns[i]["role"] == "user" and censored_turns[i + 1]["role"] == "assistant":
                    curated.append({
                        "instruction": censored_turns[i]["content"],
                        "input": "",
                        "output": censored_turns[i + 1]["content"]
                    })
        elif fmt == "sharegpt":
            # ShareGPT maps roles to "human" / "gpt"
            conv_list = []
            for t in censored_turns:
                role = "human" if t["role"] == "user" else "gpt"
                conv_list.append({
                    "from": role,
                    "value": t["content"]
                })
            if conv_list:
                curated.append({
                    "conversations": conv_list
                })

    return {
        "format": fmt,
        "item_count": len(curated),
        "total_turns_processed": total_turns_processed,
        "dataset": curated
    }


@router.post("/create-model", summary="Create custom model in Ollama")
async def create_custom_model(body: CreateModelRequest):
    """Compile custom Modelfile template and trigger 'ollama create'."""
    # Build Modelfile contents
    modelfile_lines = [
        f"FROM {body.base_model}",
        f'SYSTEM """{body.system_prompt}"""',
        f"PARAMETER temperature {body.temperature}"
    ]
    modelfile = "\n".join(modelfile_lines)

    try:
        response = await ollama_client.create_model(body.name, modelfile)
        return {
            "message": f"Model '{body.name}' created successfully.",
            "response": response
        }
    except Exception as e:
        logger.error("Failed to create model: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Ollama creation error: {str(e)}"
        )
