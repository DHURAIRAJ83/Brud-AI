"""
Audit Service
-------------
Provides querying and aggregation logic for audit logs.
"""

import logging
from typing import Optional

from models.audit_log import AuditLogModel

logger = logging.getLogger(__name__)


class AuditService:

    @staticmethod
    async def get_logs(
        limit: int = 100,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        action: Optional[str] = None,
        category: Optional[str] = None,
        since: Optional[str] = None,
    ) -> list[dict]:
        """Retrieve audit logs."""
        return await AuditLogModel.query(
            limit=limit,
            user_id=user_id,
            device_id=device_id,
            action=action,
            category=category,
            since=since
        )

    @staticmethod
    async def get_security_events(limit: int = 20) -> list[dict]:
        """Retrieve recent security-related events."""
        return await AuditLogModel.recent_security_events(limit)


audit_service = AuditService()
