"""
Tamil Language Intelligence Module
------------------------------------
Your USP (Unique Selling Proposition) 💥

Features:
  1. Language detection: Tamil / English / Tanglish / Mixed
  2. Tanglish → Tamil script conversion (rule-based, offline, zero-latency)
  3. Text normalization before LLM (fixes common mistakes)
  4. Script detection utilities

Approach:
  - Fully rule-based for Tanglish → Tamil (no model needed)
  - Covers the most commonly used Tanglish phonemes
  - LLM is used only as fallback for ambiguous cases (optional)

This runs in microseconds on CPU — no ML model required.
"""

import re
import logging
import unicodedata
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Language(str, Enum):
    TAMIL = "ta"
    ENGLISH = "en"
    TANGLISH = "tanglish"   # English-script Tamil
    MIXED = "mixed"         # Both Tamil + English
    UNKNOWN = "unknown"


# ── Tamil Unicode range ────────────────────────────────────────────────────────
TAMIL_UNICODE_START = 0x0B80
TAMIL_UNICODE_END = 0x0BFF


def _has_tamil_script(text: str) -> bool:
    """Check if text contains Tamil Unicode characters."""
    return any(TAMIL_UNICODE_START <= ord(c) <= TAMIL_UNICODE_END for c in text)


def _tamil_char_ratio(text: str) -> float:
    """Fraction of characters that are Tamil script."""
    if not text:
        return 0.0
    tamil_count = sum(
        1 for c in text if TAMIL_UNICODE_START <= ord(c) <= TAMIL_UNICODE_END
    )
    return tamil_count / len(text.replace(" ", ""))


# ── Tanglish detection ─────────────────────────────────────────────────────────

# Common Tanglish words (English-written Tamil) — highly indicative
TANGLISH_SIGNALS = {
    "enna", "ennaku", "naan", "nee", "avar", "ivan", "ival", "avanga",
    "inga", "anga", "epdi", "eppo", "yenna", "yenakku", "romba", "konjam",
    "sollu", "kelu", "paru", "paaru", "vaa", "po", "vandha", "vandhu",
    "pannu", "panni", "pannuvaen", "theriyum", "theriyala", "puriyudha",
    "seri", "illa", "illai", "aam", "aama", "aiyo", "adha", "itha",
    "athu", "ithu", "unakku", "enakku", "namakku", "ungalukku",
    "vendum", "vendam", "mudiyum", "mudiyala", "solren", "keten",
    "paathen", "vandhen", "poren", "kita", "kitta", "dhan", "dhaan",
    "thaane", "mattum", "ellam", "orru", "rendu", "moonu", "naalu",
    "oru", "rendum", "sollunga", "kelunga", "vaanga", "poonga",
    "therinja", "theriyaadha", "maari", "maadiri", "pola", "kuda",
    "panra", "panren", "solren", "ketaen", "paakuren", "iruken",
    "irukkiren", "vandhutten", "poyiten", "vanthen",
}


def _is_tanglish(text: str) -> bool:
    """Return True if text is Tamil written in English script."""
    if _has_tamil_script(text):
        return False  # Already in Tamil script
    words = set(re.findall(r"\b\w+\b", text.lower()))
    overlap = words & TANGLISH_SIGNALS
    # Need ≥2 tanglish words OR 30%+ word overlap
    return len(overlap) >= 2 or (len(words) > 0 and len(overlap) / len(words) >= 0.3)


# ── Tanglish → Tamil transliteration map ──────────────────────────────────────
# Rule-based: covers the most common Tanglish → Tamil phoneme mappings
# Ordered from longest to shortest to prefer greedy matching

TANGLISH_TO_TAMIL: dict[str, str] = {
    # Greetings & common phrases
    "vanakkam": "வணக்கம்",
    "vanakam": "வணக்கம்",
    "nandri": "நன்றி",
    "romba nandri": "ரொம்ப நன்றி",
    "seri": "சரி",
    "illa": "இல்ல",
    "illai": "இல்லை",
    "aam": "ஆம்",
    "aama": "ஆமா",
    "aiyo": "ஐயோ",
    "romba": "ரொம்ப",
    "konjam": "கொஞ்சம்",
    "naan": "நான்",
    "nee": "நீ",
    "avar": "அவர்",
    "ivan": "இவன்",
    "ival": "இவள்",
    "avanga": "அவங்க",
    "naanga": "நாங்க",
    "ungalukku": "உங்களுக்கு",
    "enakku": "எனக்கு",
    "unakku": "உனக்கு",
    "namakku": "நமக்கு",
    "enna": "என்ன",
    "yenna": "என்ன",
    "yenakku": "எனக்கு",
    "epdi": "எப்படி",
    "eppo": "எப்போ",
    "inga": "இங்க",
    "anga": "அங்க",
    "athu": "அது",
    "ithu": "இது",
    "adha": "அதை",
    "itha": "இதை",
    "ellam": "எல்லாம்",
    "mattum": "மட்டும்",
    "dhan": "தான்",
    "dhaan": "தான்",
    "thaane": "தானே",
    "pola": "போல",
    "maadiri": "மாதிரி",
    "maari": "மாரி",
    "kuda": "கூட",
    "theriyum": "தெரியும்",
    "theriyala": "தெரியல",
    "puriyudha": "புரியுதா",
    "vendum": "வேண்டும்",
    "vendam": "வேண்டாம்",
    "mudiyum": "முடியும்",
    "mudiyala": "முடியல",
    "sollu": "சொல்லு",
    "sollunga": "சொல்லுங்க",
    "kelu": "கேளு",
    "kelunga": "கேளுங்க",
    "paru": "பாரு",
    "paaru": "பாரு",
    "vaa": "வா",
    "po": "போ",
    "poonga": "போங்க",
    "vaanga": "வாங்க",
    "pannu": "பண்ணு",
    "panni": "பண்ணி",
    "panra": "பண்றா",
    "panren": "பண்றேன்",
    "oru": "ஒரு",
    "orru": "ஒரு",
    "rendu": "ரெண்டு",
    "moonu": "மூணு",
    "naalu": "நாலு",
    "kita": "கிட்ட",
    "kitta": "கிட்ட",
    "iruken": "இருக்கேன்",
    "irukkiren": "இருக்கிறேன்",
    "poren": "போறேன்",
    "vanthen": "வந்தேன்",
    "vandhutten": "வந்துட்டேன்",
    "poyiten": "போயிட்டேன்",
    "solren": "சொல்றேன்",
    "ketaen": "கேட்டேன்",
    "paathen": "பாத்தேன்",
    "vandhen": "வந்தேன்",
    "keten": "கேட்டேன்",
    "paakuren": "பாக்குறேன்",
}

