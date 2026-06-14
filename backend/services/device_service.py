"""
Device Service
--------------
Business logic for device registration, lifecycle, and status tracking.
"""

import logging
from typing import Optional

from fastapi import HTTPException

from models.device import DeviceModel, DeviceRegister, DeviceHeartbeat, DeviceStatus
from models.audit_log import AuditLogModel, AuditAction, AuditCategory

logger = logging.getLogger(__name__)


class DeviceService:

    @staticmethod
    async def register_device(
        user_id: str,
        data: DeviceRegister,
        ip_address: str = "",
        user_agent: str = ""
    ) -> dict:
        """Register a new device and log the event."""
        try:
            device = await DeviceModel.register(user_id, data)

            await AuditLogModel.log(
                action=AuditAction.DEVICE_REGISTERED,
                category=AuditCategory.DEVICE,
                user_id=user_id,
                device_id=device["id"],
                details={"device_name": data.device_name, "os_type": data.os_type.value},
                ip_address=ip_address,
                user_agent=user_agent
            )

            return device
        except Exception as e:
            logger.error("Failed to register device: %s", e)
            raise HTTPException(status_code=500, detail="Device registration failed")

    @staticmethod
    async def process_heartbeat(
        api_key: str,
        data: DeviceHeartbeat,
        ip_address: str = ""
    ) -> dict:
        """Process heartbeat from a device."""
        device = await DeviceModel.get_by_api_key(api_key)
        if not device:
            raise HTTPException(status_code=401, detail="Invalid API key")

        updated_device = await DeviceModel.heartbeat(device["id"], data)

        # Log heartbeat periodically (not every single one to avoid spam)
        # In a real system, you might throttle these logs.
        # await AuditLogModel.log(
        #     action=AuditAction.DEVICE_HEARTBEAT,
        #     category=AuditCategory.DEVICE,
        #     device_id=device["id"],
        #     user_id=device["user_id"],
        #     ip_address=ip_address
        # )

        return updated_device

    @staticmethod
    async def get_device(device_id: str) -> dict:
        """Get device details."""
        device = await DeviceModel.get_by_id(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return device

    @staticmethod
    async def list_user_devices(user_id: str) -> list[dict]:
        """List all devices for a given user."""
        return await DeviceModel.list_by_user(user_id)

    @staticmethod
    async def unregister_device(
        device_id: str,
        user_id: str,
        ip_address: str = "",
        user_agent: str = ""
    ):
        """Unregister a device."""
        device = await DeviceModel.get_by_id(device_id)
        if not device or device["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Device not found or unauthorized")

        await DeviceModel.unregister(device_id)

        await AuditLogModel.log(
            action=AuditAction.DEVICE_UNREGISTERED,
            category=AuditCategory.DEVICE,
            user_id=user_id,
            device_id=device_id,
            details={"device_name": device.get("device_name")},
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    async def check_stale_devices():
        """Cron job to mark stale devices offline."""
        await DeviceModel.check_stale_devices(timeout_minutes=2)


device_service = DeviceService()
