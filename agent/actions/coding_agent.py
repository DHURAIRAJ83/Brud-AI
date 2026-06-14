"""
Coding Agent Actions
---------------------
Implements programming tools including read, write, explain, search symbol,
project analysis, test execution, and the self-healing error-fixing loop.
Includes strict containment boundaries, extension whitelisting, and a backup system.
"""

import os
import time
import glob
import shutil
import logging
import asyncio
import difflib
import httpx
from typing import Dict, Any, List, Optional

from actions.registry import action_registry
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_WRITE_SIZE = 1_000_000  # 1 MB Limit
ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", 
    ".md", ".yaml", ".yml", ".html", ".css", ".txt"
}

def _get_project_root() -> str:
    """Returns the resolved absolute path of the project workspace."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def _verify_safe_path(user_path: str, check_extension: bool = False) -> str:
    """Resolve user-provided path and ensure it is strictly contained within project root."""
    root = _get_project_root()
    
    if os.path.isabs(user_path):
        resolved = os.path.abspath(user_path)
    else:
        resolved = os.path.abspath(os.path.join(root, user_path))
        
    # Check containment
    if not resolved.startswith(root):
        raise PermissionError(f"Access denied: Path '{resolved}' is outside project root '{root}'")
        
    # Explicitly block systemic directories
    blocked_roots = ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)", "/etc", "/root", "/var", "/bin"]
    for blocked in blocked_roots:
        try:
            blocked_abs = os.path.abspath(blocked)
            if resolved.startswith(blocked_abs) or resolved == blocked_abs:
                raise PermissionError(f"Access denied: System directory '{resolved}' is blocked")
        except Exception:
            pass

    if check_extension:
        _, ext = os.path.splitext(resolved)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            raise PermissionError(f"Access denied: File extension '{ext}' is not permitted. Permitted: {list(ALLOWED_EXTENSIONS)}")
            
    return resolved

def _backup_file(file_path: str):
    """Saves a timestamped backup of the target file, retaining only the last 20 backups per file."""
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return
        
    root = _get_project_root()
    backup_dir = os.path.join(root, ".backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    base_name = os.path.basename(file_path)
    name, ext = os.path.splitext(base_name)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_name = f"{name}_{timestamp}{ext}"
    backup_path = os.path.join(backup_dir, backup_name)
    
    # Save copy
    shutil.copy2(file_path, backup_path)
    logger.info("Created file backup: %s -> %s", file_path, backup_path)
    
    # Retention check: Keep last 20 backups matching this file name prefix
    pattern = os.path.join(backup_dir, f"{name}_*{ext}")
    existing_backups = sorted(glob.glob(pattern))
    
    if len(existing_backups) > 20:
        to_delete = existing_backups[:-20]
        for old_backup in to_delete:
            try:
                os.remove(old_backup)
                logger.debug("Pruned old backup file: %s", old_backup)
            except Exception as e:
                logger.warning("Failed to delete stale backup %s: %s", old_backup, e)

def _get_diff(file_a: str, file_b: str) -> str:
    """Computes a unified diff between two files."""
    try:
        with open(file_a, "r", encoding="utf-8", errors="ignore") as f:
            lines_a = f.readlines()
    except Exception:
        lines_a = []
        
    try:
        with open(file_b, "r", encoding="utf-8", errors="ignore") as f:
            lines_b = f.readlines()
    except Exception:
        lines_b = []
        
    diff = difflib.unified_diff(
        lines_a, lines_b,
        fromfile=os.path.basename(file_a),
        tofile=os.path.basename(file_b)
    )
    return "".join(diff)


@action_registry.register("coding.create_project")
async def create_project(params: Dict[str, Any]) -> dict:
    """Create a new subfolder/project inside the workspace."""
    try:
        project_name = params.get("project_name")
        if not project_name:
            return {"success": False, "tool": "coding.create_project", "error": "Missing parameter 'project_name'"}
            
        target_dir = _verify_safe_path(project_name)
        os.makedirs(target_dir, exist_ok=True)
        return {
            "success": True,
            "tool": "coding.create_project",
            "message": f"Successfully created project folder '{project_name}'",
            "data": {"path": target_dir}
        }
    except Exception as e:
        return {"success": False, "tool": "coding.create_project", "error": str(e)}


@action_registry.register("coding.read_code")
async def read_code(params: Dict[str, Any]) -> dict:
    """Reads content from a code file securely."""
    try:
        file_path_str = params.get("file_path") or params.get("file")
        if not file_path_str:
            return {"success": False, "tool": "coding.read_code", "error": "Missing parameter 'file_path'"}
            
        target_file = _verify_safe_path(file_path_str, check_extension=True)
        if not os.path.exists(target_file) or not os.path.isfile(target_file):
            return {"success": False, "tool": "coding.read_code", "error": f"File not found: {file_path_str}"}
            
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        
        with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        if start_line is not None:
            # 1-indexed conversion
            s_idx = max(0, start_line - 1)
            e_idx = end_line if end_line is not None else len(lines)
            selected_lines = lines[s_idx:e_idx]
            content = "".join(selected_lines)
            message = f"Read lines {start_line} to {e_idx} of {os.path.basename(target_file)}"
        else:
            content = "".join(lines)
            message = f"Read entire content of {os.path.basename(target_file)}"
            
        return {
            "success": True,
            "tool": "coding.read_code",
            "message": message,
            "data": {"content": content, "lines_read": len(content.splitlines())}
        }
    except Exception as e:
        return {"success": False, "tool": "coding.read_code", "error": str(e)}


@action_registry.register("coding.write_code")
async def write_code(params: Dict[str, Any]) -> dict:
    """Writes, appends, or edits code contents in a file securely with backup execution."""
    try:
        file_path_str = params.get("file_path") or params.get("file")
        if not file_path_str:
            return {"success": False, "tool": "coding.write_code", "error": "Missing parameter 'file_path'"}
            
        target_file = _verify_safe_path(file_path_str, check_extension=True)
        content = params.get("content", "")
        mode = params.get("mode", "write").lower() # "write" (overwrite), "append", "replace"
        
        # Check size constraints
        if len(content) > MAX_WRITE_SIZE:
            return {
                "success": False,
                "tool": "coding.write_code",
                "error": f"Write payload size exceeds maximum limit of {MAX_WRITE_SIZE} bytes"
            }
            
        # Create backup if file exists
        if os.path.exists(target_file):
            _backup_file(target_file)
            
        if mode == "write":
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content)
            msg = f"Overwrote contents of {os.path.basename(target_file)}"
        elif mode == "append":
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(content)
            msg = f"Appended content to {os.path.basename(target_file)}"
        elif mode == "replace":
            target_content = params.get("target_content")
            if not target_content:
                return {"success": False, "tool": "coding.write_code", "error": "Parameter 'target_content' is required in 'replace' mode"}
                
            if not os.path.exists(target_file):
                return {"success": False, "tool": "coding.write_code", "error": "Cannot execute replacement on non-existent file"}
                
            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                file_text = f.read()
                
            if target_content not in file_text:
                return {
                    "success": False,
                    "tool": "coding.write_code",
                    "error": "Target content to replace was not found in the file"
                }
                
            updated_text = file_text.replace(target_content, content, 1)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(updated_text)
            msg = f"Replaced content inside {os.path.basename(target_file)}"
        else:
            return {"success": False, "tool": "coding.write_code", "error": f"Invalid mode parameter: {mode}"}
            
        return {
            "success": True,
            "tool": "coding.write_code",
            "message": msg,
            "data": {"file_path": target_file}
        }
    except Exception as e:
        return {"success": False, "tool": "coding.write_code", "error": str(e)}


@action_registry.register("coding.restore_backup")
async def restore_backup(params: Dict[str, Any]) -> dict:
    """Restores a file from its timestamped version history under .backups/ folder."""
    try:
        file_path_str = params.get("file_path") or params.get("file")
        if not file_path_str:
            return {"success": False, "tool": "coding.restore_backup", "error": "Missing parameter 'file_path'"}
            
        target_file = _verify_safe_path(file_path_str, check_extension=True)
        root = _get_project_root()
        backup_dir = os.path.join(root, ".backups")
        
        backup_file = params.get("backup_file")
        dry_run = params.get("dry_run", False)
        
        base_name = os.path.basename(target_file)
        name, ext = os.path.splitext(base_name)
        
        # If no specific backup specified, find the latest timestamped backup
        if not backup_file:
            pattern = os.path.join(backup_dir, f"{name}_*{ext}")
            matching = sorted(glob.glob(pattern))
            if not matching:
                return {"success": False, "tool": "coding.restore_backup", "error": f"No backups found for {base_name}"}
            selected_backup = matching[-1]  # Latest
        else:
            selected_backup = os.path.join(backup_dir, os.path.basename(backup_file))
            if not os.path.exists(selected_backup):
                return {"success": False, "tool": "coding.restore_backup", "error": f"Specified backup file not found: {backup_file}"}
                
        # Dry Run option computes diff and awaits dashboard consent
        diff_text = _get_diff(target_file, selected_backup)
        if dry_run:
            return {
                "success": True,
                "tool": "coding.restore_backup",
                "message": f"Dry-run: Previewing restoration of {base_name} from {os.path.basename(selected_backup)}",
                "data": {
                    "diff": diff_text,
                    "target_file": target_file,
                    "backup_file": selected_backup,
                    "dry_run": True
                }
            }
            
        # Actual restore
        shutil.copy2(selected_backup, target_file)
        return {
            "success": True,
            "tool": "coding.restore_backup",
            "message": f"Successfully restored {base_name} from backup {os.path.basename(selected_backup)}",
            "data": {
                "diff": diff_text,
                "target_file": target_file,
                "backup_file": selected_backup,
                "dry_run": False
            }
        }
    except Exception as e:
        return {"success": False, "tool": "coding.restore_backup", "error": str(e)}


@action_registry.register("coding.explain_code")
async def explain_code(params: Dict[str, Any]) -> dict:
    """Reads a code file locally and prompts the backend LLM to explain classes, functions, and flow."""
    try:
        file_path_str = params.get("file_path") or params.get("file")
        if not file_path_str:
            return {"success": False, "tool": "coding.explain_code", "error": "Missing parameter 'file_path'"}
            
        target_file = _verify_safe_path(file_path_str, check_extension=True)
        if not os.path.exists(target_file):
            return {"success": False, "tool": "coding.explain_code", "error": f"File not found: {file_path_str}"}
            
        with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
            code_content = f.read()
            
        base_name = os.path.basename(target_file)
        prompt = (
            f"விளக்கம் தேவைப்படும் குறியீடு (File: {base_name}):\n\n"
            f"```python\n{code_content[:15000]}\n```\n\n" # Limit size to fit within token boundaries
            f"தயவுசெய்து மேலே உள்ள குறியீட்டைப் புரிந்து கொண்டு, அதில் உள்ள Classes, Functions, Dependencies, மற்றும் "
            f"அதன் செயல்பாட்டு ஓட்டத்தை (flow) தமிழில் தெளிவாகவும் சுருக்கமாகவும் விளக்கவும்."
        )
        
        # Dispatch request to backend chat API
        api_key = settings.api_key
        headers = {"X-API-Key": api_key} if api_key else {}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.vps_url}/api/chat",
                headers=headers,
                json={
                    "message": prompt,
                    "session_id": "agent-code-explain"
                },
                timeout=60.0
            )
            if resp.status_code == 200:
                explanation = resp.json().get("response", "")
                return {
                    "success": True,
                    "tool": "coding.explain_code",
                    "message": f"Generated code explanation for {base_name}",
                    "data": {"explanation": explanation}
                }
            else:
                return {
                    "success": False,
                    "tool": "coding.explain_code",
                    "error": f"Backend LLM returned status code {resp.status_code}: {resp.text}"
                }
    except Exception as e:
        return {"success": False, "tool": "coding.explain_code", "error": str(e)}


@action_registry.register("coding.search_symbol")
async def search_symbol(params: Dict[str, Any]) -> dict:
    """Search for symbol declarations by querying the backend VS Code indexer API."""
    try:
        query = params.get("query")
        if not query:
            return {"success": False, "tool": "coding.search_symbol", "error": "Missing parameter 'query'"}
            
        api_key = settings.api_key
        headers = {"X-API-Key": api_key} if api_key else {}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.vps_url}/api/vscode/index/query",
                headers=headers,
                params={"q": query},
                timeout=10.0
            )
            if resp.status_code == 200:
                return {
                    "success": True,
                    "tool": "coding.search_symbol",
                    "message": f"Searched symbol index matching '{query}'",
                    "data": resp.json()
                }
            else:
                return {
                    "success": False,
                    "tool": "coding.search_symbol",
                    "error": f"Backend query endpoint returned {resp.status_code}: {resp.text}"
                }
    except Exception as e:
        return {"success": False, "tool": "coding.search_symbol", "error": str(e)}


@action_registry.register("coding.analyze_project")
async def analyze_project(params: Dict[str, Any]) -> dict:
    """Analyze the project structure, counting API routes, tests, framework settings, and DB configs locally."""
    try:
        root = _get_project_root()
        
        # 1. Framework detection
        framework = "Unknown"
        req_paths = [
            os.path.join(root, "backend", "requirements.txt"),
            os.path.join(root, "requirements.txt")
        ]
        for req_path in req_paths:
            if os.path.exists(req_path):
                try:
                    with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().lower()
                        if "fastapi" in content:
                            framework = "FastAPI"
                        elif "django" in content:
                            framework = "Django"
                        elif "flask" in content:
                            framework = "Flask"
                        break
                except Exception:
                    pass
                    
        # 2. Frontend detection
        frontend = "None"
        pkg_paths = [
            os.path.join(root, "frontend", "package.json"),
            os.path.join(root, "dashboard", "package.json"),
            os.path.join(root, "package.json")
        ]
        for pkg_path in pkg_paths:
            if os.path.exists(pkg_path):
                try:
                    with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().lower()
                        if "react" in content:
                            frontend = "React"
                        elif "vue" in content:
                            frontend = "Vue"
                        elif "next" in content:
                            frontend = "Next.js"
                        break
                except Exception:
                    pass

        # 3. Database detection
        database = "Unknown"
        db_found = False
        for folder_root, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "venv", "node_modules", "__pycache__", ".backups"}]
            for file in files:
                if file.endswith(".db") or file.endswith(".sqlite") or file.endswith(".sqlite3"):
                    database = "SQLite"
                    db_found = True
                    break
            if db_found:
                break
                
        if not db_found:
            for req_path in req_paths:
                if os.path.exists(req_path):
                    try:
                        with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read().lower()
                            if "psycopg" in content or "postgresql" in content:
                                database = "PostgreSQL"
                            elif "mysql" in content:
                                database = "MySQL"
                    except Exception:
                        pass

        # 4. Count test cases
        test_count = 0
        test_dir = os.path.join(root, "backend", "tests")
        if not os.path.exists(test_dir):
            test_dir = os.path.join(root, "tests")
            
        if os.path.exists(test_dir):
            for folder_root, dirs, files in os.walk(test_dir):
                for file in files:
                    if file.startswith("test_") and file.endswith(".py"):
                        try:
                            with open(os.path.join(folder_root, file), "r", encoding="utf-8", errors="ignore") as f:
                                for line in f:
                                    if line.strip().startswith("def test_"):
                                        test_count += 1
                        except Exception:
                            pass

        # 5. Count routes (by scanning route decorations in backend)
        routes_count = 0
        for folder_root, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "venv", "node_modules", "__pycache__", ".backups"}]
            for file in files:
                if file.endswith(".py"):
                    try:
                        with open(os.path.join(folder_root, file), "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                clean_line = line.strip()
                                if clean_line.startswith("@") and ("router." in clean_line or "app." in clean_line) and any(m in clean_line for m in [".get(", ".post(", ".put(", ".delete(", ".patch("]):
                                    routes_count += 1
                    except Exception:
                        pass
                        
        return {
            "success": True,
            "tool": "coding.analyze_project",
            "message": "Completed codebase analysis",
            "data": {
                "project": "Tamil_AI",
                "framework": framework,
                "frontend": frontend,
                "database": database,
                "tests": test_count,
                "routes": routes_count
            }
        }
    except Exception as e:
        return {"success": False, "tool": "coding.analyze_project", "error": str(e)}


@action_registry.register("coding.run_tests")
async def run_tests(params: Dict[str, Any]) -> dict:
    """Executes local automated tests and captures logs."""
    try:
        test_command = params.get("test_command") or "pytest"
        root = _get_project_root()
        
        # Execute in backend subdirectory if pytest tests are in backend/tests
        if "pytest" in test_command and os.path.exists(os.path.join(root, "backend")):
            cwd = os.path.join(root, "backend")
        else:
            cwd = root
            
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
            "tool": "coding.run_tests",
            "message": f"Ran test command: {test_command}",
            "data": {
                "returncode": proc.returncode,
                "output": output[:3000]
            }
        }
    except Exception as e:
        return {"success": False, "tool": "coding.run_tests", "error": str(e)}


@action_registry.register("coding.fix_errors")
async def fix_errors(params: Dict[str, Any]) -> dict:
    """Starts a self-healing diagnostic compile loop, querying the model to fix test exceptions iteratively."""
    try:
        file_path_str = params.get("file_path") or params.get("file")
        if not file_path_str:
            return {"success": False, "tool": "coding.fix_errors", "error": "Missing parameter 'file_path'"}
            
        target_file = _verify_safe_path(file_path_str, check_extension=True)
        error_message = params.get("error_message") or ""
        test_command = params.get("test_command") or "pytest"
        max_retries = params.get("max_retries", 3)
        
        api_key = settings.api_key
        headers = {"X-API-Key": api_key} if api_key else {}
        
        attempts = []
        fixed = False
        current_error = error_message
        
        for attempt_idx in range(1, max_retries + 1):
            logger.info("Auto-fix attempt %d of %d for file: %s", attempt_idx, max_retries, base_name := os.path.basename(target_file))
            
            # Read current content
            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                current_code = f.read()
                
            # Construct self-correcting prompt
            prompt = (
                f"குறியீட்டில் (File: {base_name}) பிழை ஏற்பட்டுள்ளது. அதை சரிசெய்ய வேண்டும்.\n\n"
                f"தற்போதைய குறியீடு:\n"
                f"```python\n{current_code}\n```\n\n"
                f"பிழை அறிக்கை (Error message):\n"
                f"```\n{current_error}\n```\n\n"
                f"தயவுசெய்து மேலே உள்ள பிழையை பகுப்பாய்வு செய்து, பிழையற்ற சரி செய்யப்பட்ட புதிய குறியீட்டை மட்டும் வழங்கவும். "
                f"வேறு எந்த விளக்கமும் தேவையில்லை. குறியீட்டை ```python மற்றும் ``` என்ற குறியீட்டுக்குள் மட்டும் எழுதவும்."
            )
            
            # Send prompt to backend
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.vps_url}/api/chat",
                    headers=headers,
                    json={
                        "message": prompt,
                        "session_id": f"agent-autofix-{attempt_idx}"
                    },
                    timeout=60.0
                )
                
            if resp.status_code != 200:
                logger.error("LLM API call failed with status %d: %s", resp.status_code, resp.text)
                attempts.append({
                    "attempt": attempt_idx,
                    "error": current_error,
                    "fix_applied": "API error",
                    "result": "failed"
                })
                continue
                
            raw_response = resp.json().get("response", "")
            
            # Extract code block
            code_block = ""
            if "```python" in raw_response:
                parts = raw_response.split("```python", 1)
                if len(parts) > 1:
                    code_block = parts[1].split("```", 1)[0].strip()
            elif "```" in raw_response:
                parts = raw_response.split("```", 1)
                if len(parts) > 1:
                    code_block = parts[1].split("```", 1)[0].strip()
            else:
                code_block = raw_response.strip()
                
            if not code_block:
                logger.warning("LLM response did not contain a valid code block")
                attempts.append({
                    "attempt": attempt_idx,
                    "error": current_error,
                    "fix_applied": "Extraction failed",
                    "result": "failed"
                })
                continue
                
            # Apply fix
            _backup_file(target_file)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(code_block)
                
            # Run tests to evaluate the fix
            test_res = await run_tests({"test_command": test_command})
            test_passed = test_res.get("success", False)
            
            attempts.append({
                "attempt": attempt_idx,
                "error": current_error,
                "fix_applied": code_block[:200] + "...", # Truncate log output
                "result": "success" if test_passed else "failed"
            })
            
            if test_passed:
                fixed = True
                logger.info("Successfully auto-fixed compilation diagnostics for %s", base_name)
                break
            else:
                # Retrieve fresh error message from test outcome
                current_error = test_res.get("data", {}).get("output", "Test failed again")
                
        if fixed:
            return {
                "success": True,
                "tool": "coding.fix_errors",
                "message": f"Successfully auto-corrected file {os.path.basename(target_file)}",
                "data": {"attempts": attempts}
            }
        else:
            return {
                "success": False,
                "tool": "coding.fix_errors",
                "message": "AUTO_FIX_FAILED: Manual Review Required",
                "error": "Failed to resolve code diagnostics within maximum retry thresholds",
                "data": {"attempts": attempts}
            }
            
    except Exception as e:
        return {"success": False, "tool": "coding.fix_errors", "error": str(e)}
