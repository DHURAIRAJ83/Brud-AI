"""
Streaming Ollama Client — SSE Token-by-Token
---------------------------------------------
Streams Ollama responses as Server-Sent Events.
Users see tokens appear in real-time — feels 3× faster.
"""

import json
import logging
from typing import AsyncGenerator, Optional
import httpx
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def stream_generate(
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted token chunks from Ollama.

    Each yielded string is a complete SSE line:
      data: {"token": "hello", "done": false}\n\n

    Final event:
      data: {"token": "", "done": true}\n\n
    """
    payload = {
        "model": model or settings.ollama_model,
        "prompt": prompt,
        "stream": True,                    # KEY: enable streaming
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": 2048,
            "num_thread": 4,
        },
    }
    if system:
        payload["system"] = system

    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("response", "")
                        done = data.get("done", False)

                        # Yield SSE event
                        yield f"data: {json.dumps({'token': token, 'done': done})}\n\n"

                        if done:
                            break
                    except json.JSONDecodeError:
                        continue

    except httpx.ConnectError:
        yield f"data: {json.dumps({'error': 'Ollama not running. Start with: ollama serve', 'done': True})}\n\n"
    except Exception as e:
        logger.error("Stream error: %s", e)
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
