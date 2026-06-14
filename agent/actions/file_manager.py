"""
File Manager Actions
--------------------
Provides file system operations with strict path security.

Allowed base directories:
- Documents
- Downloads
- Desktop
- Projects (usually in home directory)
"""

import os
import glob
import logging
from pathlib import Path
from typing import Dict, Any, List

from actions.registry import action_registry

logger = logging.getLogger(__name__)

# ── Security Rules ────────────────────────────────────────────────────────────

HOME_DIR = Path.home()
ALLOWED_BASES = [
    HOME_DIR / "Documents",
    HOME_DIR / "Downloads",
    HOME_DIR / "Desktop",
    HOME_DIR / "Projects",
]

BLOCKED_PATHS = [
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
]

def _resolve_safe_path(user_path: str) -> Path:
    """Resolve a user-provided path string to a safe absolute Path."""
    # Special aliases
    alias_map = {
        "documents": HOME_DIR / "Documents",
        "downloads": HOME_DIR / "Downloads",
        "desktop": HOME_DIR / "Desktop",
        "projects": HOME_DIR / "Projects",
    }
    
    path_str = user_path.lower().strip()
    if path_str in alias_map:
        return alias_map[path_str]
        
    # Attempt to resolve
    try:
        if os.path.isabs(user_path):
            target = Path(user_path).resolve()
        else:
            # Default to home dir if relative
            target = (HOME_DIR / user_path).resolve()
            
        # Check against blocked paths first
        for blocked in BLOCKED_PATHS:
            if blocked in target.parents or target == blocked:
                raise PermissionError(f"Access to {target} is blocked by security policy.")
                
        # Check if it's within an allowed base
        is_allowed = False
        for allowed in ALLOWED_BASES:
            if allowed in target.parents or target == allowed:
                is_allowed = True
                break
                
        if not is_allowed:
            raise PermissionError(f"Path {target} is outside of allowed directories (Documents, Downloads, Desktop, Projects).")
            
        return target
        
    except Exception as e:
        raise PermissionError(f"Path resolution failed or denied: {e}")


# ── Actions ───────────────────────────────────────────────────────────────────

@action_registry.register("files.list")
async def list_files(params: Dict[str, Any]) -> dict:
    """List files in a directory."""
    try:
        path_str = params.get("path", "downloads")
        target_dir = _resolve_safe_path(path_str)
        
        if not target_dir.exists() or not target_dir.is_dir():
            return {
                "success": False,
                "tool": "files.list",
                "error": f"Directory not found: {target_dir}"
            }
            
        file_filter = params.get("filter", "*")
        search_pattern = target_dir / file_filter
        
        files = []
        for file_path in glob.glob(str(search_pattern)):
            p = Path(file_path)
            files.append({
                "name": p.name,
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else 0,
                "modified": p.stat().st_mtime
            })
            
        return {
            "success": True,
            "tool": "files.list",
            "message": f"Found {len(files)} items in {target_dir.name}",
            "data": {"path": str(target_dir), "items": files}
        }
        
    except Exception as e:
        return {
            "success": False,
            "tool": "files.list",
            "error": str(e)
        }

@action_registry.register("files.search")
async def search_files(params: Dict[str, Any]) -> dict:
    """Search for files in a directory recursively."""
    try:
        query = params.get("query", "")
        if not query:
            return {
                "success": False,
                "tool": "files.search",
                "error": "Query parameter is required"
            }
            
        path_str = params.get("path", "documents")
        target_dir = _resolve_safe_path(path_str)
        
        if not target_dir.exists() or not target_dir.is_dir():
            return {
                "success": False,
                "tool": "files.search",
                "error": f"Directory not found: {target_dir}"
            }
            
        # Recursive glob search
        search_pattern = f"**/*{query}*"
        matched = []
        
        # Limit search depth/results for safety
        count = 0
        for file_path in target_dir.rglob(f"*{query}*"):
            if count >= 50: # Limit results
                break
            matched.append({
                "name": file_path.name,
                "path": str(file_path.relative_to(target_dir)),
                "is_dir": file_path.is_dir()
            })
            count += 1
            
        return {
            "success": True,
            "tool": "files.search",
            "message": f"Found {len(matched)} matching items in {target_dir.name}",
            "data": {"path": str(target_dir), "query": query, "items": matched}
        }
        
    except Exception as e:
        return {
            "success": False,
            "tool": "files.search",
            "error": str(e)
        }

