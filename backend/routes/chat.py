"""
Chat Route — POST /api/chat
"""

import uuid
from fastapi import APIRouter, HTTPException, Depends
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ai.orchestrator import orchestrator

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for memory continuity")
    source: str = Field("chat", description="Source of request (chat, voice)")
    voice_auth_session_id: Optional[str] = Field(None, description="Optional voice authentication session token ID")


class ChatResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    language: str
    source: str
    session_id: str


from services.auth_service import get_current_user

@router.post("/chat", response_model=ChatResponse, summary="Send a chat message")
async def chat(
    request: ChatRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Send a user message to the Tamil AI assistant.
    - Detects language (Tamil / English)
    - Detects intent and routes to appropriate tool or LLM
    - Maintains conversation memory per session_id
    """
    session_id = request.session_id or str(uuid.uuid4())
    user_id = current_user["id"] if current_user else "admin-user-123"
    try:
        result = await orchestrator.process(
            user_message=request.message,
            session_id=session_id,
            source=request.source,
            voice_auth_session_id=request.voice_auth_session_id,
            user_id=user_id
        )
        return ChatResponse(**result)

    except HTTPException:
        raise  # Re-raise 403/401/422 as-is — do NOT convert to 500
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {e}")
