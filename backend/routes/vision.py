"""
Vision Routes
-------------
Endpoints to process screenshots and graphics files using vision LLMs.
"""

import base64
import os
import logging
import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional
from services.vision_service import vision_service
from services.runtime_manager import runtime_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/vision/analyze", summary="Analyze an image using vision LLMs")
async def analyze_image(
    prompt: str = Form(..., description="Description of what to look for or analyze"),
    image_path: Optional[str] = Form(None, description="Optional local file path to the image"),
    file: Optional[UploadFile] = File(None, description="Optional uploaded screenshot image file")
):
    """
    Analyzes an image using the active Ollama vision fallback chain (qwen2.5-vl -> llava:7b -> text).
    """
    if file:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty uploaded file")
            
        img_b64 = base64.b64encode(content).decode("utf-8")
        base_url = await runtime_manager.get_active_url()
        models_to_try = ["qwen2.5-vl", "llava:7b"]
        
        for model in models_to_try:
            try:
                logger.info("Directly analyzing uploaded file with vision model %s", model)
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(
                        f"{base_url}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt,
                            "images": [img_b64],
                            "stream": False
                        }
                    )
                    if resp.status_code == 200:
                        return {
                            "success": True,
                            "model": model,
                            "analysis": resp.json().get("response", "").strip()
                        }
            except Exception as ex:
                logger.warning("direct upload analysis failed for model %s: %s", model, ex)
                
        # Fallback text descriptor message
        return {
            "success": False,
            "model": "none",
            "analysis": "Vision analysis unavailable. All vision models failed to respond."
        }
        
    elif image_path:
        analysis = await vision_service.analyze_image(image_path, prompt)
        return {
            "success": "Error" not in analysis,
            "model": "qwen2.5-vl/llava:7b",
            "analysis": analysis
        }
    else:
        raise HTTPException(status_code=400, detail="Either image_path or file parameter must be provided")
