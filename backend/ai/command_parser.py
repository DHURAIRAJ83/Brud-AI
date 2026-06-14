"""
Command Parser — Tamil/English NL → Tool-Based JSON
------------------------------------------------------
Converts natural language commands (Tamil, English, Tanglish)
into structured tool-based action schemas.

Tool naming pattern: namespace.action
  - desktop.open_app, desktop.close_app
  - browser.open, browser.search
  - files.list, files.search, files.read, files.create_folder
  - screen.capture, screen.ocr
  - git.commit, git.push
  - vscode.create_project

Uses a two-tier approach:
  1. Rule-based fast-path for common Tamil/English desktop commands
  2. LLM fallback for complex or ambiguous commands

CPU Optimization:
  - Rule-based path runs in microseconds
  - LLM path uses low temperature + small max_tokens
"""

import json
import logging
import re
from typing import Callable, Coroutine, Any, Dict, Optional

from pydantic import BaseModel, Field

from ai.ollama_client import ollama_client
from ai.tamil_intelligence import tamil_intelligence, Language

logger = logging.getLogger(__name__)


# ── Action Schema ─────────────────────────────────────────────────────────────

class DesktopAction(BaseModel):
    """Structured action parsed from natural language."""
    tool: str = Field(..., description="Tool name: desktop.open_app, files.list, etc.")
    params: dict = Field(default_factory=dict, description="Tool-specific parameters")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    source_language: str = Field("en", description="Detected language: ta, en, mixed")
    raw_input: str = Field("", description="Original user message")
    is_desktop_command: bool = Field(True, description="Whether this is a desktop action")


# ── Tamil Command Vocabulary ──────────────────────────────────────────────────

# App name aliases (Tamil → English canonical name)
APP_ALIASES: dict[str, str] = {
    # Tamil names
    "குரோம்": "chrome",
    "கூகுள் குரோம்": "chrome",
    "பயர்பாக்ஸ்": "firefox",
    "விஎஸ்கோட்": "vscode",
    "வி.எஸ்.கோட்": "vscode",
    "நோட்பேட்": "notepad",
    "நோட்பேட்++": "notepad++",
    "எக்ஸ்புளோரர்": "explorer",
    "கால்குலேட்டர்": "calculator",
    "பெயிண்ட்": "paint",
    "வேர்ட்": "word",
    "எக்செல்": "excel",
    "பவர்பாயிண்ட்": "powerpoint",
    "டெர்மினல்": "terminal",
    "கமாண்ட் ப்ராம்ப்ட்": "cmd",

    # English / common aliases
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "vs code": "vscode",
    "vscode": "vscode",
    "visual studio code": "vscode",
    "notepad": "notepad",
    "notepad++": "notepad++",
    "explorer": "explorer",
    "file explorer": "explorer",
    "file manager": "explorer",
    "calculator": "calculator",
    "calc": "calculator",
    "paint": "paint",
    "word": "word",
    "excel": "excel",
    "powerpoint": "powerpoint",
    "ppt": "powerpoint",
    "terminal": "terminal",
    "cmd": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "spotify": "spotify",
    "discord": "discord",
    "slack": "slack",
    "teams": "teams",
    "zoom": "zoom",
    "telegram": "telegram",
    "whatsapp": "whatsapp",
    "obs": "obs",
    "vlc": "vlc",
    "git bash": "gitbash",
    "postman": "postman",
}

# Known folder aliases (Tamil → path key)
FOLDER_ALIASES: dict[str, str] = {
    # Tamil
    "பதிவிறக்கம்": "downloads",
    "பதிவிறக்கங்கள்": "downloads",
    "ஆவணங்கள்": "documents",
    "டெஸ்க்டாப்": "desktop",
    "படங்கள்": "pictures",
    "வீடியோக்கள்": "videos",
    "இசை": "music",

    # English
    "downloads": "downloads",
    "download": "downloads",
    "documents": "documents",
    "document": "documents",
    "desktop": "desktop",
    "pictures": "pictures",
    "photos": "pictures",
    "videos": "videos",
    "music": "music",
    "home": "home",
}

