import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_command_service_poll():
    from services.command_service import command_service
    
    mock_device = {"id": "dev_123", "user_id": "user_123"}
    mock_commands = [
        {"id": "cmd_1", "status": "pending"},
        {"id": "cmd_2", "status": "approved"}
    ]
    
    with patch("models.device.DeviceModel.get_by_api_key", return_value=mock_device):
        with patch("models.command.CommandModel.poll_pending", return_value=mock_commands):
            results = await command_service.poll_commands("valid_api_key")
            assert len(results) == 2
            assert results[0]["id"] == "cmd_1"

@pytest.mark.asyncio
async def test_command_service_execution_start():
    from services.command_service import command_service
    from models.execution import ExecutionCreate
    
    mock_device = {"id": "dev_123", "user_id": "user_123"}
    mock_command = {"id": "cmd_1", "device_id": "dev_123", "status": "pending", "user_id": "user_123"}
    mock_execution = {"id": "exec_1"}
    
    with patch("models.device.DeviceModel.get_by_api_key", return_value=mock_device):
        with patch("models.command.CommandModel.get_by_id", return_value=mock_command):
            with patch("models.execution.ExecutionModel.create", return_value=mock_execution):
                with patch("models.command.CommandModel.update_status") as mock_update:
                    with patch("models.audit_log.AuditLogModel.log"):
                        
                        data = ExecutionCreate(command_id="cmd_1", device_id="dev_123")
                        result = await command_service.report_execution_start("api_key", data)
                        
                        assert result["id"] == "exec_1"
                        mock_update.assert_called_once()
