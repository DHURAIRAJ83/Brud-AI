"""
Git Control Actions
--------------------
Provides secure git actions (commit with diff previews, push) via command-line subprocesses.
"""

import os
import logging
import asyncio
from typing import Dict, Any

from actions.registry import action_registry
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def _get_project_root() -> str:
    """Returns the resolved absolute path of the project workspace."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

@action_registry.register("git.commit")
async def git_commit(params: Dict[str, Any]) -> dict:
    """Stage and commit changes in the repository. Generates dry-run previews on request."""
    try:
        message = params.get("message")
        if not message:
            return {"success": False, "tool": "git.commit", "error": "Missing parameter 'message'"}
            
        dry_run = params.get("dry_run", False)
        root = _get_project_root()
        
        # 1. Run git status to see if there are changes
        status_proc = await asyncio.create_subprocess_shell(
            "git status --porcelain",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=root
        )
        status_out, _ = await status_proc.communicate()
        status_text = status_out.decode().strip()
        
        if not status_text:
            return {
                "success": True,
                "tool": "git.commit",
                "message": "No changes to commit. Working tree clean.",
                "data": {"committed": False}
            }
            
        # 2. Dry run preview stats using git diff
        diff_proc = await asyncio.create_subprocess_shell(
            "git diff --stat",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=root
        )
        diff_out, _ = await diff_proc.communicate()
        diff_stat = diff_out.decode().strip()
        
        # Parse diff statistics (files changed, insertions, deletions)
        files_changed = 0
        insertions = 0
        deletions = 0
        if diff_stat:
            # e.g., " 2 files changed, 10 insertions(+), 5 deletions(-)"
            last_line = diff_stat.splitlines()[-1] if diff_stat.splitlines() else ""
            parts = last_line.split(",")
            for part in parts:
                clean_part = part.strip().lower()
                if "file" in clean_part:
                    files_changed = int(clean_part.split()[0])
                elif "insertion" in clean_part:
                    insertions = int(clean_part.split()[0])
                elif "deletion" in clean_part:
                    deletions = int(clean_part.split()[0])

        if dry_run:
            return {
                "success": True,
                "tool": "git.commit",
                "message": "Dry-run: Previewing commit changes",
                "data": {
                    "dry_run": True,
                    "diff_stat": diff_stat,
                    "files_changed": files_changed,
                    "insertions": insertions,
                    "deletions": deletions,
                    "status_output": status_text
                }
            }
            
        # 3. Stage and commit
        add_proc = await asyncio.create_subprocess_shell(
            "git add .",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=root
        )
        await add_proc.wait()
        
        commit_proc = await asyncio.create_subprocess_shell(
            f'git commit -m "{message}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=root
        )
        commit_out, commit_err = await commit_proc.communicate()
        commit_text = commit_out.decode().strip() + "\n" + commit_err.decode().strip()
        
        success = (commit_proc.returncode == 0)
        return {
            "success": success,
            "tool": "git.commit",
            "message": f"Committed modifications: {message}" if success else "Failed to commit changes",
            "data": {
                "dry_run": False,
                "committed": success,
                "commit_output": commit_text,
                "files_changed": files_changed,
                "insertions": insertions,
                "deletions": deletions
            }
        }
    except Exception as e:
        return {"success": False, "tool": "git.commit", "error": str(e)}


@action_registry.register("git.push")
async def git_push(params: Dict[str, Any]) -> dict:
    """Push local commits to remote origin repository."""
    try:
        branch = params.get("branch") or "main"
        root = _get_project_root()
        
        proc = await asyncio.create_subprocess_shell(
            f"git push origin {branch}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=root
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode().strip() + "\n" + stderr.decode().strip()
        success = (proc.returncode == 0)
        
        return {
            "success": success,
            "tool": "git.push",
            "message": f"Pushed commits to origin/{branch}" if success else "Failed to push commits to remote",
            "data": {
                "branch": branch,
                "output": output[:2000]
            }
        }
    except Exception as e:
        return {"success": False, "tool": "git.push", "error": str(e)}
