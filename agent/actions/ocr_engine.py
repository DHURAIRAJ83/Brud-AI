"""
OCR Engine Actions
------------------
Pytesseract-based OCR module with mixed-language support (Tamil + English)
capable of extracting plain text, scanning for application errors, 
and computing layout coordinates (bounding boxes) for GUI objects.
"""

import logging
import os
import sys
import mss
from mss.tools import to_png
from datetime import datetime
from PIL import Image
import pytesseract
from typing import Dict, Any

from actions.registry import action_registry
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Tesseract binary path
if settings.ocr_tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.ocr_tesseract_cmd
    logger.info("Configured Tesseract path: %s", settings.ocr_tesseract_cmd)
elif sys.platform == "win32":
    default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(default_win_path):
        pytesseract.pytesseract.tesseract_cmd = default_win_path
        logger.info("Found and configured default Windows Tesseract: %s", default_win_path)
    else:
        logger.warning("Tesseract OCR binary not found. Please install Tesseract or configure OCR_TESSERACT_CMD in .env.")

@action_registry.register("screen.ocr")
async def screen_ocr(params: Dict[str, Any]) -> dict:
    """Perform Tamil/English OCR on the specified image file or capture a new screenshot."""
    try:
        image_path = params.get("image_path")
        
        # If no image path provided, capture full screen first
        if not image_path:
            filename = f"screenshots/ocr_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with mss.mss() as sct:
                sct_img = sct.grab(sct.monitors[0])
                to_png(sct_img.rgb, sct_img.size, output=filename)
            image_path = filename
            
        if not os.path.exists(image_path):
            return {
                "success": False,
                "tool": "screen.ocr",
                "error": f"Image file not found: {image_path}"
            }
            
        img = Image.open(image_path)
        
        # Run Tesseract OCR (with mixed Tamil + English layout configuration)
        try:
            text = pytesseract.image_to_string(img, lang="tam+eng")
        except Exception as ocr_err:
            logger.warning("Mixed Tamil+English OCR failed, falling back to English only: %s", ocr_err)
            text = pytesseract.image_to_string(img, lang="eng")
            
        return {
            "success": True,
            "tool": "screen.ocr",
            "message": "Successfully extracted text from image",
            "data": {
                "image_path": os.path.abspath(image_path),
                "text": text.strip(),
                "languages": ["tam", "eng"]
            }
        }
    except Exception as e:
        logger.error("OCR action failed: %s", e)
        return {
            "success": False,
            "tool": "screen.ocr",
            "error": f"OCR execution failed: {str(e)}. Please check if Tesseract binary is installed on target agent system."
        }

@action_registry.register("screen.read_error")
async def screen_read_error(params: Dict[str, Any]) -> dict:
    """Analyze screen or target image file to detect system dialogue error strings."""
    try:
        ocr_res = await screen_ocr(params)
        if not ocr_res.get("success"):
            return ocr_res
            
        text = ocr_res["data"]["text"]
        
        # Search criteria for typical fatal error contexts (English & Tamil)
        error_keywords = [
            "error", "exception", "failed", "fatal", "crash", "bug", "invalid", 
            "not found", "denied", "unauthorized", "warning", "blocked",
            "பிழை", "தோல்வி", "தவறு", "விலக்கப்பட்டது", "கிடைக்கவில்லை"
        ]
        
        found_errors = []
        lines = text.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in error_keywords):
                found_errors.append({
                    "line_number": i + 1,
                    "content": line.strip()
                })
                
        is_error_present = len(found_errors) > 0
        message = f"Detected {len(found_errors)} error indicator(s) on screen" if is_error_present else "No obvious error indicators found on screen"
        
        return {
            "success": True,
            "tool": "screen.read_error",
            "message": message,
            "data": {
                "image_path": ocr_res["data"]["image_path"],
                "error_present": is_error_present,
                "findings": found_errors,
                "raw_text": text
            }
        }
    except Exception as e:
        logger.error("Read error action failed: %s", e)
        return {
            "success": False,
            "tool": "screen.read_error",
            "error": str(e)
        }

@action_registry.register("screen.extract_text")
async def screen_extract_text(params: Dict[str, Any]) -> dict:
    """Extract text alongside bounding box layout coordinates from the screen or image."""
    try:
        image_path = params.get("image_path")
        
        if not image_path:
            filename = f"screenshots/ocr_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with mss.mss() as sct:
                sct_img = sct.grab(sct.monitors[0])
                to_png(sct_img.rgb, sct_img.size, output=filename)
            image_path = filename
            
        if not os.path.exists(image_path):
            return {
                "success": False,
                "tool": "screen.extract_text",
                "error": f"Image file not found: {image_path}"
            }
            
        img = Image.open(image_path)
        
        try:
            data_df = pytesseract.image_to_data(img, lang="tam+eng", output_type=pytesseract.Output.DICT)
        except Exception:
            data_df = pytesseract.image_to_data(img, lang="eng", output_type=pytesseract.Output.DICT)
            
        words_data = []
        n_boxes = len(data_df['text'])
        for i in range(n_boxes):
            text_word = data_df['text'][i].strip()
            conf = float(data_df['conf'][i])
            if text_word and conf > 40:  # Threshold confidence
                words_data.append({
                    "word": text_word,
                    "left": data_df['left'][i],
                    "top": data_df['top'][i],
                    "width": data_df['width'][i],
                    "height": data_df['height'][i],
                    "confidence": conf
                })
                
        full_text = pytesseract.image_to_string(img, lang="tam+eng")
        
        return {
            "success": True,
            "tool": "screen.extract_text",
            "message": f"Extracted {len(words_data)} layout elements with locations",
            "data": {
                "image_path": os.path.abspath(image_path),
                "text": full_text.strip(),
                "elements": words_data
            }
        }
    except Exception as e:
        logger.error("Extract text failed: %s", e)
        return {
            "success": False,
            "tool": "screen.extract_text",
            "error": str(e)
        }
