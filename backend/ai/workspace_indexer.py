"""
Workspace Codebase Indexer
--------------------------
Recursively scans the active workspace folder, parses Python files via AST,
and indexes all classes, functions, FastAPI routes, database models, and imports.
Enables instant local code queries.
"""

import ast
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Directory blacklist to prevent scanning library dependencies or large caches
SKIP_DIRS = {
    ".git", ".github", ".vscode", "venv", ".venv", "node_modules", 
    "__pycache__", "build", "dist", "out", ".pytest_cache", ".backups"
}

class WorkspaceASTVisitor(ast.NodeVisitor):
    """AST visitor to parse code constructs in Python files."""
    
    def __init__(self, relative_path: str):
        self.relative_path = relative_path
        self.classes: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.routes: List[Dict[str, Any]] = []
        self.imports: List[Dict[str, Any]] = []

    def visit_Import(self, node):
        for alias in node.names:
            symbol_name = alias.asname or alias.name
            self.imports.append({
                "name": alias.name,
                "symbol_name": symbol_name,
                "symbol_type": "module",
                "line": node.lineno,
                "file": self.relative_path
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            symbol_name = alias.asname or alias.name
            symbol_type = "class" if alias.name and alias.name[0].isupper() else "function_or_var"
            self.imports.append({
                "name": f"{module}.{alias.name}",
                "symbol_name": symbol_name,
                "symbol_type": symbol_type,
                "line": node.lineno,
                "file": self.relative_path
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
                
        self.classes.append({
            "name": node.name,
            "line": node.lineno,
            "bases": bases,
            "file": self.relative_path
        })
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        is_route = False
        route_path = ""
        route_method = ""
        
        for decorator in node.decorator_list:
            # Detect router decorators: e.g. @router.get("/status") or @app.post("/create")
            if isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    # Check router or app decorators
                    if func.value.id in ["router", "app"] or "router" in func.value.id:
                        is_route = True
                        route_method = func.attr.upper()
                        # Get path argument
                        if decorator.args:
                            first_arg = decorator.args[0]
                            if isinstance(first_arg, ast.Constant):
                                route_path = first_arg.value
                            elif isinstance(first_arg, ast.Str):
                                route_path = first_arg.s
                                
        if is_route:
            self.routes.append({
                "path": route_path,
                "method": route_method,
                "function": node.name,
                "line": node.lineno,
                "file": self.relative_path
            })
        else:
            self.functions.append({
                "name": node.name,
                "line": node.lineno,
                "file": self.relative_path
            })
        self.generic_visit(node)


class WorkspaceIndexer:
    """Recursively parses and queries the code structure of the project workspace."""
    
    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = Path(root_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
        self.files_count = 0
        self.classes: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.routes: List[Dict[str, Any]] = []
        self.imports: List[Dict[str, Any]] = []
        self._initialized = False

    async def scan(self) -> dict:
        """Scan the workspace recursively and parse all Python files with Incremental re-indexing (HR-03)."""
        import json
        from datetime import datetime, timezone
        from models.base import db_manager
        
        self.classes.clear()
        self.functions.clear()
        self.routes.clear()
        self.imports.clear()
        self.files_count = 0
        
        if not self.root_dir.exists():
            logger.warning("Workspace root directory does not exist: %s", self.root_dir)
            return {"status": "error", "message": "Root directory not found"}
            
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.root_dir).replace("\\", "/")
                    
                    # HR-03: Incremental Check
                    mtime = os.path.getmtime(full_path)
                    mtime_str = datetime.fromtimestamp(mtime, timezone.utc).isoformat()
                    
                    row = await db_manager.fetch_one(
                        "SELECT last_modified, classes, functions, routes FROM project_modules WHERE file_path = ?",
                        (rel_path,)
                    )
                    
                    if row and row["last_modified"] >= mtime_str:
                        # Skip AST parsing, load cache
                        try:
                            cached_classes = json.loads(row["classes"])
                            cached_funcs = json.loads(row["functions"])
                            cached_routes = json.loads(row["routes"])
                            
                            self.classes.extend([{"name": name, "file": rel_path, "line": 0, "bases": []} for name in cached_classes])
                            self.functions.extend([{"name": name, "file": rel_path, "line": 0} for name in cached_funcs])
                            
                            for route_str in cached_routes:
                                parts = route_str.split(" ", 1)
                                method = parts[0] if len(parts) > 0 else "GET"
                                path_val = parts[1] if len(parts) > 1 else "/"
                                self.routes.append({
                                    "path": path_val,
                                    "method": method,
                                    "function": "",
                                    "line": 0,
                                    "file": rel_path
                                })
                            
                            # Load dependencies
                            dep_rows = await db_manager.fetch_all(
                                "SELECT to_file, symbol_name, symbol_type, line_number FROM project_dependencies WHERE from_file = ?",
                                (rel_path,)
                            )
                            for dep in dep_rows:
                                self.imports.append({
                                    "name": dep["to_file"],
                                    "symbol_name": dep["symbol_name"],
                                    "symbol_type": dep["symbol_type"],
                                    "line": dep["line_number"],
                                    "file": rel_path
                                })
                        except Exception as e:
                            logger.error("Failed loading index cache for %s: %s", rel_path, e)
                            await self._parse_and_save_file(full_path, rel_path, mtime_str)
                    else:
                        await self._parse_and_save_file(full_path, rel_path, mtime_str)
                        
                    self.files_count += 1
                    
        self._initialized = True
        logger.info(
            "✅ WorkspaceIndexer scanned %d files: %d classes, %d functions, %d routes indexed.",
            self.files_count, len(self.classes), len(self.functions), len(self.routes)
        )
        return {
            "status": "success",
            "files_scanned": self.files_count,
            "classes": len(self.classes),
            "functions": len(self.functions),
            "routes": len(self.routes)
        }

    async def _parse_and_save_file(self, full_path: str, rel_path: str, mtime_str: str):
        import uuid
        import json
        from models.base import db_manager
        
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
            
            tree = ast.parse(source, filename=full_path)
            visitor = WorkspaceASTVisitor(rel_path)
            visitor.visit(tree)
            
            # Save module details to DB
            classes_json = json.dumps([c["name"] for c in visitor.classes])
            funcs_json = json.dumps([f["name"] for f in visitor.functions])
            routes_json = json.dumps([f"{r['method']} {r['path']}" for r in visitor.routes])
            
            await db_manager.execute(
                """INSERT OR REPLACE INTO project_modules (file_path, classes, functions, routes, last_modified)
                   VALUES (?, ?, ?, ?, ?)""",
                (rel_path, classes_json, funcs_json, routes_json, mtime_str)
            )
            
            # Delete old dependencies
            await db_manager.execute("DELETE FROM project_dependencies WHERE from_file = ?", (rel_path,))
            
            # Resolve and save dependencies
            for imp in visitor.imports:
                to_file = self.resolve_module_path(imp["name"])
                if to_file:
                    dep_id = str(uuid.uuid4())
                    await db_manager.execute(
                        """INSERT INTO project_dependencies (id, from_file, to_file, symbol_name, symbol_type, line_number)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (dep_id, rel_path, to_file, imp["symbol_name"], imp["symbol_type"], imp["line"])
                    )
            
            # Update memory lists
            self.classes.extend(visitor.classes)
            self.functions.extend(visitor.functions)
            self.routes.extend(visitor.routes)
            self.imports.extend(visitor.imports)
        except Exception as e:
            logger.debug("Failed parsing AST and saving for file %s: %s", rel_path, e)

    def resolve_module_path(self, import_name: str) -> Optional[str]:
        """Resolves a python import path (e.g. ai.sqlite_memory) to a workspace relative file path."""
        import_path = import_name.replace(".", "/")
        candidates = [
            f"{import_path}.py",
            f"{import_path}/__init__.py",
        ]
        
        parts = import_name.split(".")
        if len(parts) > 1:
            parent_import = ".".join(parts[:-1])
            parent_path = parent_import.replace(".", "/")
            candidates.append(f"{parent_path}.py")
            candidates.append(f"{parent_path}/__init__.py")
            
        for cand in candidates:
            if (self.root_dir / cand).exists():
                return cand
            if (self.root_dir / "backend" / cand).exists():
                return f"backend/{cand}"
        return None

    async def resolve_dependency_chain(self, start_file: str, max_depth: int = 3) -> list[dict]:
        """Traces imports starting from start_file up to max_depth (HR-04 depth control)."""
        from models.base import db_manager
        visited = set()
        queue = [(start_file, 1)]
        dependencies = []
        
        while queue:
            current_file, depth = queue.pop(0)
            if current_file in visited or depth > max_depth:
                continue
            visited.add(current_file)
            
            rows = await db_manager.fetch_all(
                "SELECT to_file, symbol_name, symbol_type, line_number FROM project_dependencies WHERE from_file = ?",
                (current_file,)
            )
            for row in rows:
                to_file = row["to_file"]
                dependencies.append({
                    "from_file": current_file,
                    "to_file": to_file,
                    "symbol_name": row["symbol_name"],
                    "symbol_type": row["symbol_type"],
                    "line": row["line_number"],
                    "depth": depth
                })
                if to_file not in visited:
                    queue.append((to_file, depth + 1))
        return dependencies

    async def query(self, search_term: str) -> List[Dict[str, Any]]:
        """Query the workspace index for symbol matches (classes, functions, routes)."""
        if not self._initialized:
            await self.scan()
            
        term = search_term.lower()
        results = []
        
        # 1. Search classes
        for c in self.classes:
            if term in c["name"].lower() or term in c["file"].lower():
                results.append({
                    "type": "class",
                    "name": c["name"],
                    "file": c["file"],
                    "line": c["line"],
                    "details": f"Inherits: {', '.join(c['bases']) if c['bases'] else 'None'}"
                })
                
        # 2. Search functions
        for f in self.functions:
            if term in f["name"].lower() or term in f["file"].lower():
                results.append({
                    "type": "function",
                    "name": f["name"],
                    "file": f["file"],
                    "line": f["line"],
                    "details": "Class method or module function"
                })
                
        # 3. Search routes
        for r in self.routes:
            if term in r["path"].lower() or term in r["function"].lower() or term in r["file"].lower():
                results.append({
                    "type": "route",
                    "name": f"{r['method']} {r['path']}",
                    "file": r["file"],
                    "line": r["line"],
                    "details": f"FastAPI route mapping to function: {r['function']}()"
                })
                
        return results[:20]

    def find_app_creation(self) -> Optional[Dict[str, Any]]:
        """Directly search for where the FastAPI app is instantiated in the workspace."""
        pattern = re.compile(r'(\b\w+\b)\s*=\s*FastAPI\s*\(')
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.root_dir).replace("\\", "/")
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            for idx, line in enumerate(f, 1):
                                match = pattern.search(line)
                                if match:
                                    return {
                                        "file": rel_path,
                                        "line": idx,
                                        "variable": match.group(1),
                                        "match_text": line.strip()
                                    }
                    except Exception:
                        pass
        return None

    async def auto_detect_and_save_project_context(self, user_id: str = "admin-user-123"):
        """Auto-detects project structure and saves it to MemoryStore project_context category."""
        from ai.memory_store import memory_store, CATEGORY_PROJECT_CONTEXT
        project_name = self.root_dir.name or "Unknown_Project"
        framework = "Unknown"
        
        req_path = self.root_dir / "backend" / "requirements.txt"
        if not req_path.exists():
            req_path = self.root_dir / "requirements.txt"
            
        if req_path.exists():
            try:
                with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                    if "fastapi" in content:
                        framework = "FastAPI"
                    elif "django" in content:
                        framework = "Django"
                    elif "flask" in content:
                        framework = "Flask"
            except Exception:
                pass
                
        frontend = "None"
        package_json = self.root_dir / "frontend" / "package.json"
        if not package_json.exists():
            package_json = self.root_dir / "dashboard" / "package.json"
        if not package_json.exists():
            package_json = self.root_dir / "package.json"
            
        if package_json.exists():
            try:
                with open(package_json, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                    if "react" in content:
                        frontend = "React"
                    elif "vue" in content:
                        frontend = "Vue"
                    elif "next" in content:
                        frontend = "Next.js"
            except Exception:
                pass
                
        database = "Unknown"
        db_files = list(self.root_dir.glob("**/*.db"))
        if db_files:
            database = "SQLite"
        else:
            if req_path.exists():
                try:
                    with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                        req_content = f.read().lower()
                        if "psycopg" in req_content or "postgresql" in req_content:
                            database = "PostgreSQL"
                        elif "mysql" in req_content:
                            database = "MySQL"
                except Exception:
                    pass
                    
        await memory_store.save_fact(user_id, "project", project_name, CATEGORY_PROJECT_CONTEXT)
        await memory_store.save_fact(user_id, "framework", framework, CATEGORY_PROJECT_CONTEXT)
        await memory_store.save_fact(user_id, "frontend", frontend, CATEGORY_PROJECT_CONTEXT)
        await memory_store.save_fact(user_id, "database", database, CATEGORY_PROJECT_CONTEXT)
        
        logger.info("Saved auto-detected project context: project=%s, framework=%s, frontend=%s, database=%s", 
                    project_name, framework, frontend, database)
        return {
            "project": project_name,
            "framework": framework,
            "frontend": frontend,
            "database": database
        }


# Singleton
workspace_indexer = WorkspaceIndexer()
