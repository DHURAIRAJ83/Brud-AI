import sys
import os
import glob
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException

# 1. Import backend components first
from main import app
from models.command import CommandModel, TrustLevel, CommandCreate
from services.command_service import command_service

# 2. Append agent path to the END of sys.path to avoid collisions
agent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "agent"))
if agent_path not in sys.path:
    sys.path.append(agent_path)

# 3. Swap config module during actions import to mock AgentSettings
mock_config = MagicMock()
mock_settings = MagicMock()
mock_settings.vps_url = "http://test"
mock_settings.api_key = "test-key"
mock_config.get_settings.return_value = mock_settings

original_config = sys.modules.get("config")
sys.modules["config"] = mock_config

try:
    from actions.registry import action_registry
    import actions.coding_agent
    import actions.git_control
finally:
    if original_config:
        sys.modules["config"] = original_config
    else:
        del sys.modules["config"]


@pytest_asyncio.fixture(scope="module")
async def test_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_coding_and_git_trust_levels():
    """Verify that coding and git actions are mapped to correct trust levels."""
    assert CommandModel.classify_trust("coding.read_code") == TrustLevel.SAFE
    assert CommandModel.classify_trust("coding.run_tests") == TrustLevel.SAFE
    assert CommandModel.classify_trust("coding.explain_code") == TrustLevel.SAFE
    assert CommandModel.classify_trust("coding.search_symbol") == TrustLevel.SAFE
    assert CommandModel.classify_trust("coding.analyze_project") == TrustLevel.SAFE
    
    assert CommandModel.classify_trust("coding.create_project") == TrustLevel.CAUTION
    assert CommandModel.classify_trust("coding.write_code") == TrustLevel.CAUTION
    assert CommandModel.classify_trust("coding.restore_backup") == TrustLevel.CAUTION
    assert CommandModel.classify_trust("git.commit") == TrustLevel.CAUTION
    
    assert CommandModel.classify_trust("git.push") == TrustLevel.DANGEROUS


@pytest.mark.asyncio
async def test_scope_protection_and_whitelists():
    """Verify scope containment, extension check whitelists, and payload write limits."""
    # 1. Scope Containment Check
    res_read = await action_registry.get_handler("coding.read_code")({"file_path": "../../../sensitive.txt"})
    assert res_read["success"] is False
    assert "outside project root" in res_read["error"]

    res_write = await action_registry.get_handler("coding.write_code")({"file_path": "../../../hacked.py", "content": "print()"})
    assert res_write["success"] is False
    assert "outside project root" in res_write["error"]

    # 2. Whitelist File Extension Check
    res_ext = await action_registry.get_handler("coding.write_code")({"file_path": "malicious.exe", "content": "abc"})
    assert res_ext["success"] is False
    assert "extension" in res_ext["error"]

    # 3. Payload Write Size Limit Check
    large_payload = "a" * 1_000_005
    res_size = await action_registry.get_handler("coding.write_code")({"file_path": "large.py", "content": large_payload})
    assert res_size["success"] is False
    assert "payload size exceeds" in res_size["error"]


