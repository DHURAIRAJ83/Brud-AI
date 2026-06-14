import pytest
import httpx
import os
import sys
from unittest.mock import patch, MagicMock, mock_open

# Ensure backend folder is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.command_parser import command_parser
from services.vision_service import vision_service
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

@pytest.mark.asyncio
async def test_rule_based_parsing_screen_commands():
    # 1. Full screenshot
    act = await command_parser.parse("take screenshot")
    assert act.tool == "screen.capture"
    assert act.is_desktop_command is True
    
    # Tamil screenshot
    act_tamil = await command_parser.parse("திரையை ஸ்கிரீன்ஷாட் எடு")
    assert act_tamil.tool == "screen.capture"

    # 2. Active Window Capture
    act_active = await command_parser.parse("active window screenshot")
    assert act_active.tool == "screen.active_window"
    
    # 3. Region capture
    act_region = await command_parser.parse("capture region x=100 y=150 w=500 h=600")
    assert act_region.tool == "screen.region_capture"
    assert act_region.params["x"] == 100
    assert act_region.params["y"] == 150
    assert act_region.params["w"] == 500
    assert act_region.params["h"] == 600

    # 4. Multi monitor capture
    act_multi = await command_parser.parse("multi monitor capture")
    assert act_multi.tool == "screen.multi_monitor_capture"


@pytest.mark.asyncio
async def test_rule_based_parsing_ocr_commands():
    # 1. Simple OCR
    act = await command_parser.parse("read screen")
    assert act.tool == "screen.ocr"
    
    # 2. Error scan
    act_err = await command_parser.parse("திரையில் என்ன error?")
    assert act_err.tool == "screen.read_error"
    
    # 3. Layout extraction with coordinates
    act_layout = await command_parser.parse("extract layout coordinates")
    assert act_layout.tool == "screen.extract_text"
    
    # 4. File-specific OCR
    act_file = await command_parser.parse("read sample.png file")
    assert act_file.tool == "screen.ocr"
    assert act_file.params["image_path"] == "sample.png"


@pytest.mark.asyncio
async def test_vision_service_fallback_chain():
    # Mock file read check
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=b"dummy_bytes")):
        
        # Scenario A: Primary model (qwen2.5-vl) succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Analyzed UI with Qwen VL successfully."}
        
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            res = await vision_service.analyze_image("dummy_path.png", "What is on screen?")
            assert "Qwen VL" in res
            assert mock_post.call_count == 1
            
        # Scenario B: Primary fails, secondary model (llava:7b) succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 404
        
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"response": "Analyzed UI with Llava successfully."}
        
        with patch("httpx.AsyncClient.post", side_effect=[mock_response_fail, mock_response_ok]) as mock_post:
            res = await vision_service.analyze_image("dummy_path.png", "What is on screen?")
            assert "Llava" in res
            assert mock_post.call_count == 2

        # Scenario C: Both models fail -> triggers text-only warning description fallback
        with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")) as mock_post:
            res = await vision_service.analyze_image("dummy_path.png", "What is on screen?")
            assert "Unable to analyze screen visually" in res
            assert mock_post.call_count == 2


def test_vision_analyze_endpoint_upload():
    # Test POST /api/vision/analyze using multipart upload file path
    # Mock the Ollama vision call
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "Vision OCR mock run completed."}
    
    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        response = client.post(
            "/api/vision/analyze",
            data={"prompt": "Find system dialogues"},
            files={"file": ("screenshot.png", b"dummy_img_bytes", "image/png")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "mock run completed" in data["analysis"]