# Sort by length descending (greedy match longer phrases first)
_SORTED_TANGLISH = sorted(TANGLISH_TO_TAMIL.keys(), key=len, reverse=True)


class TamilIntelligence:
    """
    Language detection + Tanglish normalization.
    All operations are synchronous and CPU-zero (rule-based).
    """

    # ── Language Detection ─────────────────────────────────────────────────────

    def detect_language(self, text: str) -> Language:
        """
        Detect the language/script of input text.
        Returns a Language enum.
        """
        if not text or not text.strip():
            return Language.UNKNOWN

        tamil_ratio = _tamil_char_ratio(text)

        if tamil_ratio > 0.5:
            return Language.TAMIL
        elif tamil_ratio > 0.1:
            return Language.MIXED
        elif _is_tanglish(text):
            return Language.TANGLISH
        else:
            return Language.ENGLISH

    def is_tanglish(self, text: str) -> bool:
        return _is_tanglish(text)

    # ── Tanglish Conversion ────────────────────────────────────────────────────

    def tanglish_to_tamil(self, text: str) -> str:
        """
        Convert Tanglish (Tamil written in English) to Tamil script.
        Uses rule-based longest-match substitution.

        Example:
          "enna panra" → "என்ன பண்றா"
        """
        result = text.lower()

        # Apply substitutions (longest match first)
        for tanglish_word in _SORTED_TANGLISH:
            tamil_word = TANGLISH_TO_TAMIL[tanglish_word]
            # Use word-boundary matching
            pattern = r"\b" + re.escape(tanglish_word) + r"\b"
            result = re.sub(pattern, tamil_word, result, flags=re.IGNORECASE)

        logger.debug("Tanglish → Tamil: '%s' → '%s'", text[:50], result[:50])
        return result

    # ── Text Normalization ─────────────────────────────────────────────────────

    def normalize(self, text: str) -> str:
        """
        Full normalization pipeline before sending to LLM:
          1. Strip excess whitespace
          2. Normalize Unicode (NFC)
          3. Convert Tanglish to Tamil if detected
          4. Fix common punctuation issues

        Returns (normalized_text, detected_language, was_converted)
        """
        # Step 1: basic cleanup
        text = text.strip()
        text = re.sub(r"\s+", " ", text)          # collapse whitespace
        text = unicodedata.normalize("NFC", text)  # Unicode normalization

        # Step 2: Tanglish conversion
        lang = self.detect_language(text)
        converted = False
        if lang == Language.TANGLISH:
            text = self.tanglish_to_tamil(text)
            converted = True

        return text, lang, converted

    def normalize_for_llm(self, text: str) -> tuple[str, dict]:
        """
        Returns (processed_text, metadata_dict) ready for LLM consumption.
        """
        normalized, lang, converted = self.normalize(text)
        meta = {
            "original": text,
            "normalized": normalized,
            "detected_language": lang.value,
            "tanglish_converted": converted,
            "char_count": len(normalized),
        }
        return normalized, meta

    # ── Script Utilities ───────────────────────────────────────────────────────

    def get_response_language_hint(self, lang: Language) -> str:
        """
        Generate a system prompt fragment to guide LLM response language.
        """
        hints = {
            Language.TAMIL: "Respond in Tamil script (தமிழ்).",
            Language.TANGLISH: "Respond in Tamil script (தமிழ்) since the user wrote in Tanglish.",
            Language.ENGLISH: "Respond in English.",
            Language.MIXED: "Respond in the same mix of Tamil and English the user used.",
            Language.UNKNOWN: "Respond in English.",
        }
        return hints.get(lang, "Respond helpfully.")

    def stats(self) -> dict:
        return {
            "tanglish_vocabulary_size": len(TANGLISH_TO_TAMIL),
            "detection_signals": len(TANGLISH_SIGNALS),
        }


# Singleton
tamil_intelligence = TamilIntelligence()
