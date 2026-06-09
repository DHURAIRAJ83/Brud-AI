import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

# Ensure backend folder is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from main import app

def get_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")

@pytest.mark.asyncio
async def test_transcribe_empty():
    async with get_client() as client:
        files = {"audio": ("audio.wav", b"", "audio/wav")}
        response = await client.post("/api/audio/transcribe", files=files)
        assert response.status_code == 400
        assert "Empty audio file" in response.json()["detail"]

@pytest.mark.asyncio
async def test_speak_empty():
    async with get_client() as client:
        response = await client.post("/api/audio/speak", json={"text": "", "language": "ta"})
        assert response.status_code == 400
        assert "Text cannot be empty" in response.json()["detail"]

@pytest.mark.asyncio
async def test_speak_success_tamil():
    async with get_client() as client:
        response = await client.post("/api/audio/speak", json={"text": "வணக்கம்", "language": "ta"})
        assert response.status_code == 200
        assert response.headers["content-type"] in ["audio/wav", "audio/mpeg"]
        assert len(response.content) > 100

@pytest.mark.asyncio
async def test_speak_success_english():
    async with get_client() as client:
        response = await client.post("/api/audio/speak", json={"text": "Hello, how are you?", "language": "en"})
        assert response.status_code == 200
        assert response.headers["content-type"] in ["audio/wav", "audio/mpeg"]
        assert len(response.content) > 100

@pytest.mark.asyncio
async def test_stream_post_success():
    async with get_client() as client:
        response = await client.post("/api/chat/stream", json={"message": "calculate 2 + 2", "session_id": "test_session"})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        
        # Verify it streams SSE data correctly
        content = response.text
        assert "data:" in content
        assert "meta" in content
        assert "calculate" in content
