"""
Metrics Route — GET /api/metrics
"""

from fastapi import APIRouter
from services.observability import obs_service
from services.monetization import monetization
from ai.model_router import model_router
from tools.tool_engine import plugin_registry

router = APIRouter()


@router.get("/metrics", summary="System observability dashboard")
async def metrics():
    """Full metrics endpoint for admin dashboard."""
    return {
        "system": obs_service.get_metrics(),
        "plugins": plugin_registry.list_plugins(),
        "model_routing": {
            "override_active": model_router._overridden_model is not None,
            "current_override": model_router._overridden_model,
        },
        "usage": monetization.get_usage_summary(),
    }


@router.get("/metrics/errors", summary="Recent error log")
async def recent_errors():
    return {"errors": obs_service.get_recent_errors(20)}


@router.post("/metrics/model-override", summary="Force a specific model for all requests")
async def set_model_override(model: str | None = None):
    """
    Set or clear the model override.
    - model=None → clear override (use dynamic routing)
    - model='tinyllama' → force TinyLlama for all
    """
    model_router.set_override(model)
    return {
        "message": f"Override set to '{model}'" if model else "Override cleared",
        "current_override": model_router._overridden_model,
    }
