"""
Plugin System — Dynamic Tool Loading
--------------------------------------
Replaces the static TOOL_REGISTRY with a self-registration system.
Each plugin file in tools/plugins/ auto-registers itself on import.

Architecture:
  tools/
  ├── tool_engine.py      ← Plugin registry + dispatcher
  ├── summarizer.py       ← Built-in tool (auto-registered)
  ├── calculator.py       ← Built-in tool
  ├── translator.py       ← Built-in tool
  ├── file_reader.py      ← Built-in tool
  └── plugins/            ← Drop new tools here, they auto-load
        ├── __init__.py
        ├── weather_tool.py   ← Example plugin
        └── web_search_tool.py

Plugin Contract:
  Each plugin must:
  1. Define: PLUGIN_NAME = "my_tool"          (str)
  2. Define: PLUGIN_INTENTS = ["my_intent"]   (list[str])
  3. Define: async def execute(message, **kwargs) -> str
  4. Call: from tools.tool_engine import plugin_registry; plugin_registry.register(...)
     OR simply export PLUGIN_NAME, PLUGIN_INTENTS, execute — the engine will auto-discover.
"""

import importlib
import importlib.util
import logging
import pkgutil
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ── Plugin Registry ────────────────────────────────────────────────────────────

class PluginRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}  # intent → async function
        self._metadata: dict[str, dict] = {}   # intent → {name, description, source}

    def register(
        self,
        intents: list[str],
        fn: Callable,
        name: str = "",
        description: str = "",
        source: str = "builtin",
    ):
        """Register an async tool function for one or more intents."""
        for intent in intents:
            self._tools[intent] = fn
            self._metadata[intent] = {
                "name": name or fn.__name__,
                "description": description,
                "source": source,
                "intents": intents,
            }
        logger.info("Registered plugin '%s' for intents: %s", name or fn.__name__, intents)

    def get(self, intent: str) -> Optional[Callable]:
        return self._tools.get(intent)

    def list_plugins(self) -> list[dict]:
        seen = set()
        result = []
        for intent, meta in self._metadata.items():
            key = meta["name"]
            if key not in seen:
                seen.add(key)
                result.append({**meta, "registered_intents": meta["intents"]})
        return result

    def unregister(self, intent: str):
        self._tools.pop(intent, None)
        self._metadata.pop(intent, None)
        logger.info("Unregistered plugin for intent: %s", intent)

    def intent_count(self) -> int:
        return len(self._tools)


# Global registry instance
plugin_registry = PluginRegistry()


# ── Tool Engine (uses plugin registry) ───────────────────────────────────────

class ToolEngine:
    def __init__(self, registry: PluginRegistry):
        self.registry = registry

    async def execute(self, intent: str, user_message: str, **kwargs) -> dict:
        tool_fn = self.registry.get(intent)
        if not tool_fn:
            logger.warning("No tool for intent: %s", intent)
            return {
                "result": f"No tool available for intent '{intent}'.",
                "tool": intent,
                "error": "not_found",
            }
        try:
            logger.info("Executing tool: %s", intent)
            result = await tool_fn(user_message, **kwargs)
            return {"result": result, "tool": intent, "error": None}
        except Exception as e:
            logger.error("Tool '%s' failed: %s", intent, e)
            return {"result": "Tool execution failed.", "tool": intent, "error": str(e)}

    def list_tools(self) -> list[str]:
        return list(self.registry._tools.keys())


# ── Auto-loader ───────────────────────────────────────────────────────────────

def _load_builtin_tools():
    """Register the built-in tools."""
    from tools.summarizer import summarize_tool
    from tools.calculator import calculate_tool
    from tools.translator import translate_tool
    from tools.file_reader import file_reader_tool

    plugin_registry.register(["summarize"], summarize_tool, name="Summarizer",
                              description="Generates concise summaries of text.")
    plugin_registry.register(["calculate"], calculate_tool, name="Calculator",
                              description="Safe math expression evaluator.")
    plugin_registry.register(["translate"], translate_tool, name="Translator",
                              description="Tamil ↔ English translation.")
    plugin_registry.register(["file_read"], file_reader_tool, name="FileReader",
                              description="Reads and answers questions about uploaded files.")


def _load_plugins_from_folder():
    """Dynamically import all .py files in tools/plugins/."""
    plugins_dir = Path(__file__).parent / "plugins"
    if not plugins_dir.exists():
        plugins_dir.mkdir(parents=True)
        logger.info("Created plugins/ directory")
        return

    for file in plugins_dir.glob("*.py"):
        if file.stem.startswith("_"):
            continue
        module_name = f"tools.plugins.{file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Auto-register if module exports required attributes
            if hasattr(module, "PLUGIN_NAME") and hasattr(module, "execute"):
                intents = getattr(module, "PLUGIN_INTENTS", [module.PLUGIN_NAME])
                desc = getattr(module, "PLUGIN_DESCRIPTION", "")
                plugin_registry.register(
                    intents=intents,
                    fn=module.execute,
                    name=module.PLUGIN_NAME,
                    description=desc,
                    source=f"plugin:{file.name}",
                )
                logger.info("Auto-loaded plugin: %s from %s", module.PLUGIN_NAME, file.name)

        except Exception as e:
            logger.error("Failed to load plugin %s: %s", file.name, e)


# Initialize
_load_builtin_tools()
_load_plugins_from_folder()

# Singleton engine
tool_engine = ToolEngine(plugin_registry)