@action_registry.register("files.read")
async def read_file(params: Dict[str, Any]) -> dict:
    """Read contents of a text file."""
    try:
        file_path_str = params.get("filename", "")
        if not file_path_str:
            return {
                "success": False,
                "tool": "files.read",
                "error": "Filename parameter is required"
            }
            
        target_file = _resolve_safe_path(file_path_str)
        
        if not target_file.exists() or not target_file.is_file():
            return {
                "success": False,
                "tool": "files.read",
                "error": f"File not found: {target_file}"
            }
            
        # Check size to prevent reading massive files
        size_kb = target_file.stat().st_size / 1024
        if size_kb > 500: # 500 KB limit
            return {
                "success": False,
                "tool": "files.read",
                "error": f"File too large to read ({size_kb:.1f} KB). Limit is 500 KB."
            }
            
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        return {
            "success": True,
            "tool": "files.read",
            "message": f"Successfully read {target_file.name}",
            "data": {"filename": target_file.name, "content": content}
        }
        
    except UnicodeDecodeError:
        return {
            "success": False,
            "tool": "files.read",
            "error": "File appears to be binary or uses unsupported encoding."
        }
    except Exception as e:
        return {
            "success": False,
            "tool": "files.read",
            "error": str(e)
        }

@action_registry.register("files.create_folder")
async def create_folder(params: Dict[str, Any]) -> dict:
    """Create a new folder."""
    try:
        folder_name = params.get("name", "")
        if not folder_name:
            return {
                "success": False,
                "tool": "files.create_folder",
                "error": "Folder name parameter is required"
            }
            
        parent_str = params.get("parent", "desktop")
        parent_dir = _resolve_safe_path(parent_str)
        
        target_dir = parent_dir / folder_name
        
        # Verify target is also safe
        _resolve_safe_path(str(target_dir))
        
        if target_dir.exists():
            return {
                "success": False,
                "tool": "files.create_folder",
                "error": f"Folder already exists: {target_dir}"
            }
            
        target_dir.mkdir(parents=True, exist_ok=False)
        
        return {
            "success": True,
            "tool": "files.create_folder",
            "message": f"Successfully created folder {folder_name} in {parent_dir.name}",
            "data": {"path": str(target_dir)}
        }
        
    except Exception as e:
        return {
            "success": False,
            "tool": "files.create_folder",
            "error": str(e)
        }

@action_registry.register("files.rename")
async def rename_file(params: Dict[str, Any]) -> dict:
    """Rename a file or folder."""
    try:
        source_str = params.get("source", "")
        new_name = params.get("new_name", "")
        
        if not source_str or not new_name:
            return {
                "success": False,
                "tool": "files.rename",
                "error": "Source and new_name parameters are required"
            }
            
        source_path = _resolve_safe_path(source_str)
        
        if not source_path.exists():
            return {
                "success": False,
                "tool": "files.rename",
                "error": f"Source not found: {source_path}"
            }
            
        # Target path is in the same directory
        target_path = source_path.parent / new_name
        
        # Verify target is safe
        _resolve_safe_path(str(target_path))
        
        if target_path.exists():
            return {
                "success": False,
                "tool": "files.rename",
                "error": f"Destination already exists: {target_path}"
            }
            
        source_path.rename(target_path)
        
        return {
            "success": True,
            "tool": "files.rename",
            "message": f"Successfully renamed to {new_name}",
            "data": {"old_path": str(source_path), "new_path": str(target_path)}
        }
        
    except Exception as e:
        return {
            "success": False,
            "tool": "files.rename",
            "error": str(e)
        }
