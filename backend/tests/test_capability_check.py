import pytest
import asyncio
from unittest.mock import patch, MagicMock

from models.device import DeviceModel
from models.command import CommandModel, CommandStatus
from models.user import UserModel
from services.command_service import command_service
from pydantic import BaseModel

# Mocking the DB since it's an integration test.
# For unit tests, we'd use an in-memory SQLite, but here we just test logic.

class DummyDevice(BaseModel):
    id: str = "dev_123"
    user_id: str = "user_123"
    capabilities: list = ["desktop.open_app"]

@pytest.mark.asyncio
async def test_capability_check_rejection():
    # Setup mock data
    mock_device = {
        "id": "dev_123",
        "user_id": "user_123",
        "capabilities": ["desktop.open_app", "files.list"]
    }
    
    with patch("services.device_service.DeviceService.get_device", return_value=mock_device):
        # We try to use "screen.capture" which is NOT in capabilities
        from models.command import CommandCreate
        from fastapi import HTTPException
        
        cmd_data = CommandCreate(
            device_id="dev_123",
            tool="screen.capture"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await command_service.enqueue_command("user_123", cmd_data)
            
        assert exc_info.value.status_code == 400
        assert "Device does not support the requested tool" in exc_info.value.detail

@pytest.mark.asyncio
async def test_capability_check_approval():
    # Setup mock data
    mock_device = {
        "id": "dev_123",
        "user_id": "user_123",
        "capabilities": ["desktop.open_app"]
    }
    mock_command = {"id": "cmd_123", "status": "pending"}
    
    with patch("services.device_service.DeviceService.get_device", return_value=mock_device):
        with patch("models.command.CommandModel.create", return_value=mock_command):
            with patch("models.audit_log.AuditLogModel.log", return_value=None):
                from models.command import CommandCreate
                
                cmd_data = CommandCreate(
                    device_id="dev_123",
                    tool="desktop.open_app"
                )
                
                result = await command_service.enqueue_command("user_123", cmd_data)
                assert result["id"] == "cmd_123"
