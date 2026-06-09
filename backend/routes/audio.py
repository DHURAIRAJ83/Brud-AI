import logging
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Response
from pydantic import BaseModel
from typing import Optional
from services.audio_service import audio_service

logger = logging.getLogger(__name__)

router = APIRouter()

class SpeakRequest(BaseModel):
    text: str
    language: str = "ta"

@router.post("/audio/transcribe", summary="Transcribe audio to text using whisper.cpp / faster-whisper")
async def transcribe(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None, description="ISO language code, e.g. 'ta'=Tamil, 'en'=English, None=auto-detect"),
):
    """
    Transcribe uploaded audio file (.wav, .mp3, etc.) to text.
    Uses whisper.cpp with a CPU fallback to faster-whisper.
    """
    content = await audio.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    max_bytes = 25 * 1024 * 1024  # 25 MB limit
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail="Audio file too large (max 25MB)")

    try:
        # whisper.cpp runs synchronously, run in thread executor to avoid blocking the event loop
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: audio_service.transcribe(content, audio.filename or "audio.wav", language)
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Audio transcription endpoint error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

@router.post("/audio/speak", summary="Synthesize text to speech")
async def speak(request: SpeakRequest):
    """
    Convert text to speech (Tamil or English).
    Returns raw audio bytes (wav or mp3).
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        audio_bytes, mime_type = await audio_service.speak(request.text, request.language)
        return Response(content=audio_bytes, media_type=mime_type)
    except Exception as e:
        logger.error("Audio speak endpoint error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Speech synthesis error: {str(e)}")
