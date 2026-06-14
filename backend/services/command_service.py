"""
Command Service
---------------
Business logic for command queue management, polling, and execution tracking.
"""

import logging
from typing import Optional

from fastapi import HTTPException

from models.command import CommandModel, CommandCreate, CommandStatus, TrustLevel
from models.execution import ExecutionModel, ExecutionCreate, ExecutionResult, ExecutionStatus
from models.audit_log import AuditLogModel, AuditAction, AuditCategory
from models.voice_profile import VoiceAuthSessionModel
from services.device_service import device_service

logger = logging.getLogger(__name__)


class CommandService:

    @staticmethod
    async def enqueue_command(
        user_id: str,
        data: CommandCreate,
        ip_address: str = "",
        user_agent: str = "",
        session_id: Optional[str] = None
    ) -> dict:
        """Create a new command in the queue."""
        # Check active skill tool whitelists
        if session_id:
            from ai.sqlite_memory import sqlite_memory
            from services.skills_service import skills_service
            active_skill_id = await sqlite_memory.get_active_skill(session_id)
            if active_skill_id:
                allowed = await skills_service.is_tool_allowed(active_skill_id, data.tool)
                if not allowed:
                    logger.warning("Rejected tool command %s because it is blocked under active skill %s", data.tool, active_skill_id)
                    raise HTTPException(
                        status_code=403,
                        detail=f"Tool '{data.tool}' is blocked under active skill '{active_skill_id}'."
                    )

        # Check security block list
        BLOCKED_TOOLS = {"terminal.execute_anything", "powershell.raw_command"}
        if data.tool in BLOCKED_TOOLS:
            logger.warning("Rejected blocked tool command %s", data.tool)
            raise HTTPException(
                status_code=403,
                detail=f"Tool '{data.tool}' is blocked due to security policies."
            )

        # Check voice security shield & session escalations
        voice_verified = False
        if getattr(data, "source", "chat") == "voice":
            trust_level = CommandModel.classify_trust(data.tool)
            if trust_level == TrustLevel.SAFE:
                voice_verified = True
            else:
                if not data.voice_auth_session_id:
                    logger.warning("Voice command %s rejected (missing auth session)", data.tool)
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "இந்தச் செயலுக்கு குரல் சரிபார்ப்பு தேவை.",
                            "code": "voice_verification_required",
                            "tool": data.tool,
                            "trust_level": trust_level
                        }
                    )
                
                # Fetch and validate session
                session = await VoiceAuthSessionModel.get_session(data.voice_auth_session_id)
                if not session:
                    logger.warning("Voice session %s not found or expired", data.voice_auth_session_id)
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "சரிபார்ப்பு அமர்வு காலாவதியானது அல்லது செல்லாதது.",
                            "code": "invalid_session",
                            "tool": data.tool,
                            "trust_level": trust_level
                        }
                    )
                
                # Device binding check (CR-03)
                if session["device_id"] != data.device_id:
                    logger.warning("Voice session device mismatch: expected %s, got %s", session["device_id"], data.device_id)
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "சரிபார்ப்பு அமர்வு இந்த சாதனத்துடன் பொருந்தவில்லை.",
                            "code": "device_mismatch",
                            "tool": data.tool,
                            "trust_level": trust_level
                        }
                    )
                
                # Command scoping check (CR-01)
                if session["command_scope"] != data.tool:
                    logger.warning("Voice session tool mismatch: expected %s, got %s", session["command_scope"], data.tool)
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "சரிபார்ப்பு அமர்வு இந்த கட்டளையுடன் பொருந்தவில்லை.",
                            "code": "scope_mismatch",
                            "tool": data.tool,
                            "trust_level": trust_level
                        }
                    )
                
                # User binding check
                if session["user_id"] != user_id:
                    logger.warning("Voice session user mismatch: expected %s, got %s", session["user_id"], user_id)
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "பயனர் சரிபார்ப்பு தோல்வி.",
                            "code": "user_mismatch",
                            "tool": data.tool,
                            "trust_level": trust_level
                        }
                    )
                
                # Single-use check (CR-02)
                if session["used"] == 1:
                    logger.warning("Voice session %s already used", data.voice_auth_session_id)
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "சரிபார்ப்பு அமர்வு ஏற்கனவே பயன்படுத்தப்பட்டுவிட்டது.",
                            "code": "session_already_used",
                            "tool": data.tool,
                            "trust_level": trust_level
                        }
                    )
                
                # Escalate policy checks
                if trust_level == TrustLevel.CAUTION:
                    if session["challenge_status"] != "passed":
                        logger.warning("Voice session %s challenge not passed", data.voice_auth_session_id)
                        raise HTTPException(
                            status_code=403,
                            detail={
                                "message": "இந்தச் செயலுக்கு எண்களைக் கூறி உறுதிப்படுத்துவது தேவை.",
                                "code": "challenge_required",
                                "tool": data.tool,
                                "trust_level": trust_level
                            }
                        )
                elif trust_level == TrustLevel.DANGEROUS:
                    if session["verification_status"] != "passed" or session["challenge_status"] != "passed":
                        logger.warning("Voice session %s biometric or challenge not passed", data.voice_auth_session_id)
                        raise HTTPException(
                            status_code=403,
                            detail={
                                "message": "இந்தச் செயலுக்கு குரல் சரிபார்ப்பு மற்றும் எண்களைக் கூறி உறுதிப்படுத்துவது தேவை.",
                                "code": "biometric_and_challenge_required",
                                "tool": data.tool,
                                "trust_level": trust_level
                            }
                        )
                
                # Verify and mark used atomically
                success = await VoiceAuthSessionModel.mark_used(data.voice_auth_session_id)
                if not success:
                    logger.warning("Voice session %s consumption failed due to concurrent reuse.", data.voice_auth_session_id)
                    raise HTTPException(
                        status_code=403,
                        detail="சரிபார்ப்பு அமர்வு ஏற்கனவே பயன்படுத்தப்பட்டுவிட்டது."
                    )
                voice_verified = True

        # Verify device exists and belongs to user
        device = await device_service.get_device(data.device_id)
        if device["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized for this device")

        # Step 8.5: Capability Negotiation
        capabilities = device.get("capabilities", [])
        if data.tool not in capabilities and data.tool != "chat":
            logger.warning("Device %s rejected tool %s (not in capabilities)", data.device_id, data.tool)
            raise HTTPException(
                status_code=400, 
                detail=f"Device does not support the requested tool '{data.tool}'. Supported: {capabilities}"
            )

        command = await CommandModel.create(user_id, data, voice_verified=voice_verified)

        audit_details = {
            "command_id": command["id"], 
            "tool": data.tool, 
            "status": command["status"]
        }
        if data.voice_auth_session_id:
            audit_details["auth_session_id"] = data.voice_auth_session_id

        await AuditLogModel.log(
            action=AuditAction.COMMAND_CREATED,
            category=AuditCategory.COMMAND,
            user_id=user_id,
            device_id=data.device_id,
            details=audit_details,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return command

    @staticmethod
    async def poll_commands(api_key: str, limit: int = 10) -> list[dict]:
        """Agent polls for commands."""
        # Authenticate device
        from models.device import DeviceModel
        device = await DeviceModel.get_by_api_key(api_key)
        if not device:
            raise HTTPException(status_code=401, detail="Invalid API key")

        return await CommandModel.poll_pending(device["id"], limit)

    @staticmethod
    async def report_execution_start(
        api_key: str,
        data: ExecutionCreate
    ) -> dict:
        """Agent reports that it started executing a command."""
        from models.device import DeviceModel
        device = await DeviceModel.get_by_api_key(api_key)
        if not device or device["id"] != data.device_id:
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Verify command
        command = await CommandModel.get_by_id(data.command_id)
        if not command or command["device_id"] != device["id"]:
            raise HTTPException(status_code=404, detail="Command not found")

        if command["status"] not in (CommandStatus.PENDING.value, CommandStatus.APPROVED.value):
            raise HTTPException(status_code=400, detail=f"Command is in state {command['status']}")

        # Create execution record
        execution = await ExecutionModel.create(data)

        # Update command status
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await CommandModel.update_status(
            command_id=data.command_id,
            status=CommandStatus.EXECUTING,
            executed_at=now
        )

        await AuditLogModel.log(
            action=AuditAction.COMMAND_EXECUTED,
            category=AuditCategory.COMMAND,
            user_id=command["user_id"],
            device_id=device["id"],
            details={"command_id": command["id"], "execution_id": execution["id"]}
        )

        return execution

    @staticmethod
    async def report_execution_result(
        api_key: str,
        data: ExecutionResult
    ) -> dict:
        """Agent reports the result of an execution."""
        from models.device import DeviceModel
        device = await DeviceModel.get_by_api_key(api_key)
        if not device:
            raise HTTPException(status_code=401, detail="Unauthorized")

        execution = await ExecutionModel.get_by_id(data.execution_id)
        if not execution or execution["device_id"] != device["id"]:
            raise HTTPException(status_code=404, detail="Execution not found")

        # Complete execution
        updated_exec = await ExecutionModel.complete(data)

        # Update command status
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cmd_status = CommandStatus.COMPLETED
        if data.status == ExecutionStatus.ERROR:
            cmd_status = CommandStatus.FAILED
        elif data.status == ExecutionStatus.TIMEOUT:
            cmd_status = CommandStatus.TIMEOUT

        await CommandModel.update_status(
            command_id=execution["command_id"],
            status=cmd_status,
            completed_at=now
        )

        # Audit log
        action = AuditAction.COMMAND_COMPLETED if data.status == ExecutionStatus.SUCCESS else AuditAction.COMMAND_FAILED
        await AuditLogModel.log(
            action=action,
            category=AuditCategory.COMMAND,
            device_id=device["id"],
            details={
                "command_id": execution["command_id"],
                "execution_id": data.execution_id,
                "status": data.status.value,
                "error_message": data.error_message,
                "result": data.result
            }
        )

        return updated_exec

    @staticmethod
    async def get_command_history(
        user_id: str,
        device_id: Optional[str] = None,
        limit: int = 50
    ) -> list[dict]:
        """Get command history for a user."""
        return await CommandModel.history(user_id, limit, device_id)


command_service = CommandService()