# File extension filters
FILE_EXTENSIONS: dict[str, str] = {
    "pdf": "*.pdf",
    "image": "*.png,*.jpg,*.jpeg,*.gif,*.bmp",
    "படம்": "*.png,*.jpg,*.jpeg,*.gif,*.bmp",
    "photo": "*.png,*.jpg,*.jpeg,*.gif,*.bmp",
    "video": "*.mp4,*.avi,*.mkv,*.mov",
    "வீடியோ": "*.mp4,*.avi,*.mkv,*.mov",
    "text": "*.txt",
    "python": "*.py",
    "doc": "*.doc,*.docx",
    "excel": "*.xls,*.xlsx",
    "code": "*.py,*.js,*.ts,*.java,*.cpp,*.c",
}


# ── Tamil Action Verbs ────────────────────────────────────────────────────────

# Tamil verb → action mapping
TAMIL_ACTION_VERBS: dict[str, str] = {
    # Open
    "திற": "open",
    "திறக்கவும்": "open",
    "திற": "open",
    "ஓபன்": "open",
    "open": "open",

    # Close
    "மூடு": "close",
    "மூடவும்": "close",
    "close": "close",
    "க்ளோஸ்": "close",

    # Search
    "தேடு": "search",
    "தேடவும்": "search",
    "search": "search",
    "சர்ச்": "search",
    "find": "search",

    # Show / List
    "காட்டு": "list",
    "காட்டவும்": "list",
    "காண்பி": "list",
    "show": "list",
    "list": "list",

    # Create
    "உருவாக்கு": "create",
    "உருவாக்கவும்": "create",
    "create": "create",
    "கிரியேட்": "create",
    "make": "create",

    # Read
    "படி": "read",
    "படிக்கவும்": "read",
    "read": "read",

    # Delete
    "அழி": "delete",
    "அழிக்கவும்": "delete",
    "delete": "delete",
    "நீக்கு": "delete",
    "remove": "delete",

    # Capture
    "பிடி": "capture",
    "capture": "capture",
    "screenshot": "capture",
    "ஸ்கிரீன்ஷாட்": "capture",
}


# ── Rule-Based Parser ─────────────────────────────────────────────────────────

