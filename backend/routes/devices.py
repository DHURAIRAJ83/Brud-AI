"""
Device Routes
-------------
Endpoints for device registration, heartbeat, and management.
"""

from fastapi import APIRouter, Depends, Request, Header
from typing import List

from models.device import DeviceRegister, DeviceResponse, DeviceHeartbeat
from services.device_service import device_service

router = APIRouter()

# Dependency to get current user ID (mocked for now, assuming security middleware sets it)
def get_current_user_id(request: Request) -> str:
    # In a real app, this comes from the auth token/session.
    # For now, we'll use a hardcoded dev user or extract from a header if provided.
    return request.headers.get("X-User-Id", "admin-user-123")


@router.post("/register", response_model=DeviceResponse)
async def register_device(
    data: DeviceRegister,
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """Register a new device and get an API key."""
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    return await device_service.register_device(user_id, data, ip, ua)


@router.post("/heartbeat", response_model=DeviceResponse)
async def device_heartbeat(
    data: DeviceHeartbeat,
    request: Request,
    x_api_key: str = Header(..., description="Device API Key")
):
    """Agent heartbeat to stay online."""
    ip = request.client.host if request.client else ""
    return await device_service.process_heartbeat(x_api_key, data, ip)


@router.get("/list", response_model=List[DeviceResponse])
async def list_devices(user_id: str = Depends(get_current_user_id)):
    """List all registered devices for the current user."""
    return await device_service.list_user_devices(user_id)


@router.delete("/{device_id}")
async def unregister_device(
    device_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """Unregister a device."""
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    await device_service.unregister_device(device_id, user_id, ip, ua)
    return {"status": "success", "message": "Device unregistered"}

@router.get("/status", summary="Get explicit device statuses")
async def get_device_statuses(user_id: str = Depends(get_current_user_id)):
    """Get all devices for user with computed ONLINE/OFFLINE status (<60s heartbeat)."""
    from models.base import db_manager
    rows = await db_manager.fetch_all(
        """SELECT 
            id, device_name, device_type, agent_version,
            CASE 
                WHEN status = 'online' AND datetime(last_heartbeat, '+60 seconds') >= datetime('now') THEN 'ONLINE'
                ELSE 'OFFLINE'
            END as computed_status,
            last_heartbeat
           FROM devices 
           WHERE user_id = ?
           ORDER BY registered_at DESC""",
        (user_id,)
    )
    return rows
