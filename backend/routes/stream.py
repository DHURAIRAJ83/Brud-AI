"""
Streaming Chat Route — GET /api/chat/stream
--------------------------------------------
FastAPI SSE endpoint. Client connects with EventSource,
receives token-by-token response from Ollama.

Client usage (JavaScript):
  const es = new EventSource(`/api/chat/stream?message=hello&session_id=abc`);
  es.onmessage = (e) => {
    const { token, done, meta } = JSON.parse(e.data);
    if (done) es.close();
    else appendToken(token);
  };
"""

import json
import logging
import uuid
import time
from collections import defaultdict, deque
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# IP-based sliding window rate limiter for WebSocket connections
ws_rate_limit_windows = defaultdict(deque)

def check_ws_rate_limit(ip: str) -> bool:
    now = time.time()
    window = ws_rate_limit_windows[ip]
    while window and (now - window[0]) > 60:
        window.popleft()
    if len(window) >= 5:  # Max 5 connections/minute
        return False
    window.append(now)
    return True

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ai.intent_engine import intent_engine
from ai.memory_system import memory_system
from ai.model_router import model_router
from ai.ollama_client import ollama_client
from ai.rag_engine import rag_engine
from ai.stream_client import stream_generate
from ai.tamil_intelligence import tamil_intelligence
from tools.tool_engine import tool_engine

router = APIRouter()

TOOL_INTENTS = {"summarize", "calculate", "translate", "file_read"}

SYSTEM_TEMPLATE = """You are a helpful AI assistant that understands Tamil and English.
{lang_hint}
{facts}
{context}
Conversation so far:
{history}
Answer helpfully and concisely."""


async def _build_stream(message: str, session_id: str):
    """Core streaming pipeline — yields SSE events."""

    # 1. Tamil normalize
    normalized, meta = tamil_intelligence.normalize_for_llm(message)
    lang_hint = tamil_intelligence.get_response_language_hint(
        tamil_intelligence.detect_language(normalized)
    )

    # 2. Intent + routing
    intent_result = await intent_engine.detect(normalized)
    intent = intent_result["intent"]
    model, tier = model_router.select_model(normalized, intent)

    # 2.5 Active skill resolution
    from ai.sqlite_memory import sqlite_memory
    from services.skills_service import skills_service
    active_skill_id = await sqlite_memory.get_active_skill(session_id)
    resolved_skill = None
    if active_skill_id:
        resolved_skill = await skills_service.get_resolved_skill(active_skill_id)
        if resolved_skill and resolved_skill.get("model") not in ("auto", "default", None):
            model = resolved_skill["model"]

    # 3. Memory
    history = memory_system.get_context(session_id)
    facts = memory_system.get_facts(session_id)

    # 4. Emit metadata event first (client can show intent/model badge immediately)
    yield f"data: {json.dumps({'type': 'meta', 'intent': intent, 'model': model, 'lang': meta['detected_language'], 'tanglish': meta['tanglish_converted'], 'normalized': normalized})}\n\n"

    full_response = ""

    # 5. Tool path — no streaming (tools return complete results)
    if intent in TOOL_INTENTS:
        result = await tool_engine.execute(intent, normalized)
        text = result.get("result", "Tool returned no output.")
        full_response = text
        # Send entire tool result as single token chunk
        yield f"data: {json.dumps({'type': 'token', 'token': text, 'done': False})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'token': '', 'done': True})}\n\n"

    else:
        # 6. RAG + streaming LLM path
        rag_context = rag_engine.build_context(normalized)
        
        # Context block
        context_block = f"Relevant knowledge:\n{rag_context}" if rag_context else ""
        
        # Check active skill prompt overrides
        if resolved_skill:
            skill_prompt = resolved_skill["system_prompt"]
            system = (
                f"{skill_prompt}\n\n"
                f"{lang_hint}\n\n"
                f"{facts}\n\n"
                f"{context_block}\n\n"
                f"Conversation so far:\n{history}\n\n"
                f"Answer helpfully and concisely."
            )
        else:
            system = SYSTEM_TEMPLATE.format(
                lang_hint=lang_hint,
                facts=facts,
                context=context_block,
                history=history,
            )

        # Override model for this request
        orig = ollama_client.model
        ollama_client.model = model
        try:
            async for chunk in stream_generate(
                prompt=normalized,
                system=system,
                model=model,
                temperature=0.7,
                max_tokens=512,
            ):
                # chunk is already SSE-formatted: "data: {...}\n\n"
                # Extract token for memory accumulation
                try:
                    payload = json.loads(chunk.removeprefix("data: ").strip())
                    full_response += payload.get("token", "")
                    # Re-emit with type field
                    payload["type"] = "token"
                    yield f"data: {json.dumps(payload)}\n\n"
                except Exception:
                    yield chunk
        finally:
            ollama_client.model = orig

    # 7. Save to memory after stream completes
    memory_system.add_turn(session_id, "user", message)
    memory_system.add_turn(session_id, "assistant", full_response)


class StreamRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

@router.get("/chat/stream", summary="Streaming chat via SSE (GET)")
async def stream_chat_get(
    message: str,
    session_id: Optional[str] = None,
):
    """
    GET SSE endpoint.
    """
    sid = session_id or str(uuid.uuid4())
    return StreamingResponse(
        _build_stream(message, sid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )

@router.post("/chat/stream", summary="Streaming chat via SSE (POST)")
async def stream_chat_post(request: StreamRequest):
    """
    POST SSE endpoint. Accept JSON body payload with message and session_id.
    """
    sid = request.session_id or str(uuid.uuid4())
    return StreamingResponse(
        _build_stream(request.message, sid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── Phase 5: WebSocket Real-time Chat ─────────────────────────────────────────

import asyncio
from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket chat endpoint — Phase 5.
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    if client_ip != "unknown" and not check_ws_rate_limit(client_ip):
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "error", "detail": "Rate limit exceeded. Max 5 connections/minute."}))
        await websocket.close(code=1008)
        return

    await websocket.accept()
    
    from config import get_settings
    settings = get_settings()

    if settings.security_enabled:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.send_text(json.dumps({"type": "error", "detail": "Authentication token required"}))
            await websocket.close(code=1008)
            return
        try:
            from services.auth_service import decode_token
            payload = decode_token(token)
            user_id = payload.get("sub")
            if not user_id:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Invalid token payload"}))
                await websocket.close(code=1008)
                return
        except Exception as e:
            logger.error("WebSocket chat authentication failed: %s", e)
            await websocket.send_text(json.dumps({"type": "error", "detail": f"Authentication failed: {str(e)}"}))
            await websocket.close(code=1008)
            return

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Invalid JSON"}))
                continue

            message    = data.get("message", "").strip()
            session_id = data.get("session_id") or str(uuid.uuid4())

            if not message:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Empty message"}))
                continue

            try:
                async for sse_chunk in _build_stream(message, session_id):
                    # _build_stream yields "data: {...}\n\n" SSE strings
                    json_part = sse_chunk.removeprefix("data: ").strip()
                    if json_part:
                        await websocket.send_text(json_part)
                        # Small yield to avoid blocking
                        await asyncio.sleep(0)
            except Exception as exc:
                await websocket.send_text(
                    json.dumps({"type": "error", "detail": str(exc)})
                )

    except WebSocketDisconnect:
        pass


class SystemEventsConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("New client connected to system-events WS. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("Client disconnected from system-events WS. Total: %d", len(self.active_connections))

    async def broadcast(self, message: dict):
        logger.info("Broadcasting system event: %s", message)
        payload = json.dumps(message)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.error("Failed to send system event: %s", e)
                self.disconnect(connection)


system_events_manager = SystemEventsConnectionManager()


@router.websocket("/ws/system-events")
async def websocket_system_events(websocket: WebSocket):
    client_ip = websocket.client.host if websocket.client else "unknown"
    if client_ip != "unknown" and not check_ws_rate_limit(client_ip):
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "error", "detail": "Rate limit exceeded. Max 5 connections/minute."}))
        await websocket.close(code=1008)
        return

    await websocket.accept()

    from config import get_settings
    settings = get_settings()

    if settings.security_enabled:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.send_text(json.dumps({"type": "error", "detail": "Authentication token required"}))
            await websocket.close(code=1008)
            return
        try:
            from services.auth_service import decode_token
            payload = decode_token(token)
            user_id = payload.get("sub")
            if not user_id:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Invalid token payload"}))
                await websocket.close(code=1008)
                return
        except Exception as e:
            logger.error("WebSocket system-events authentication failed: %s", e)
            await websocket.send_text(json.dumps({"type": "error", "detail": "Authentication failed"}))
            await websocket.close(code=1008)
            return

    # Connection registered manually to bypass connect accept phase
    system_events_manager.active_connections.append(websocket)
    logger.info("New client connected to system-events WS. Total: %d", len(system_events_manager.active_connections))
    
    try:
        while True:
            # Block and wait for messages (e.g. keep-alive or ping) from the client
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        system_events_manager.disconnect(websocket)
    except Exception as e:
        logger.error("Error in system-events WebSocket: %s", e)
        system_events_manager.disconnect(websocket)