class RuleBasedParser:
    """
    Fast rule-based parser for common Tamil/English desktop commands.
    Returns None if it can't parse (falls through to LLM).
    """

    def parse(self, text: str, language: str = "en") -> Optional[DesktopAction]:
        """Attempt rule-based parsing of the command."""
        lower = text.lower().strip()
        normalized = text.strip()

        # Try each parser in order
        parsers = [
            self._parse_open_app,
            self._parse_close_app,
            self._parse_web_search,
            self._parse_open_url,
            self._parse_list_files,
            self._parse_file_search,
            self._parse_create_folder,
            self._parse_read_file,
            self._parse_screen_capture,
            self._parse_screen_ocr,
            self._parse_skills_activation,
        ]

        for parser in parsers:
            result = parser(normalized, lower, language)
            if result:
                result.raw_input = text
                result.source_language = language
                return result

        return None

    def _find_app(self, text: str) -> Optional[str]:
        """Find application name in text."""
        lower = text.lower()
        # Check longest aliases first
        for alias in sorted(APP_ALIASES.keys(), key=len, reverse=True):
            if alias.lower() in lower:
                return APP_ALIASES[alias]
        return None

    def _find_folder(self, text: str) -> Optional[str]:
        """Find folder name in text."""
        lower = text.lower()
        for alias in sorted(FOLDER_ALIASES.keys(), key=len, reverse=True):
            if alias in lower:
                return FOLDER_ALIASES[alias]
        return None

    def _find_file_filter(self, text: str) -> Optional[str]:
        """Find file type filter in text."""
        lower = text.lower()
        for key, pattern in FILE_EXTENSIONS.items():
            if key in lower:
                return pattern
        return None

    # ── Pattern matchers ──────────────────────────────────────────────────────

    def _parse_open_app(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "VS Code திற", "open chrome", "குரோம் திற" """
        open_signals = ["திற", "திறக்கவும்", "ஓபன்", "open", "launch", "start", "run"]
        if any(s in lower for s in open_signals):
            app = self._find_app(text)
            if app:
                return DesktopAction(
                    tool="desktop.open_app",
                    params={"app": app},
                    confidence=0.95,
                    is_desktop_command=True,
                )
        return None

    def _parse_close_app(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "chrome மூடு", "close notepad" """
        close_signals = ["மூடு", "மூடவும்", "close", "quit", "exit", "kill", "க்ளோஸ்"]
        if any(s in lower for s in close_signals):
            app = self._find_app(text)
            if app:
                return DesktopAction(
                    tool="desktop.close_app",
                    params={"app": app},
                    confidence=0.90,
                    is_desktop_command=True,
                )
        return None

    def _parse_web_search(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "Google ல FastAPI tutorial தேடு", "search for python tutorials" """
        search_signals = ["தேடு", "தேடவும்", "search", "find", "google", "சர்ச்"]
        if any(s in lower for s in search_signals):
            # Extract search query — remove action words and engine names
            query = text
            remove_words = [
                "google", "ல்", "ல", "தேடு", "தேடவும்", "search", "for",
                "சர்ச்", "search for", "find", "in", "on", "இல்",
            ]
            for word in remove_words:
                query = re.sub(r'\b' + re.escape(word) + r'\b', '', query, flags=re.IGNORECASE)
            query = re.sub(r'\s+', ' ', query).strip()

            if query:
                # Detect search engine
                engine = "google"
                if "youtube" in lower:
                    engine = "youtube"
                elif "bing" in lower:
                    engine = "bing"

                return DesktopAction(
                    tool="browser.search",
                    params={"query": query, "engine": engine},
                    confidence=0.85,
                    is_desktop_command=True,
                )
        return None

    def _parse_open_url(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "open google.com", "github.com திற" """
        url_pattern = r'(https?://\S+|[\w-]+\.(?:com|org|net|io|dev|in|co)\S*)'
        match = re.search(url_pattern, text)
        if match:
            url = match.group(1)
            if not url.startswith("http"):
                url = f"https://{url}"
            return DesktopAction(
                tool="browser.open",
                params={"url": url},
                confidence=0.90,
                is_desktop_command=True,
            )
        return None

    def _parse_list_files(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "Downloads folder files காட்டு", "show files in documents" """
        list_signals = ["காட்டு", "காண்பி", "show", "list", "display", "files"]
        folder_mentioned = self._find_folder(text)
        file_filter = self._find_file_filter(text)

        if folder_mentioned and any(s in lower for s in list_signals):
            params = {"path": folder_mentioned}
            if file_filter:
                params["filter"] = file_filter
            return DesktopAction(
                tool="files.list",
                params=params,
                confidence=0.90,
                is_desktop_command=True,
            )
        return None

    def _parse_file_search(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "find report.pdf", "report என்ற file தேடு" """
        search_signals = ["தேடு", "search", "find", "locate"]
        file_signals = ["file", "கோப்பு", "document", "ஆவணம்"]

        if (any(s in lower for s in search_signals) and
                any(s in lower for s in file_signals)):
            # Extract filename/pattern
            query = text
            for word in search_signals + file_signals + ["என்ற", "called", "named"]:
                query = re.sub(r'\b' + re.escape(word) + r'\b', '', query, flags=re.IGNORECASE)
            query = re.sub(r'\s+', ' ', query).strip()

            folder = self._find_folder(text)
            params = {"query": query}
            if folder:
                params["path"] = folder
            return DesktopAction(
                tool="files.search",
                params=params,
                confidence=0.80,
                is_desktop_command=True,
            )
        return None

    def _parse_create_folder(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "create new folder called Projects", "Projects என்ற folder உருவாக்கு" """
        create_signals = ["உருவாக்கு", "create", "make", "mkdir", "கிரியேட்"]
        folder_signals = ["folder", "directory", "கோப்புறை", "dir"]

        if (any(s in lower for s in create_signals) and
                any(s in lower for s in folder_signals)):
            # Extract folder name
            name = text
            for word in create_signals + folder_signals + ["new", "புதிய", "called", "named", "என்ற"]:
                # Remove word case-insensitively, handling optional spaces around it
                pattern = r'(?i)\s*' + re.escape(word) + r'\s*'
                name = re.sub(pattern, ' ', name)
            name = re.sub(r'\s+', ' ', name).strip()

            parent = self._find_folder(text)
            params = {"name": name}
            if parent:
                params["parent"] = parent
            return DesktopAction(
                tool="files.create_folder",
                params=params,
                confidence=0.85,
                is_desktop_command=True,
            )
        return None

    def _parse_read_file(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "read readme.txt", "readme.txt படி" """
        read_signals = ["படி", "படிக்கவும்", "read", "open file", "view"]
        if any(s in lower for s in read_signals):
            # Try to find a filename
            file_pattern = r'[\w.-]+\.(?:txt|md|py|js|json|csv|log|cfg|ini|yaml|yml|xml|html|css)'
            match = re.search(file_pattern, text)
            if match:
                return DesktopAction(
                    tool="files.read",
                    params={"filename": match.group()},
                    confidence=0.85,
                    is_desktop_command=True,
                )
        return None

    def _parse_screen_capture(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "take screenshot", "ஸ்கிரீன்ஷாட் எடு", "capture screen" """
        capture_signals = [
            "screenshot", "ஸ்கிரீன்ஷாட்", "screen capture",
            "capture screen", "திரை பிடி", "திரை எடு",
            "take screenshot", "grab screen", "திரையை படம் பிடி",
            "ஸ்கிரீன் ஷாட்", "capture", "capture region", "region capture"
        ]
        if any(s in lower for s in capture_signals):
            tool = "screen.capture"
            params = {}
            
            if any(w in lower for w in ["window", "active", "சாளரம்", "முன்னணி"]):
                tool = "screen.active_window"
            elif any(w in lower for w in ["region", "area", "பகுதி", "குறிப்பிட்ட"]):
                tool = "screen.region_capture"
                x = re.search(r'x\s*[=:]\s*(\d+)', lower)
                y = re.search(r'y\s*[=:]\s*(\d+)', lower)
                w = re.search(r'w\s*[=:]\s*(\d+)', lower)
                h = re.search(r'h\s*[=:]\s*(\d+)', lower)
                params["x"] = int(x.group(1)) if x else 0
                params["y"] = int(y.group(1)) if y else 0
                params["w"] = int(w.group(1)) if w else 400
                params["h"] = int(h.group(1)) if h else 400
            elif any(w in lower for w in ["multi", "all", "எல்லா", "பல்வேறு"]):
                tool = "screen.multi_monitor_capture"

            return DesktopAction(
                tool=tool,
                params=params,
                confidence=0.95,
                is_desktop_command=True,
            )
        return None

    def _parse_screen_ocr(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "read screen", "திரையில் என்ன error", "திரையை வாசி" """
        ocr_signals = [
            "ocr", "வாசி", "படி", "read text", "extract text", "எழுது", 
            "எழுதி", "என்ன எழுதப்பட்டுள்ளது", "டெக்ஸ்ட்", "read screen", 
            "read", "extract", "layout", "coordinates"
        ]
        error_signals = ["error", "பிழை", "பிரச்சனை", "தவறு", "problem"]
        
        if any(s in lower for s in ocr_signals) or any(s in lower for s in error_signals):
            tool = "screen.ocr"
            params = {}
            
            if any(s in lower for s in error_signals):
                tool = "screen.read_error"
            elif any(s in lower for s in ["layout", "boxes", "coordinates", "இடம்", "பகுதி", "அளவுகள்", "extract"]):
                tool = "screen.extract_text"
                
            file_match = re.search(r'([\w-]+\.(?:png|jpg|jpeg))', lower)
            if file_match:
                params["image_path"] = file_match.group(1)
                
            return DesktopAction(
                tool=tool,
                params=params,
                confidence=0.90,
                is_desktop_command=True,
            )
        return None

    def _parse_skills_activation(self, text: str, lower: str, lang: str) -> Optional[DesktopAction]:
        """Parse: "FastAPI Expert-ஆக மாறு", "switch to researcher skill", "activate skill devops-engineer" """
        signals = ["ஆக மாறு", "ஆக மாற்று", "change to", "switch to", "activate skill", "skills", "personality"]
        if any(s in lower for s in signals):
            skill_slugs = [
                "assistant", "tamil-teacher", "researcher", "python-developer",
                "fastapi-expert", "devops-engineer", "ai-engineer", "textile-expert"
            ]
            for slug in skill_slugs:
                normalized_slug = slug.replace("-", " ")
                if slug in lower or normalized_slug in lower:
                    return DesktopAction(
                        tool="skills.activate",
                        params={"skill_id": slug},
                        confidence=0.95,
                        is_desktop_command=True,
                    )
            # Transliterations
            tamil_map = {
                "தமிழ்ப் பேராசிரியர்": "tamil-teacher",
                "ஆராய்ச்சியாளர்": "researcher",
                "பைதான் டெவலப்பர்": "python-developer",
                "வல்லுநர்": "fastapi-expert",
                "டெவொப்ஸ்": "devops-engineer",
                "நெசவு": "textile-expert"
            }
            for key, val in tamil_map.items():
                if key in lower:
                    return DesktopAction(
                        tool="skills.activate",
                        params={"skill_id": val},
                        confidence=0.90,
                        is_desktop_command=True,
                    )
        return None


# ── LLM-Based Parser ─────────────────────────────────────────────────────────

COMMAND_PARSER_SYSTEM = """You are a command parser for a Tamil/English AI desktop assistant called Rudran AI.

Convert the user's natural language command into a structured JSON action.

Available tools:
- desktop.open_app     → params: {"app": "name"}
- desktop.close_app    → params: {"app": "name"}
- browser.open         → params: {"url": "https://..."}
- browser.search       → params: {"query": "search terms", "engine": "google"}
- files.list           → params: {"path": "downloads", "filter": "*.pdf"}
- files.search         → params: {"query": "filename", "path": "documents"}
- files.read           → params: {"filename": "readme.txt"}
- files.create_folder  → params: {"name": "ProjectName", "parent": "desktop"}
- screen.capture       → params: {}
- screen.active_window → params: {}
- screen.region_capture → params: {"x": 0, "y": 0, "w": 400, "h": 400}
- screen.multi_monitor_capture → params: {}
- screen.ocr           → params: {"image_path": "optional.png"}
- screen.read_error    → params: {"image_path": "optional.png"}
- screen.extract_text  → params: {"image_path": "optional.png"}
- process.list         → params: {}
- process.kill         → params: {"name": "process_name"}

Rules:
1. Reply ONLY with valid JSON — no extra text.
2. Use lowercase for tool names.
3. Understand both Tamil and English commands.
4. If the command is NOT a desktop action, set "is_desktop_command" to false.

Response format:
{"tool": "<tool>", "params": {<params>}, "confidence": <0.0-1.0>, "is_desktop_command": true}

Examples:
"VS Code திற" → {"tool": "desktop.open_app", "params": {"app": "vscode"}, "confidence": 0.95, "is_desktop_command": true}
"Google ல FastAPI tutorial தேடு" → {"tool": "browser.search", "params": {"query": "FastAPI tutorial", "engine": "google"}, "confidence": 0.90, "is_desktop_command": true}
"Downloads folder ல PDF files காட்டு" → {"tool": "files.list", "params": {"path": "downloads", "filter": "*.pdf"}, "confidence": 0.90, "is_desktop_command": true}
"What is Python?" → {"tool": "chat", "params": {}, "confidence": 0.90, "is_desktop_command": false}
"""


class LLMParser:
    """Fallback LLM-based parser for complex/ambiguous commands."""

    async def parse(self, text: str, language: str = "en") -> Optional[DesktopAction]:
        """Parse command using LLM."""
        prompt = f"Parse this command:\n\n{text}\n\nJSON:"
        try:
            raw = await ollama_client.generate(
                prompt=prompt,
                system=COMMAND_PARSER_SYSTEM,
                temperature=0.1,
                max_tokens=200,
            )
            # Extract JSON
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return DesktopAction(
                    tool=data.get("tool", "chat"),
                    params=data.get("params", {}),
                    confidence=data.get("confidence", 0.7),
                    source_language=language,
                    raw_input=text,
                    is_desktop_command=data.get("is_desktop_command", True),
                )
        except Exception as e:
            logger.warning("LLM command parsing failed: %s", e)

        return None


# ── Command Parser (Main Entry Point) ─────────────────────────────────────────

class CommandParser:
    """
    Two-tier command parser:
      1. Rule-based fast path (microseconds, offline)
      2. LLM fallback (seconds, uses Ollama)
    """

    def __init__(self):
        self.rule_parser = RuleBasedParser()
        self.llm_parser = LLMParser()

    def decompose_multi_step(self, raw_input: str) -> list[str]:
        """Splits compound sentences by multi-step signals into individual raw command candidates."""
        pattern = re.compile(
            r'\b(?:and|then|also|after\s+that|plus)\b|'
            r'(?:\s+மற்றும்\s+|\s+பின்னர்\s+|\s+அதன்பிறகு\s+)',
            re.IGNORECASE
        )
        parts = pattern.split(raw_input)
        return [p.strip() for p in parts if p.strip()]

    async def parse(self, user_message: str) -> DesktopAction:
        """
        Parse a natural language command into a structured tool action.

        Returns a DesktopAction with:
          - tool: namespace.action (e.g., "desktop.open_app")
          - params: action-specific parameters
          - confidence: 0.0 to 1.0
          - is_desktop_command: whether this is a desktop action or just chat
        """
        # Detect language
        normalized, meta = tamil_intelligence.normalize_for_llm(user_message)
        lang = meta["detected_language"]

        # Tier 1: Rule-based (instant)
        result = self.rule_parser.parse(normalized, lang)
        if result:
            logger.info(
                "Command parsed (rules): tool=%s confidence=%.2f lang=%s",
                result.tool, result.confidence, lang
            )
            return result

        # Also try parsing original (non-normalized) text
        result = self.rule_parser.parse(user_message, lang)
        if result:
            logger.info(
                "Command parsed (rules/original): tool=%s confidence=%.2f",
                result.tool, result.confidence
            )
            return result

        # Tier 2: LLM fallback (slow but smart)
        result = await self.llm_parser.parse(normalized, lang)
        if result:
            logger.info(
                "Command parsed (LLM): tool=%s confidence=%.2f",
                result.tool, result.confidence
            )
            return result

        # Fallback: not a desktop command
        logger.info("Command not recognized as desktop action: '%s'", user_message[:50])
        return DesktopAction(
            tool="chat",
            params={"message": user_message},
            confidence=0.5,
            source_language=lang,
            raw_input=user_message,
            is_desktop_command=False,
        )

    def is_desktop_command(self, text: str) -> bool:
        """Quick check if text looks like a desktop command (no LLM call)."""
        lower = text.lower()
        desktop_signals = list(TAMIL_ACTION_VERBS.keys()) + [
            "open", "close", "search", "show", "list", "create",
            "delete", "capture", "screenshot", "folder", "file",
            "skills", "மாறு", "change to", "switch to", "personality"
        ]
        return any(signal in lower for signal in desktop_signals)


# Singleton
command_parser = CommandParser()
