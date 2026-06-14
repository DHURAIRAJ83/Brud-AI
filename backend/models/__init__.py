"""
Tamil AI Assistant — Database Models
--------------------------------------
Async SQLite models for device management, command queue,
execution tracking, and audit logging.

Android-compatible schema design from Day 1.
"""

from models.base import db_manager
from models.device import DeviceModel, DeviceStatus, OSType
from models.command import CommandModel, CommandStatus
from models.execution import ExecutionModel, ExecutionStatus
from models.audit_log import AuditLogModel, AuditAction
from models.user import UserModel, UserRole

__all__ = [
    "db_manager",
    "DeviceModel", "DeviceStatus", "OSType",
    "CommandModel", "CommandStatus",
    "ExecutionModel", "ExecutionStatus",
    "AuditLogModel", "AuditAction",
    "UserModel", "UserRole",
]
