"""
Summarizer Tool
---------------
Generates a concise summary of the user-supplied text using the local LLM.
Applies token trimming to stay within CPU-friendly context limits.
"""

import logging

from ai.ollama_client import ollama_client

logger = logging.getLogger(__name__)

MAX_INPUT_WORDS = 600   # Trim very long inputs to keep latency low


async def summarize_tool(user_message: str, **_) -> str:
    """
    Summarize the text provided in user_message.
    If the message just says 'summarize', we prompt for content.
    """
    # Strip common command prefixes
    for prefix in ["summarize", "summary of", "சுருக்கம்", "சுருக்கு"]:
        if user_message.lower().startswith(prefix):
            user_message = user_message[len(prefix):].strip()

    if len(user_message) < 30:
        return "Please provide the text you want me to summarize."

    # Trim to CPU-friendly token limit
    words = user_message.split()
    if len(words) > MAX_INPUT_WORDS:
        user_message = " ".join(words[:MAX_INPUT_WORDS]) + "…"
        logger.info("Input trimmed to %d words for summarizer", MAX_INPUT_WORDS)

    prompt = f"""Provide a clear, concise summary (3-5 sentences) of the following text.
If the text is in Tamil, respond in Tamil. Otherwise respond in English.

Text:
{user_message}

Summary:"""

    summary = await ollama_client.generate(
        prompt=prompt,
        temperature=0.3,
        max_tokens=256,
    )
    return summary
