"""
Smart Model Router — Dynamic LLM Selection
--------------------------------------------
Routes each query to the most appropriate Ollama model based on:
  - Input length (token count proxy)
  - Intent type (complexity signal)
  - Explicit complexity heuristics

Goal:
  Simple query  → TinyLlama (fast, small, CPU-friendly)
  Complex query → Mistral (quality, reasoning)

This dramatically improves throughput on CPU hardware.
"""

import logging
from enum import Enum
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ModelTier(str, Enum):
    FAST = "fast"       # TinyLlama or smallest available
    BALANCED = "balanced"  # Mistral 7B or equivalent
    STRONG = "strong"   # Largest available (if any)


# Model tier configuration — edit to match your pulled models
MODEL_REGISTRY: dict[ModelTier, str] = {
    ModelTier.FAST:     "qwen3:8b",
    ModelTier.BALANCED: "qwen3:8b",
    ModelTier.STRONG:   "qwen3:8b",   # override if you have llama3
}

# Intent → complexity score (0=trivial, 1=simple, 2=complex)
INTENT_COMPLEXITY: dict[str, int] = {
    "calculate":   0,   # Pure arithmetic — no LLM needed ideally
    "translate":   1,   # Moderate
    "summarize":   1,   # Moderate
    "file_read":   1,   # Moderate
    "chat":        1,   # General
    "search_rag":  2,   # Reasoning over context
    "unknown":     2,   # Assume complex
}


class ModelRouter:
    """
    Decides which Ollama model to use for a given request.

    Scoring logic (additive):
      - Word count > 80   → +2
      - Word count > 30   → +1
      - Intent complexity  → 0/1/2
      - Question marks > 2 → +1 (multi-question)
      - Code block present → +1

    Score → Tier:
      0-1  → FAST
      2-3  → BALANCED
      4+   → STRONG
    """

    def __init__(self):
        self._overridden_model: Optional[str] = None  # Admin override

    def set_override(self, model: Optional[str]):
        """Force a specific model for all requests (admin control)."""
        self._overridden_model = model
        if model:
            logger.info("Model router: override set to '%s'", model)
        else:
            logger.info("Model router: override cleared, using dynamic routing")

    def score(self, text: str, intent: str = "chat") -> int:
        """Compute complexity score for routing decision."""
        words = len(text.split())
        score = 0

        # Length signal
        if words > 60:
            score += 2
        elif words > 20:
            score += 1

        # Intent signal
        score += INTENT_COMPLEXITY.get(intent, 1)

        # Multi-question signal
        if text.count("?") > 2:
            score += 1

        # Code / technical content
        if any(tok in text for tok in ["```", "def ", "class ", "import ", "SELECT "]):
            score += 1

        return score

    def select_model(self, text: str, intent: str = "chat") -> tuple[str, ModelTier]:
        """
        Returns (model_name, tier) for the given text + intent.
        If admin override is active, returns that model regardless.
        """
        if self._overridden_model:
            return self._overridden_model, ModelTier.BALANCED

        complexity = self.score(text, intent)

        if complexity <= 1:
            tier = ModelTier.FAST
        elif complexity <= 3:
            tier = ModelTier.BALANCED
        else:
            tier = ModelTier.STRONG

        model = MODEL_REGISTRY.get(tier, settings.ollama_model)
        logger.info(
            "Model router: score=%d → tier=%s → model=%s (intent=%s, words=%d)",
            complexity, tier.value, model, intent, len(text.split())
        )
        return model, tier

    def get_routing_info(self, text: str, intent: str = "chat") -> dict:
        """Return routing metadata for observability."""
        score = self.score(text, intent)
        model, tier = self.select_model(text, intent)
        return {
            "model": model,
            "tier": tier.value,
            "complexity_score": score,
            "word_count": len(text.split()),
            "intent": intent,
            "override_active": self._overridden_model is not None,
        }


# Singleton
model_router = ModelRouter()
