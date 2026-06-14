"""
Plugin Marketplace Routes
-------------------------
GET    /api/v1/admin/plugins         → list all plugins
POST   /api/v1/admin/plugins/{name}/toggle → toggle enable/disable
POST   /api/v1/admin/plugins/upload  → upload python plugin
DELETE /api/v1/admin/plugins/{name}  → delete a custom plugin
"""

import ast
import logging
import importlib.util
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel

from tools.tool_engine import plugin_registry

logger = logging.getLogger(__name__)
router = APIRouter()


class ToggleRequest(BaseModel):
    enabled: bool


@router.get("", summary="List all registered plugins")
async def list_plugins():
    """Returns a list of all plugins, their intents, source, and enabled status."""
    return plugin_registry.list_plugins()


@router.post("/{name}/toggle", summary="Toggle enabled status of a plugin")
async def toggle_plugin(name: str, body: ToggleRequest):
    """Enable or disable a plugin in the system."""
    updated = plugin_registry.toggle_plugin(name, body.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found in registry.")
    return {"message": f"Plugin '{name}' status updated to {body.enabled}.", "enabled": body.enabled}


@router.post("/upload", summary="Upload a new python plugin file")
async def upload_plugin(file: UploadFile = File(...)):
    """Upload, compile-check, and dynamically load a python plugin file."""
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files are supported.")

    # Read and decode the file content
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File content must be UTF-8 encoded text.")

    # Validate syntax using ast.parse and simple sandbox
    try:
        tree = ast.parse(content)
        # Sandbox blocklist
        blocked_imports = {"subprocess", "pty", "shlex", "os"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in blocked_imports:
                        raise HTTPException(status_code=400, detail=f"Import of '{alias.name}' is blocked by sandbox.")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in blocked_imports:
                    raise HTTPException(status_code=400, detail=f"Import from '{node.module}' is blocked by sandbox.")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ["system", "popen", "spawn"]:
                        raise HTTPException(status_code=400, detail="System execution calls are blocked by sandbox.")
    except SyntaxError as e:
        raise HTTPException(status_code=400, detail=f"Python syntax error in plugin: {e}")

    # Extract metadata attributes
    plugin_name = None
    execute_defined = False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PLUGIN_NAME":
                    if isinstance(node.value, ast.Constant):
                        plugin_name = node.value.value
                    elif isinstance(node.value, ast.Str):  # Fallback for older python ASTs
                        plugin_name = node.value.s
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "execute":
            execute_defined = True

    if not plugin_name:
        raise HTTPException(status_code=400, detail="Plugin file must define PLUGIN_NAME = '...'")
    if not execute_defined:
        raise HTTPException(status_code=400, detail="Plugin file must define async def execute(message, **kwargs) -> str")

    # Sanitize name
    safe_filename = Path(file.filename).name
    plugins_dir = Path(__file__).parent.parent / "tools" / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    file_path = plugins_dir / safe_filename

    # Write file to disk
    try:
        with open(file_path, "wb") as f:
            f.write(content_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write plugin to disk: {e}")

    # Unregister existing if name matches
    plugin_registry.unregister_plugin(plugin_name)

    # Dynamic loading
    module_name = f"tools.plugins.{file_path.stem}"
    try:
        if module_name in sys.modules:
            del sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        intents = getattr(module, "PLUGIN_INTENTS", [module.PLUGIN_NAME])
        desc = getattr(module, "PLUGIN_DESCRIPTION", "")

        plugin_registry.register(
            intents=intents,
            fn=module.execute,
            name=module.PLUGIN_NAME,
            description=desc,
            source=f"plugin:{file_path.name}",
        )
    except Exception as e:
        # If dynamic load fails, clean up the file
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f"Failed to compile or load plugin module: {e}")

    return {"message": f"Plugin '{plugin_name}' uploaded and registered successfully."}


@router.delete("/{name}", summary="Delete custom plugin")
async def delete_plugin(name: str):
    """Delete a custom plugin file and unregister it."""
    plugins = plugin_registry.list_plugins()
    plugin = next((p for p in plugins if p["name"] == name), None)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found in registry.")

    if plugin["source"] == "builtin":
        raise HTTPException(status_code=400, detail="Cannot delete built-in plugins.")

    filename = plugin["source"].replace("plugin:", "")
    file_path = Path(__file__).parent.parent / "tools" / "plugins" / filename

    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete plugin file from disk: {e}")

    plugin_registry.unregister_plugin(name)
    return {"message": f"Plugin '{name}' uninstalled and deleted successfully."}
