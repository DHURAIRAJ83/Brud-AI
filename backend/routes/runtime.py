"""
Runtime Routes — Phase 4: Hybrid AI Runtime System
----------------------------------------------------
Endpoints:
  GET  /api/runtime/status  — current runtime status
  POST /api/runtime/mode    — switch mode (local/cloud/hybrid)
  GET  /api/models          — list available models on local + cloud
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.runtime_manager import runtime_manager, RuntimeMode

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SetModeRequest(BaseModel):
    mode: str   # "local" | "cloud" | "hybrid"


class SetModelRequest(BaseModel):
    model: str  # "tinyllama" | "mistral" | "llama3" | "qwen2.5:3b"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/runtime/status", summary="Get current AI runtime status")
async def runtime_status():
    """
    Returns the current runtime mode, active runtime,
    local/cloud availability, active model, and failover count.
    """
    status = await runtime_manager.get_runtime()
    return {
        "mode":            status["mode"],
        "runtime":         status["runtime"],
        "local_available": status["local_available"],
        "cloud_available": status["cloud_available"],
        "active_model":    status["active_model"],
        "failover_count":  status["failover_count"],
    }


@router.post("/runtime/mode", summary="Switch AI runtime mode")
async def set_runtime_mode(body: SetModeRequest):
    """
    Switch the AI runtime mode.

    Modes:
    - `local`  — use only local Ollama
    - `cloud`  — use only cloud/VPS Ollama
    - `hybrid` — try local first, fall back to cloud (recommended)
    """
    try:
        mode = RuntimeMode(body.mode.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{body.mode}'. Must be: local, cloud, or hybrid.",
        )
    status = await runtime_manager.switch_runtime(mode)
    return {
        "message": f"Runtime mode switched to '{mode.value}'.",
        **{k: status[k] for k in ("mode", "runtime", "local_available", "cloud_available")},
    }


@router.post("/runtime/model", summary="Override active AI model")
async def set_active_model(body: SetModelRequest):
    """Set a specific model as the active model (overrides auto-routing)."""
    valid = {"tinyllama", "mistral", "llama3", "qwen2.5:3b"}
    if body.model not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{body.model}'. Must be one of: {', '.join(sorted(valid))}.",
        )
    await runtime_manager.set_active_model(body.model)
    return {"message": f"Active model set to '{body.model}'.", "model": body.model}


@router.get("/models", summary="List available AI models (local + cloud)")
async def list_models():
    """
    Returns models available on local Ollama and cloud Ollama.

    Example response:
    ```json
    {
      "local": ["tinyllama", "mistral"],
      "cloud": ["tinyllama", "mistral", "llama3", "qwen2.5:3b"]
    }
    ```
    """
    models = await runtime_manager.list_models()
    # Re-probe to get fresh data
    await runtime_manager.check_local()
    await runtime_manager.check_cloud()
    return await runtime_manager.list_models()


@router.post("/runtime/refresh", summary="Force re-probe of all AI endpoints")
async def refresh_runtime():
    """Manually trigger a re-probe of local and cloud Ollama endpoints."""
    await runtime_manager.check_local()
    await runtime_manager.check_cloud()
    status = await runtime_manager.get_runtime()
    return {
        "message": "Runtime endpoints re-probed.",
        "mode":            status["mode"],
        "runtime":         status["runtime"],
        "local_available": status["local_available"],
        "cloud_available": status["cloud_available"],
        "active_model":    status["active_model"],
        "failover_count":  status["failover_count"],
    }
