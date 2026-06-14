"""
Vision Service
--------------
Manages visual analysis using local vision models hosted on Ollama.
Supports model fallback hierarchy: qwen2.5-vl (primary) -> llava:7b (secondary) -> text-only.
"""

import base64
import logging
import os
import httpx
from services.runtime_manager import runtime_manager

logger = logging.getLogger(__name__)

class VisionService:
    async def analyze_image(self, image_path: str, prompt: str) -> str:
        """
        Analyze a screenshot or local image file.
        Attempts qwen2.5-vl first, then falls back to llava:7b, and finally returns a warning string.
        """
        if not os.path.exists(image_path):
            logger.error("Vision analyze failed: path not found: %s", image_path)
            return f"Error: Image path not found: {image_path}"
            
        try:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        except Exception as e:
            logger.error("Failed to read vision source image: %s", e)
            return f"Error reading image file: {e}"
            
        base_url = await runtime_manager.get_active_url()
        models_to_try = ["qwen2.5-vl", "llava:7b"]
        
        for model in models_to_try:
            try:
                logger.info("Attempting vision analysis using model: %s on %s", model, base_url)
                async with httpx.AsyncClient(timeout=40.0) as client:
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
                        analysis_text = resp.json().get("response", "").strip()
                        logger.info("Vision analysis succeeded with model: %s", model)
                        return analysis_text
                    else:
                        logger.warning("Ollama vision endpoint for %s returned status %d", model, resp.status_code)
            except Exception as ex:
                logger.warning("Querying vision model %s failed: %s", model, ex)
                
        # Final Fallback
        logger.warning("All vision models failed. Returning final text description fallback instructions.")
        return (
            "Unable to analyze screen visually. Local vision models (qwen2.5-vl, llava:7b) "
            "are currently offline or failed to respond. Please pull a vision model (e.g. 'ollama pull qwen2.5-vl') "
            "and verify Ollama connection."
        )

vision_service = VisionService()
