"""
Translator Tool
---------------
Translates between Tamil and English using the local LLM.
Detects source language automatically.
"""

import logging

from langdetect import detect as detect_lang

from ai.ollama_client import ollama_client

logger = logging.getLogger(__name__)


async def translate_tool(user_message: str, **_) -> str:
    """Translate user_message between Tamil ↔ English."""
    # Strip command prefix
    for prefix in ["translate", "translation", "மொழிபெயர்", "to english", "to tamil"]:
        if user_message.lower().startswith(prefix):
            user_message = user_message[len(prefix):].lstrip(": ").strip()

    if not user_message:
        return "Please provide the text you want to translate."

    # Detect source language
    try:
        lang = detect_lang(user_message)
    except Exception:
        lang = "en"

    target = "Tamil" if lang == "en" else "English"
    source = "English" if lang == "en" else "Tamil"

    prompt = (
        f"Translate the following {source} text to {target}.\n"
        f"Provide ONLY the translated text, no explanation.\n\n"
        f"Text: {user_message}\n\n"
        f"Translation:"
    )

    translation = await ollama_client.generate(
        prompt=prompt,
        temperature=0.2,
        max_tokens=300,
    )
    return f"**{source} → {target}**\n\n{translation}"
