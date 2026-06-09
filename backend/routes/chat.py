"""
Chat Route — POST /api/chat
"""

import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ai.orchestrator import orchestrator

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for memory continuity")


class ChatResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    language: str
    source: str
    session_id: str


@router.post("/chat", response_model=ChatResponse, summary="Send a chat message")
async def chat(request: ChatRequest):
    """
    Send a user message to the Tamil AI assistant.
    - Detects language (Tamil / English)
    - Detects intent and routes to appropriate tool or LLM
    - Maintains conversation memory per session_id
    """
    session_id = request.session_id or str(uuid.uuid4())
    try:
        result = await orchestrator.process(
            user_message=request.message,
            session_id=session_id,
        )
        return ChatResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {e}")
