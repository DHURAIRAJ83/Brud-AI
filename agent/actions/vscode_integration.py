"""
VS Code Extension Integration Actions
--------------------------------------
Enables the desktop agent to execute workspace operations (open file, search code,
run tests, create project) directly inside VS Code if the extension is connected,
or fallback to local file system / subprocess / shell actions if offline.
"""

import os
import logging
import asyncio
import subprocess
import httpx
from typing import Dict, Any, Optional

from actions.registry import action_registry
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

async def _check_extension_connected() -> tuple[bool, Optional[str]]:
    """Check if any VS Code extension is connected via the backend."""
    try:
        api_key = settings.api_key
        headers = {"X-API-Key": api_key} if api_key else {}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.vps_url}/api/vscode/status",
                headers=headers,
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                connected = data.get("connected", False)
                sessions = data.get("sessions", [])
                session_id = sessions[0] if sessions else None
                return connected, session_id
    except Exception as e:
        logger.warning("Failed to check VS Code extension status: %s", e)
    return False, None

async def _execute_via_extension(session_id: str, command: str, params: dict) -> dict:
    """Send command to VS Code Extension via backend WebSocket bridge."""
    try:
        api_key = settings.api_key
        headers = {"X-API-Key": api_key} if api_key else {}
        payload = {
            "command": command,
            "params": params,
            "session_id": session_id
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.vps_url}/api/vscode/execute",
                headers=headers,
                json=payload,
                timeout=35.0
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                return {"status": "error", "message": f"Backend returned {resp.status_code}: {resp.text}"}
    except Exception as e:
        logger.error("Failed to execute VS Code command via extension: %s", e)
        return {"status": "error", "message": str(e)}


@action_registry.register("vscode.open_file")
async def open_file(params: Dict[str, Any]) -> dict:
    """
    Open a file in VS Code.
    Fallback flow: VS Code WebSocket Extension -> VS Code CLI (code --goto) -> OS Default Handler -> Read contents.
    """
    file_path = params.get("file_path") or params.get("file")
    if not file_path:
        return {
            "success": False,
            "tool": "vscode.open_file",
            "error": "Parameter 'file_path' is required"
        }

    # Resolve safe absolute path
    # If file_path is relative, resolve it against the active workspace
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if not os.path.isabs(file_path):
        abs_file_path = os.path.abspath(os.path.join(workspace_dir, file_path))
    else:
        abs_file_path = os.path.abspath(file_path)

    start_line = params.get("start_line")
    end_line = params.get("end_line")

    # 1. Check Priority 1: VS Code Extension Connected
    connected, session_id = await _check_extension_connected()
    if connected and session_id:
        logger.info("Routing 'vscode.open_file' to connected VS Code extension session: %s", session_id)
        res = await _execute_via_extension(session_id, "vscode.open_file", {
            "file_path": abs_file_path,
            "start_line": start_line,
            "end_line": end_line
        })
        if res.get("status") == "success":
            return {
                "success": True,
                "tool": "vscode.open_file",
                "message": f"Opened file in VS Code editor: {file_path}",
                "data": res
            }
        logger.warning("VS Code extension failed command execution, falling back: %s", res.get("message"))

    # 2. Check Priority 2: Desktop Agent Local Execution via VS Code CLI
    logger.info("Falling back to local execution for 'vscode.open_file'")
    try:
        line_suffix = f":{start_line}" if start_line else ""
        cmd = ["code", "--goto", f"{abs_file_path}{line_suffix}"] if start_line else ["code", abs_file_path]
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            return {
                "success": True,
                "tool": "vscode.open_file",
                "message": f"Opened file {file_path} locally using VS Code CLI (code)",
                "data": {"fallback": "local_subprocess"}
            }
    except Exception as e:
        logger.warning("Local VS Code CLI execution failed: %s", e)

    # 3. Check Priority 3: Command Line Fallback (OS Default Association / Content Read)
    try:
        if hasattr(os, "startfile"):
            os.startfile(abs_file_path)
            return {
                "success": True,
                "tool": "vscode.open_file",
                "message": f"Opened file {file_path} using default system file association",
                "data": {"fallback": "system_default"}
            }
    except Exception as e:
        logger.warning("Default OS startfile failed: %s", e)

    # Final read preview fallback
    try:
        if os.path.exists(abs_file_path) and os.path.isfile(abs_file_path):
            with open(abs_file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            preview = "".join(lines[:50])
            return {
                "success": True,
                "tool": "vscode.open_file",
                "message": f"VS Code extension/CLI offline. Displaying file preview (first 50 lines).",
                "data": {"content_preview": preview, "fallback": "read_preview"}
            }
    except Exception as e:
        logger.error("All fallback options failed for open_file: %s", e)

    return {
        "success": False,
        "tool": "vscode.open_file",
        "error": f"Failed to open or read file: {file_path}"
    }


@action_registry.register("vscode.search_code")
async def search_code(params: Dict[str, Any]) -> dict:
    """
    Search workspace code.
    Fallback flow: VS Code WebSocket Extension -> AST Indexer API -> Direct Directory Search.
    """
    query = params.get("query")
    if not query:
        return {
            "success": False,
            "tool": "vscode.search_code",
            "error": "Parameter 'query' is required"
        }

    # 1. Check Priority 1: VS Code Extension Connected
    connected, session_id = await _check_extension_connected()
    if connected and session_id:
        logger.info("Routing 'vscode.search_code' to connected VS Code extension session: %s", session_id)
        res = await _execute_via_extension(session_id, "vscode.search_code", {"query": query})
        if res.get("status") == "success":
            return {
                "success": True,
                "tool": "vscode.search_code",
                "message": f"Searched workspace code via VS Code for '{query}'",
                "data": res
            }
        logger.warning("VS Code extension failed command execution, falling back: %s", res.get("message"))

    # 2. Check Priority 2: Use backend Workspace Indexer AST Query API
    logger.info("Falling back to workspace index API for 'vscode.search_code'")
    try:
        api_key = settings.api_key
        headers = {"X-API-Key": api_key} if api_key else {}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.vps_url}/api/vscode/index/query",
                headers=headers,
                params={"q": query},
                timeout=5.0
            )
            if resp.status_code == 200:
                return {
                    "success": True,
                    "tool": "vscode.search_code",
                    "message": f"Searched codebase AST symbols for '{query}'",
                    "data": resp.json()
                }
    except Exception as e:
        logger.warning("Workspace indexer API request failed: %s", e)

    # 3. Check Priority 3: Local file tree scan search
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    matches = []
    try:
        for root, dirs, files in os.walk(workspace_dir):
            dirs[:] = [d for d in dirs if d not in {".git", ".github", ".vscode", "venv", ".venv", "node_modules", "__pycache__"}]
            for file in files:
                if query.lower() in file.lower():
                    matches.append(os.path.relpath(os.path.join(root, file), workspace_dir).replace("\\", "/"))
                    if len(matches) >= 20:
                        break
            if len(matches) >= 20:
                break
        return {
            "success": True,
            "tool": "vscode.search_code",
            "message": f"Searched workspace files matching '{query}'",
            "data": {"matches": matches, "fallback": "local_directory_scan"}
        }
    except Exception as e:
        logger.error("All fallback options failed for search_code: %s", e)

    return {
        "success": False,
        "tool": "vscode.search_code",
        "error": str(e)
    }


