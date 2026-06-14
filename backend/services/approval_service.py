"""
Approval Service
----------------
Handles user approvals for CAUTION and DANGEROUS actions.
"""

import logging
from fastapi import HTTPException

from models.command import CommandModel, CommandApproval, CommandStatus
from models.audit_log import AuditLogModel, AuditAction, AuditCategory

logger = logging.getLogger(__name__)


class ApprovalService:

    @staticmethod
    async def get_pending_approvals(user_id: str) -> list[dict]:
        """Get list of commands awaiting user approval."""
        return await CommandModel.get_awaiting_approval(user_id)

    @staticmethod
    async def process_approval(
        user_id: str,
        command_id: str,
        approval: CommandApproval,
        ip_address: str = "",
        user_agent: str = ""
    ) -> dict:
        """Approve or reject a command."""
        command = await CommandModel.get_by_id(command_id)

        if not command:
            raise HTTPException(status_code=404, detail="Command not found")

        if command["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to approve this command")

        if command["status"] != CommandStatus.AWAITING_APPROVAL.value:
            raise HTTPException(status_code=400, detail=f"Command is not awaiting approval (status: {command['status']})")

        from models.base import db_manager

        if approval.approved:
            updated_cmd = await CommandModel.approve(command_id, approval.approved_by)
            action = AuditAction.COMMAND_APPROVED
            # Bulk approve other sub-steps in the same decomposed command
            await db_manager.execute(
                """UPDATE commands
                   SET status = ?, approved_by = ?, approved_at = ?
                   WHERE user_id = ? AND raw_input = ? AND status = ? AND id != ?""",
                (CommandStatus.APPROVED.value, approval.approved_by, updated_cmd.get("approved_at"), user_id, command["raw_input"], CommandStatus.AWAITING_APPROVAL.value, command_id)
            )
        else:
            updated_cmd = await CommandModel.reject(command_id)
            action = AuditAction.COMMAND_REJECTED
            # Bulk reject other sub-steps
            await db_manager.execute(
                """UPDATE commands
                   SET status = ?
                   WHERE user_id = ? AND raw_input = ? AND status = ? AND id != ?""",
                (CommandStatus.REJECTED.value, user_id, command["raw_input"], CommandStatus.AWAITING_APPROVAL.value, command_id)
            )

        await AuditLogModel.log(
            action=action,
            category=AuditCategory.COMMAND,
            user_id=user_id,
            device_id=command["device_id"],
            details={"command_id": command_id, "tool": command["tool"]},
            ip_address=ip_address,
            user_agent=user_agent
        )

        return updated_cmd


approval_service = ApprovalService()
