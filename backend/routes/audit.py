"""
Audit Routes
------------
Endpoints for viewing audit logs.
"""

from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from models.audit_log import AuditLogResponse
from services.audit_service import audit_service

router = APIRouter()


from datetime import datetime, timedelta, timezone

@router.get("/", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = 100,
    user_id: Optional[str] = None,
    device_id: Optional[str] = None,
    action: Optional[str] = None,
    category: Optional[str] = None,
    filter: Optional[str] = "all",
):
    """Query audit logs."""
    since = None
    if filter == "today":
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    elif filter == "7d":
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    elif filter == "30d":
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    return await audit_service.get_logs(
        limit=limit,
        user_id=user_id,
        device_id=device_id,
        action=action,
        category=category,
        since=since
    )


@router.get("/security", response_model=List[AuditLogResponse])
async def get_security_events(limit: int = 20):
    """Get recent security events."""
    return await audit_service.get_security_events(limit)