@action_registry.register("vscode.run_tests")
async def run_tests(params: Dict[str, Any]) -> dict:
    """
    Run tests in the workspace.
    Fallback flow: VS Code WebSocket Extension -> Local Subprocess Executor.
    """
    test_command = params.get("test_command") or "pytest"

    # 1. Check Priority 1: VS Code Extension Connected
    connected, session_id = await _check_extension_connected()
    if connected and session_id:
        logger.info("Routing 'vscode.run_tests' to connected VS Code extension session: %s", session_id)
        res = await _execute_via_extension(session_id, "vscode.run_tests", {"test_command": test_command})
        if res.get("status") == "success":
            return {
                "success": True,
                "tool": "vscode.run_tests",
                "message": f"Triggered tests in VS Code: {test_command}",
                "data": res
            }
        logger.warning("VS Code extension failed command execution, falling back: %s", res.get("message"))

    # 2 & 3. Check Priority 2 & 3: Run as local subprocess
    logger.info("Falling back to local subprocess for 'vscode.run_tests'")
    try:
        # Determine appropriate workspace directory
        workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        # If running pytest, make sure to execute in backend folder if tests are there
        if "pytest" in test_command and os.path.exists(os.path.join(workspace_dir, "backend")):
            cwd = os.path.join(workspace_dir, "backend")
        else:
            cwd = workspace_dir

        proc = await asyncio.create_subprocess_shell(
            test_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode(errors='ignore') + "\n" + stderr.decode(errors='ignore')
        success = (proc.returncode == 0)

        return {
            "success": success,
            "tool": "vscode.run_tests",
            "message": f"Executed local test command: {test_command}",
            "data": {
                "returncode": proc.returncode,
                "output": output[:3000], # Keep log size reasonable
                "fallback": "local_subprocess"
            }
        }
    except Exception as e:
        logger.error("Local test execution failed: %s", e)
        return {
            "success": False,
            "tool": "vscode.run_tests",
            "error": f"Failed to execute local tests: {e}"
        }


@action_registry.register("vscode.create_project")
async def create_project(params: Dict[str, Any]) -> dict:
    """
    Create a project folder.
    Fallback flow: VS Code WebSocket Extension -> OS Local Directory Creation.
    """
    project_name = params.get("project_name")
    if not project_name:
        return {
            "success": False,
            "tool": "vscode.create_project",
            "error": "Parameter 'project_name' is required"
        }

    # 1. Check Priority 1: VS Code Extension Connected
    connected, session_id = await _check_extension_connected()
    if connected and session_id:
        logger.info("Routing 'vscode.create_project' to connected VS Code extension session: %s", session_id)
        res = await _execute_via_extension(session_id, "vscode.create_project", {"project_name": project_name})
        if res.get("status") == "success":
            return {
                "success": True,
                "tool": "vscode.create_project",
                "message": f"Created project directory via VS Code: {project_name}",
                "data": res
            }
        logger.warning("VS Code extension failed command execution, falling back: %s", res.get("message"))

    # 2 & 3. Check Priority 2 & 3: Local directory creation
    logger.info("Falling back to local OS creation for 'vscode.create_project'")
    try:
        workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        target_dir = os.path.join(workspace_dir, project_name)
        os.makedirs(target_dir, exist_ok=True)
        return {
            "success": True,
            "tool": "vscode.create_project",
            "message": f"Created project directory locally: {project_name}",
            "data": {
                "path": target_dir,
                "fallback": "local_os"
            }
        }
    except Exception as e:
        logger.error("Local project folder creation failed: %s", e)
        return {
            "success": False,
            "tool": "vscode.create_project",
            "error": f"Failed to create project folder: {e}"
        }
