"""
Unit Tests for Desktop Agent Actions
------------------------------------
Verifies action registry registration and fallback behavior of vscode integration.
"""

import asyncio
import os
import pytest
from unittest.mock import patch, AsyncMock

from actions.registry import action_registry
import actions.vscode_integration
from config import get_settings

settings = get_settings()

@pytest.mark.asyncio
async def test_vscode_open_file_fallback():
    # Test fallback to preview content when CLI and WS are offline
    test_file = "test_temp_open.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("Line 1\nLine 2\nLine 3")
    
    try:
        # Mock status check to return connected=False
        with patch("actions.vscode_integration._check_extension_connected", return_value=(False, None)):
            # Mock subprocess run to fail or raise exception
            with patch("subprocess.run", side_effect=Exception("no code command")):
                with patch("os.startfile", side_effect=Exception("no startfile")):
                    res = await action_registry.get_handler("vscode.open_file")({"file_path": test_file})
                    assert res["success"] is True
                    assert "preview" in res["message"].lower()
                    assert "Line 1" in res["data"]["content_preview"]
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

@pytest.mark.asyncio
async def test_vscode_search_code_fallback():
    with patch("actions.vscode_integration._check_extension_connected", return_value=(False, None)):
        # Mock indexer API call to fail
        with patch("httpx.AsyncClient.get", side_effect=Exception("backend offline")):
            res = await action_registry.get_handler("vscode.search_code")({"query": "main.py"})
            assert res["success"] is True
            assert "fallback" in res["data"]
            assert res["data"]["fallback"] == "local_directory_scan"

@pytest.mark.asyncio
async def test_vscode_create_project_local():
    test_dir = "test_project_temp_xyz"
    try:
        with patch("actions.vscode_integration._check_extension_connected", return_value=(False, None)):
            res = await action_registry.get_handler("vscode.create_project")({"project_name": test_dir})
            assert res["success"] is True
            assert os.path.exists(test_dir)
            assert res["data"]["fallback"] == "local_os"
    finally:
        if os.path.exists(test_dir):
            os.rmdir(test_dir)
