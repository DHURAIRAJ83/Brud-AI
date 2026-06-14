"""
Intent Detection Engine
-----------------------
Uses the local LLM to classify user intent via structured prompt-based
classification. Returns a JSON-like dict with `intent` + `confidence`.

Supported intents:
  chat          – General conversation / Q&A
  summarize     – Condense a text / document
  calculate     – Math or numeric computation
  translate     – Language translation request
  search_rag    – Query over uploaded documents
  file_read     – Read / extract info from a file
  unknown       – Couldn't determine intent
"""

import json
import logging
import re
from typing import Optional

from ai.ollama_client import ollama_client

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """You are an intent classifier for a Tamil/English AI assistant.

Classify the user message into exactly one of these intents:
- chat        : general conversation or question
- summarize   : user wants a summary of text/document
- calculate   : mathematical calculation or number problem
- translate   : user wants translation between Tamil and English
- search_rag  : user wants to search uploaded documents/files
- file_read   : user wants to read or extract content from a file
- change_skill: user wants to switch or change to another skill profile or personality
- unknown     : none of the above

Rules:
1. Reply ONLY with valid JSON — no extra text.
2. Confidence must be a float between 0.0 and 1.0.
3. Use lowercase for the intent value.

Response format:
{"intent": "<intent>", "confidence": <float>, "reasoning": "<one sentence>"}
"""


class IntentEngine:
    def __init__(self):
        # Fast keyword shortcuts — avoids LLM call for obvious cases
        self._keyword_map = {
            "summarize": ["summarize", "summary", "சுருக்கம்", "சுருக்கு"],
            "calculate": ["calculate", "math", "compute", "+", "-", "*", "/", "கணக்கு"],
            "translate": ["translate", "translation", "மொழிபெயர்", "to english", "to tamil"],
            "search_rag": ["find in", "search document", "from the file", "கோப்பில்"],
            "change_skill": ["ஆக மாறு", "ஆக மாற்று", "change to", "switch to", "skills", "activate skill"],
        }

    def _quick_classify(self, text: str) -> Optional[dict]:
        """Keyword-based fast path to avoid LLM overhead."""
        lower = text.lower()
        for intent, keywords in self._keyword_map.items():
            if any(kw in lower for kw in keywords):
                return {"intent": intent, "confidence": 0.85, "reasoning": "Keyword match"}
        return None

    async def detect(self, user_message: str) -> dict:
        """
        Detect intent of `user_message`.
        Returns: {"intent": str, "confidence": float, "reasoning": str}
        """
        # 1. Try fast keyword path first
        quick = self._quick_classify(user_message)
        if quick:
            logger.info("Intent (keyword): %s", quick["intent"])
            return quick

        # 2. LLM classification
        prompt = (
            f"Classify this message:\n\n"
            f"Message: {user_message}\n\n"
            f"JSON response:"
        )
        try:
            raw = await ollama_client.generate(
                prompt=prompt,
                system=INTENT_SYSTEM_PROMPT,
                temperature=0.1,   # Low temp → deterministic classification
                max_tokens=128,
            )

            # Extract JSON from response (LLM may wrap it in markdown)
            json_match = re.search(r"\{.*?\}", raw, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                logger.info("Intent (LLM): %s (%.2f)", result.get("intent"), result.get("confidence"))
                return result

        except Exception as e:
            logger.warning("Intent detection failed: %s", e)

        return {"intent": "chat", "confidence": 0.5, "reasoning": "Fallback to chat"}


# Singleton
intent_engine = IntentEngine()
