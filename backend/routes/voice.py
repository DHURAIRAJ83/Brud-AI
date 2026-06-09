"""
Voice Route — POST /api/voice/transcribe
POST /api/voice/transcribe-and-chat
"""

import asyncio
import uuid
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

from services.voice_service import voice_service
from ai.orchestrator import orchestrator

router = APIRouter()


@router.post("/voice/transcribe", summary="Transcribe audio to text (Tamil/English)")
async def transcribe(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None, description="ISO code: 'ta'=Tamil, None=auto"),
):
    """
    Upload an audio file and get back transcribed text.
    Supports WAV, MP3, M4A, OGG, WebM, FLAC.
    Tamil is auto-detected if language is not specified.
    """
    if not voice_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Whisper STT not available. Run: pip install faster-whisper",
        )

    content = await audio.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    max_bytes = 25 * 1024 * 1024  # 25 MB
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail="Audio file too large (max 25MB)")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: voice_service.transcribe(content, audio.filename or "audio.wav", language),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/voice/transcribe-and-chat", summary="Voice → Text → AI response (one-shot)")
async def transcribe_and_chat(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
):
    """
    Transcribe audio AND send the text through the AI pipeline in one call.
    Returns both the transcription and the AI response.
    Perfect for voice-first interactions.
    """
    if not voice_service.is_available():
        raise HTTPException(status_code=503, detail="Whisper STT not available")

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Step 1: Transcribe
    try:
        loop = asyncio.get_event_loop()
        stt_result = await loop.run_in_executor(
            None,
            lambda: voice_service.transcribe(content, audio.filename or "audio.wav", language),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {e}")

    transcribed_text = stt_result.get("text", "").strip()
    if not transcribed_text:
        raise HTTPException(status_code=422, detail="Could not transcribe audio — please speak clearly")

    # Step 2: Send to AI orchestrator
    sid = session_id or str(uuid.uuid4())
    try:
        ai_result = await orchestrator.process(
            user_message=transcribed_text,
            session_id=sid,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error: {e}")

    return {
        "transcription": stt_result,
        "ai_response": ai_result,
        "session_id": sid,
    }


@router.get("/voice/status", summary="Check Whisper availability and model info")
async def voice_status():
    available = voice_service.is_available()
    return {
        "available": available,
        "model": "faster-whisper",
        "model_size": "base" if available else None,
        "languages_supported": ["ta (Tamil)", "en (English)", "auto-detect"],
        "install_command": "pip install faster-whisper" if not available else None,
    }
