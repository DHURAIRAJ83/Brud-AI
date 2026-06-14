"""
AI Skills Service
-----------------
Manages skill definitions, version logs, inheritance resolution, and tool whitelisting boundaries.
"""

import json
import uuid
import logging
from typing import Optional, Dict, Any, List

from models.base import db_manager

logger = logging.getLogger(__name__)

class SkillsService:
    """Core logic for managing AI skills and versions."""

    async def get_all_skills(self) -> List[Dict[str, Any]]:
        """List all available skills (builtin and custom)."""
        rows = await db_manager.fetch_all("SELECT * FROM skills ORDER BY is_builtin DESC, id ASC")
        for row in rows:
            row["tools"] = json.loads(row.get("tools") or '{"allow": [], "deny": []}')
            row["memory_scope"] = json.loads(row.get("memory_scope") or "[]")
            row["is_builtin"] = bool(row.get("is_builtin", 0))
        return rows

    async def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get skill config by ID."""
        row = await db_manager.fetch_one("SELECT * FROM skills WHERE id = ?", (skill_id,))
        if row:
            row["tools"] = json.loads(row.get("tools") or '{"allow": [], "deny": []}')
            row["memory_scope"] = json.loads(row.get("memory_scope") or "[]")
            row["is_builtin"] = bool(row.get("is_builtin", 0))
        return row

    async def create_skill(
        self,
        skill_id: str,
        name: str,
        description: str = "",
        category: str = "General",
        system_prompt: str = "",
        model: str = "auto",
        tools: Optional[Dict[str, List[str]]] = None,
        memory_scope: Optional[List[str]] = None,
        parent_skill_id: Optional[str] = None,
        voice_profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create or update a skill, adding a version record to history."""
        # Validate parent
        if parent_skill_id:
            parent = await self.get_skill(parent_skill_id)
            if not parent:
                raise ValueError(f"Parent skill '{parent_skill_id}' does not exist")

        tools_dict = tools or {"allow": [], "deny": []}
        memory_scope_list = memory_scope or ["project_context"]

        # 1. Fetch current max version
        version_row = await db_manager.fetch_one(
            "SELECT MAX(version) as max_v FROM skill_versions WHERE skill_id = ?",
            (skill_id,)
        )
        max_v = version_row.get("max_v") if version_row else None
        next_v = (max_v + 1) if max_v is not None else 1

        # 2. Check if skill exists to prevent triggering ON DELETE CASCADE on skill_versions
        existing = await self.get_skill(skill_id)
        if existing:
            await db_manager.execute(
                """UPDATE skills
                   SET name = ?, description = ?, category = ?, system_prompt = ?, model = ?, tools = ?, memory_scope = ?, parent_skill_id = ?, voice_profile = ?
                   WHERE id = ?""",
                (
                    name, description, category, system_prompt, model,
                    json.dumps(tools_dict), json.dumps(memory_scope_list), parent_skill_id, voice_profile, skill_id
                )
            )
        else:
            await db_manager.execute(
                """INSERT INTO skills
                   (id, name, description, category, system_prompt, model, tools, memory_scope, parent_skill_id, is_builtin, voice_profile)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    skill_id, name, description, category, system_prompt, model,
                    json.dumps(tools_dict), json.dumps(memory_scope_list), parent_skill_id, voice_profile
                )
            )


        # 3. Create version record
        version_id = str(uuid.uuid4())
        await db_manager.execute(
            """INSERT INTO skill_versions
               (id, skill_id, version, system_prompt, model, tools, memory_scope)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id, skill_id, next_v, system_prompt, model,
                json.dumps(tools_dict), json.dumps(memory_scope_list)
            )
        )

        logger.info("Created skill '%s' version %d", skill_id, next_v)
        return await self.get_skill(skill_id)

    async def delete_skill(self, skill_id: str) -> bool:
        """Delete custom skill (builtin skills cannot be deleted)."""
        skill = await self.get_skill(skill_id)
        if not skill:
            return False
        if skill["is_builtin"]:
            raise PermissionError("Cannot delete builtin skill profiles")

        await db_manager.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        return True

    async def get_resolved_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Resolve parent inheritance properties recursively."""
        skill = await self.get_skill(skill_id)
        if not skill:
            return None

        # Base case: no parent
        parent_id = skill.get("parent_skill_id")
        if not parent_id:
            return skill

        parent = await self.get_resolved_skill(parent_id)
        if not parent:
            return skill

        # Resolve inheritance fields:
        # Prompt: parent + double newline + child prompt
        parent_prompt = parent.get("system_prompt", "").strip()
        child_prompt = skill.get("system_prompt", "").strip()
        if parent_prompt and child_prompt:
            resolved_prompt = f"{parent_prompt}\n\n{child_prompt}"
        else:
            resolved_prompt = child_prompt or parent_prompt

        # Model: if child specifies non-auto, use child; else parent
        child_model = skill.get("model", "auto")
        resolved_model = child_model if child_model not in ("auto", "default") else parent.get("model", "auto")

        # Tools Allow & Deny:
        parent_tools = parent.get("tools") or {"allow": [], "deny": []}
        child_tools = skill.get("tools") or {"allow": [], "deny": []}

        # Allow: Union of allow lists
        resolved_allow = list(set(parent_tools.get("allow", []) + child_tools.get("allow", [])))
        # Deny: Union of deny lists
        resolved_deny = list(set(parent_tools.get("deny", []) + child_tools.get("deny", [])))

        # Memory Scope: Union of namespaces
        resolved_scope = list(set((parent.get("memory_scope") or []) + (skill.get("memory_scope") or [])))

        # Voice Profile: if child specifies, use it; else parent
        child_voice = skill.get("voice_profile")
        resolved_voice = child_voice if child_voice else parent.get("voice_profile")

        return {
            "id": skill["id"],
            "name": skill["name"],
            "description": skill["description"],
            "category": skill["category"],
            "system_prompt": resolved_prompt,
            "model": resolved_model,
            "tools": {"allow": resolved_allow, "deny": resolved_deny},
            "memory_scope": resolved_scope,
            "parent_skill_id": parent_id,
            "is_builtin": skill["is_builtin"],
            "voice_profile": resolved_voice,
            "created_at": skill["created_at"]
        }

    def _match_pattern(self, pattern: str, tool: str) -> bool:
        """Helper to match wildcard patterns e.g. coding.* to coding.write_code"""
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-1]  # e.g., "coding."
            return tool.startswith(prefix)
        return pattern == tool

    async def is_tool_allowed(self, skill_id: Optional[str], tool: str) -> bool:
        """Verify if the tool can be executed by the active skill."""
        if not skill_id:
            return True  # Default: all standard tools allowed

        resolved = await self.get_resolved_skill(skill_id)
        if not resolved:
            return True  # Fallback: assume allowed

        tools_config = resolved.get("tools") or {"allow": [], "deny": []}
        deny_list = tools_config.get("deny") or []
        allow_list = tools_config.get("allow") or []

        # 1. Deny Check: If matching pattern in deny list -> blocked
        for pattern in deny_list:
            if self._match_pattern(pattern, tool):
                logger.warning("Tool '%s' explicitly blocked by active skill '%s' deny rules", tool, skill_id)
                return False

        # 2. Allow Check:
        # If allow list is empty, then everything not explicitly denied is allowed
        if not allow_list:
            return True

        # If allow list is not empty, tool must match at least one pattern
        for pattern in allow_list:
            if self._match_pattern(pattern, tool):
                return True

        logger.warning("Tool '%s' blocked by active skill '%s': not in allow list", tool, skill_id)
        return False

# Singleton
skills_service = SkillsService()