@pytest.mark.asyncio
async def test_write_backup_and_restore():
    """Verify file backup operations, retention policy checks, and rollback restores."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    test_file = os.path.join(project_root, "test_back_rest.py")
    backups_dir = os.path.join(project_root, ".backups")
    
    try:
        # Write initial code
        res1 = await action_registry.get_handler("coding.write_code")({
            "file_path": test_file,
            "content": "print('v1')"
        })
        assert res1["success"] is True

        # Write secondary code (triggers backup)
        res2 = await action_registry.get_handler("coding.write_code")({
            "file_path": test_file,
            "content": "print('v2')"
        })
        assert res2["success"] is True

        # Verify backup file exists
        assert os.path.exists(backups_dir)
        backups = glob.glob(os.path.join(backups_dir, "test_back_rest_*.py"))
        assert len(backups) >= 1

        # Run dry-run restore diff preview
        res_preview = await action_registry.get_handler("coding.restore_backup")({
            "file_path": test_file,
            "dry_run": True
        })
        assert res_preview["success"] is True
        assert "v1" in res_preview["data"]["diff"]
        assert "v2" in res_preview["data"]["diff"]

        # Run actual restore
        res_restore = await action_registry.get_handler("coding.restore_backup")({
            "file_path": test_file,
            "dry_run": False
        })
        assert res_restore["success"] is True
        
        # Verify code is reverted to v1
        with open(test_file, "r") as f:
            restored_code = f.read()
        assert restored_code == "print('v1')"

    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
        # Clean up mock backups for this file
        pattern = os.path.join(backups_dir, "test_back_rest_*.py")
        for f in glob.glob(pattern):
            try:
                os.remove(f)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_git_dry_run():
    """Verify git commit dry run correctly calculates diff stats."""
    mock_status = b"M main.py\n"
    mock_diff = b" main.py | 5 +----\n 1 file changed, 1 insertion(+), 4 deletions(-)\n"

    with patch("asyncio.create_subprocess_shell") as mock_shell:
        proc1 = AsyncMock()
        proc1.communicate.return_value = (mock_status, b"")
        proc1.returncode = 0
        
        proc2 = AsyncMock()
        proc2.communicate.return_value = (mock_diff, b"")
        proc2.returncode = 0

        mock_shell.side_effect = [proc1, proc2]

        res = await action_registry.get_handler("git.commit")({
            "message": "test commit",
            "dry_run": True
        })
        assert res["success"] is True
        assert res["data"]["dry_run"] is True
        assert res["data"]["files_changed"] == 1
        assert res["data"]["insertions"] == 1
        assert res["data"]["deletions"] == 4


@pytest.mark.asyncio
async def test_explain_code_via_api():
    """Verify code explanation LLM query dispatching and response handling."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    test_file = os.path.join(project_root, "test_explain.py")
    with open(test_file, "w") as f:
        f.write("def dummy(): pass")

    try:
        # Mock chat response
        mock_response = {"response": "விளக்கம்: இது ஒரு dummy function", "intent": "chat"}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = mock_response
            mock_post.return_value = resp

            res = await action_registry.get_handler("coding.explain_code")({"file_path": test_file})
            assert res["success"] is True
            assert "dummy" in res["data"]["explanation"]
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)


@pytest.mark.asyncio
async def test_project_analysis_locally():
    """Verify local files analysis (test counts, route detection, packages)."""
    res = await action_registry.get_handler("coding.analyze_project")({})
    assert res["success"] is True
    data = res["data"]
    assert "framework" in data
    assert "database" in data
    assert "tests" in data
    assert "routes" in data
    assert data["tests"] >= 30  # Adjust assertion threshold to map definitions


@pytest.mark.asyncio
async def test_auto_fix_error_retry_loop():
    """Verify self-healing compilation error fixing retry logs."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    test_file = os.path.join(project_root, "test_autofix.py")
    with open(test_file, "w") as f:
        f.write("def bad_syntax() error")

    backups_dir = os.path.join(project_root, ".backups")

    try:
        # Mock API calls and test results
        mock_llm_response_1 = {"response": "```python\ndef bad_syntax():\n    return 1\n```"}
        mock_llm_response_2 = {"response": "```python\ndef bad_syntax():\n    return 2\n```"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            # LLM API calls
            resp1 = MagicMock()
            resp1.status_code = 200
            resp1.json.return_value = mock_llm_response_1
            
            resp2 = MagicMock()
            resp2.status_code = 200
            resp2.json.return_value = mock_llm_response_2

            mock_post.side_effect = [resp1, resp2]

            # Test execution calls: First retry fails, second retry succeeds
            with patch("actions.coding_agent.run_tests") as mock_run_tests:
                res1 = {"success": False, "data": {"output": "SyntaxError: invalid syntax"}}
                res2 = {"success": True, "data": {"output": "Tests passed"}}
                mock_run_tests.side_effect = [res1, res2]

                res = await action_registry.get_handler("coding.fix_errors")({
                    "file_path": test_file,
                    "error_message": "SyntaxError: invalid syntax",
                    "max_retries": 2
                })
                assert res["success"] is True
                assert len(res["data"]["attempts"]) == 2
                assert res["data"]["attempts"][0]["result"] == "failed"
                assert res["data"]["attempts"][1]["result"] == "success"

    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
        # Clean backups
        for f in glob.glob(os.path.join(backups_dir, "test_autofix_*.py")):
            try:
                os.remove(f)
            except Exception:
                pass
