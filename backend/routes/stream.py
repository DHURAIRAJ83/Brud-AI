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
import uuid
from typing import Optional
from pydantic import BaseModel

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
        system = SYSTEM_TEMPLATE.format(
            lang_hint=lang_hint,
            facts=facts,
            context=f"Relevant knowledge:\n{rag_context}" if rag_context else "",
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
