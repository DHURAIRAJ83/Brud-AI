"""
Tamil Intelligence Route — normalization and language utilities
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ai.tamil_intelligence import tamil_intelligence

router = APIRouter()


class NormalizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


@router.post("/tamil/normalize", summary="Normalize text: detect language and convert Tanglish→Tamil")
async def normalize(request: NormalizeRequest):
    """
    Detect language (Tamil/English/Tanglish/Mixed) and convert Tanglish to Tamil script.

    Example:
      Input:  "enna panra da nee"
      Output: "என்ன பண்றா தா நீ"
    """
    normalized, meta = tamil_intelligence.normalize_for_llm(request.text)
    return {
        "original": request.text,
        "normalized": normalized,
        "detected_language": meta["detected_language"],
        "tanglish_converted": meta["tanglish_converted"],
        "response_hint": tamil_intelligence.get_response_language_hint(
            tamil_intelligence.detect_language(request.text)
        ),
        "stats": tamil_intelligence.stats(),
    }


@router.post("/tamil/tanglish-to-tamil", summary="Convert Tanglish to Tamil script")
async def tanglish_to_tamil(request: NormalizeRequest):
    result = tamil_intelligence.tanglish_to_tamil(request.text)
    return {"original": request.text, "tamil": result}


@router.get("/tamil/stats", summary="Tamil intelligence module stats")
async def tamil_stats():
    return tamil_intelligence.stats()
