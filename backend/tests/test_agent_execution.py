import pytest
import asyncio
from unittest.mock import patch
import sys
import os

# Add repo root and agent directories to path so agent package and its internal modules can be imported
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
agent_dir = os.path.join(repo_root, "agent")
if repo_root not in sys.path:
    sys.path.append(repo_root)
if agent_dir not in sys.path:
    sys.path.append(agent_dir)

# We don't want to actually execute commands on the dev machine during tests, 
# so we mock the registry and subprocess calls.

@pytest.mark.asyncio
async def test_agent_execution_success_schema():
    from agent.actions.registry import action_registry
    
    # Mock an action
    @action_registry.register("test.success")
    async def mock_success(params):
        return {
            "success": True,
            "tool": "test.success",
            "message": "It worked",
            "data": {"value": 42}
        }
        
    handler = action_registry.get_handler("test.success")
    result = await handler({})
    
    assert result["success"] is True
    assert result["tool"] == "test.success"
    assert result["message"] == "It worked"
    assert result["data"]["value"] == 42

@pytest.mark.asyncio
async def test_agent_execution_failure_schema():
    from agent.actions.app_control import open_app
    
    # Execute with invalid OS or app to trigger failure
    with patch("agent.actions.app_control.get_os_type", return_value="unknown_os"):
        result = await open_app({"app": "vscode"})
        
        assert result["success"] is False
        assert result["tool"] == "desktop.open_app"
        assert "error" in result
        assert "not implemented" in result["error"]
