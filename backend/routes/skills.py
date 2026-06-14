"""
Skills Router
-------------
REST endpoints for the AI Skills System (Marketplace).
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from services.skills_service import skills_service
from ai.sqlite_memory import sqlite_memory

router = APIRouter()

# ── Pydantic Request/Response Models ──────────────────────────────────────────

class SkillCreateSchema(BaseModel):
    id: str = Field(..., description="Unique skill ID (slug, e.g. fastapi-expert)")
    name: str = Field(..., description="Display name of the skill")
    description: str = Field("", description="Short description")
    category: str = Field("General", description="Marketplace category (Developer, Teacher, etc.)")
    system_prompt: str = Field(..., description="System instructions/personality for the LLM")
    model: str = Field("auto", description="Model override, e.g. qwen2.5-coder")
    tools: Dict[str, List[str]] = Field(
        default_factory=lambda: {"allow": [], "deny": []},
        description="JSON dict containing allowed/denied tools"
    )
    memory_scope: List[str] = Field(
        default_factory=lambda: ["project_context"],
        description="Namespace list for vector search context"
    )
    parent_skill_id: Optional[str] = Field(None, description="Parent skill ID to inherit from")
    voice_profile: Optional[str] = Field(None, description="Voice profile ID/name for the skill")

class SkillActivationSchema(BaseModel):
    session_id: str = Field(..., description="Conversation session ID")
    skill_id: Optional[str] = Field(None, description="Skill ID to activate, or null to deactivate")

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", summary="Get all skills")
async def list_skills():
    """List all available seed and custom skills."""
    try:
        return await skills_service.get_all_skills()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{skill_id}", summary="Get a resolved skill")
async def get_skill(skill_id: str):
    """Retrieve settings for a skill, resolving its inheritance path."""
    resolved = await skills_service.get_resolved_skill(skill_id)
    if not resolved:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return resolved

@router.post("", summary="Create or update a skill")
async def create_skill(data: SkillCreateSchema):
    """Create a new custom skill profile or update an existing one (saves version increment)."""
    try:
        # Prevent overwriting builtin seed skills
        existing = await skills_service.get_skill(data.id)
        if existing and existing.get("is_builtin"):
            raise HTTPException(status_code=403, detail="Cannot modify builtin default skills")

        skill = await skills_service.create_skill(
            skill_id=data.id,
            name=data.name,
            description=data.description,
            category=data.category,
            system_prompt=data.system_prompt,
            model=data.model,
            tools=data.tools,
            memory_scope=data.memory_scope,
            parent_skill_id=data.parent_skill_id,
            voice_profile=data.voice_profile
        )
        return {"success": True, "message": f"Successfully saved skill '{data.id}'", "skill": skill}
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{skill_id}", summary="Delete custom skill")
async def delete_skill(skill_id: str):
    """Remove a custom skill profile."""
    try:
        deleted = await skills_service.delete_skill(skill_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
        return {"success": True, "message": f"Successfully deleted skill '{skill_id}'"}
    except PermissionError as perm_err:
        raise HTTPException(status_code=403, detail=str(perm_err))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/activate", summary="Activate skill in session")
async def activate_skill(data: SkillActivationSchema):
    """Set the active skill profile for a chat session."""
    try:
        if data.skill_id:
            skill = await skills_service.get_skill(data.skill_id)
            if not skill:
                raise HTTPException(status_code=404, detail=f"Skill '{data.skill_id}' does not exist")

        await sqlite_memory.set_active_skill(data.session_id, data.skill_id)

        from routes.stream import system_events_manager
        await system_events_manager.broadcast({
            "event": "skill_changed",
            "session_id": data.session_id,
            "active_skill_id": data.skill_id
        })

        return {
            "success": True,
            "message": f"Activated skill '{data.skill_id}' in session '{data.session_id}'" if data.skill_id else f"Deactivated skill in session '{data.session_id}'",
            "active_skill_id": data.skill_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
