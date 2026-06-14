"""
Error Translator Service
------------------------
Provides fast, offline, and predictable rule-based mapping of English
system errors to user-friendly Tamil messages.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

ERROR_MAP = {
    # File / System errors
    "File not found": "கோப்பு கிடைக்கவில்லை.",
    "Folder not found": "கோப்புறை கிடைக்கவில்லை.",
    "Directory not found": "கோப்புறை கிடைக்கவில்லை.",
    "Access denied": "இந்த செயலை செய்ய அனுமதி இல்லை.",
    "Permission denied": "இந்த செயலை செய்ய அனுமதி இல்லை.",
    
    # Application errors
    "Application not found": "இந்த கணினியில் அந்த பயன்பாடு நிறுவப்படவில்லை.",
    "Could not close": "பயன்பாட்டை மூட முடியவில்லை. அது இயங்கிக் கொண்டிருக்கிறதா?",
    "Failed to start": "பயன்பாட்டை திறக்க முடியவில்லை.",
    
    # Capability / Registration errors
    "Device does not support the requested tool": "இந்த சாதனம் இந்த செயல்பாட்டை ஆதரிக்கவில்லை.",
    "Invalid API key": "உள்நுழைவு தோல்வியடைந்தது. API Key தவறானது.",
    "Not authorized": "அனுமதி மறுக்கப்பட்டது.",
    
    # Web / Network
    "URL scheme not allowed": "பாதுகாப்பு கருதி இந்த இணையதளத்தை திறக்க முடியாது.",
    "Failed to launch web browser": "பிரவுசரை திறக்க முடியவில்லை."
}

class ErrorTranslator:
    @staticmethod
    def translate(error_message: str) -> str:
        """
        Translate an English error message into Tamil using rule-based mapping.
        Falls back to returning the original error if no match is found.
        """
        if not error_message:
            return "தெரியாத பிழை ஏற்பட்டது."
            
        # Exact matching
        if error_message in ERROR_MAP:
            return ERROR_MAP[error_message]
            
        # Substring matching (for errors with dynamic parameters like "File not found: X")
        for key, tamil_msg in ERROR_MAP.items():
            if key.lower() in error_message.lower():
                return tamil_msg
                
        # Future LLM Fallback would go here.
        # For now, return original if no rule matches.
        logger.warning(f"No Tamil translation found for error: {error_message}")
        return error_message

error_translator = ErrorTranslator()
