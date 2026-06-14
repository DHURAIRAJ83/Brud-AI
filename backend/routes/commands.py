"""
Command Routes
--------------
Endpoints for creating commands, polling (agent), reporting results, and approvals.
"""

from fastapi import APIRouter, Depends, Request, Header
from typing import List

from models.command import CommandCreate, CommandResponse, CommandApproval
from models.execution import ExecutionCreate, ExecutionResult, ExecutionResponse
from services.command_service import command_service
from services.approval_service import approval_service

router = APIRouter()

def get_current_user_id(request: Request) -> str:
    return request.headers.get("X-User-Id", "admin-user-123")


# ── Chat/User facing ──────────────────────────────────────────────────────────

@router.post("/create", response_model=CommandResponse)
async def create_command(
    data: CommandCreate,
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """Create a new command in the queue."""
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    return await command_service.enqueue_command(user_id, data, ip, ua)


@router.get("/history", response_model=List[CommandResponse])
async def get_command_history(
    device_id: str = None,
    limit: int = 50,
    user_id: str = Depends(get_current_user_id)
):
    """Get history of commands."""
    return await command_service.get_command_history(user_id, device_id, limit)


@router.get("/", response_model=List[CommandResponse])
async def get_all_commands(
    limit: int = 100,
    user_id: str = Depends(get_current_user_id)
):
    """Admin/Dashboard: Get all commands."""
    return await command_service.get_command_history(user_id, None, limit)


@router.get("/activity")
async def get_live_activity(
    limit: int = 50,
    user_id: str = Depends(get_current_user_id)
):
    """Dashboard: Get live activity feed combining commands and executions."""
    # For now, just return latest commands as activity. 
    # In a real app, you might join with executions table.
    cmds = await command_service.get_command_history(user_id, None, limit)
    return [cmd.dict() for cmd in cmds]


# ── Approvals ─────────────────────────────────────────────────────────────────

@router.get("/pending-approvals", response_model=List[CommandResponse])
async def get_pending_approvals(user_id: str = Depends(get_current_user_id)):
    """Get commands awaiting user approval (CAUTION/DANGEROUS)."""
    return await approval_service.get_pending_approvals(user_id)


@router.post("/{command_id}/approve", response_model=CommandResponse)
async def approve_command(
    command_id: str,
    approval: CommandApproval,
    request: Request,
    user_id: str = Depends(get_current_user_id)
):
    """Approve or reject a command."""
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    return await approval_service.process_approval(user_id, command_id, approval, ip, ua)


# ── Agent facing (Requires Device API Key) ────────────────────────────────────

@router.get("/poll", response_model=List[CommandResponse])
async def poll_commands(
    limit: int = 10,
    x_api_key: str = Header(..., description="Device API Key")
):
    """Agent polls for pending commands."""
    return await command_service.poll_commands(x_api_key, limit)


@router.post("/execution/start", response_model=ExecutionResponse)
async def report_execution_start(
    data: ExecutionCreate,
    x_api_key: str = Header(..., description="Device API Key")
):
    """Agent reports execution started."""
    return await command_service.report_execution_start(x_api_key, data)


@router.post("/execution/result", response_model=ExecutionResponse)
async def report_execution_result(
    data: ExecutionResult,
    x_api_key: str = Header(..., description="Device API Key")
):
    """Agent reports execution result."""
    return await command_service.report_execution_result(x_api_key, data)
