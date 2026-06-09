"""
AI Orchestrator v2 — Upgraded Core Brain
-----------------------------------------
Now integrates:
  ✅ Phase 1: Language detect → Intent → Tool/RAG → Memory
  🆕 Agent System (multi-step for complex queries)
  🆕 Smart Model Router (TinyLlama vs Mistral)
  🆕 Tamil Intelligence (Tanglish normalization + response hints)
  🆕 Context Compression (auto-summarize long histories)
  🆕 Observability metadata in every response
"""

import logging
import time
from typing import Optional

from ai.agent import agent
from ai.intent_engine import intent_engine
from ai.sqlite_memory import sqlite_memory        # Phase 3: persistent
from ai.memory_store import memory_store          # Task 3: typed persistent memory
from ai.model_router import model_router
from ai.ollama_client import ollama_client
from ai.rag_engine import rag_engine
from ai.tamil_intelligence import tamil_intelligence, Language
from tools.tool_engine import tool_engine

logger = logging.getLogger(__name__)

TOOL_INTENTS = {"summarize", "calculate", "translate", "file_read"}

# Context compression threshold: if history > N words, summarize old turns
CONTEXT_COMPRESS_THRESHOLD = 600  # words

SYSTEM_PROMPT_TEMPLATE = """You are a helpful AI assistant that understands both Tamil and English.
{lang_hint}

{typed_facts}

{context}

Conversation so far:
{history}

Answer helpfully, concisely, and accurately."""


class Orchestrator:

    # ── Context Compression ────────────────────────────────────────────────────
    async def _compress_context_if_needed(self, history: str, session_id: str) -> str:
        """
        If history is too long, summarize the oldest half to save tokens.
        Keeps recent turns intact for continuity.
        """
        if len(history.split()) <= CONTEXT_COMPRESS_THRESHOLD:
            return history

        logger.info("Context compression triggered for session %s", session_id)
        lines = history.strip().split("\n")
        half = len(lines) // 2
        old_part = "\n".join(lines[:half])
        recent_part = "\n".join(lines[half:])

        try:
            summary = await ollama_client.generate(
                prompt=f"Summarize this conversation history in 3 sentences:\n{old_part}",
                temperature=0.1,
                max_tokens=150,
            )
            compressed = f"[Earlier conversation summary]: {summary}\n\n{recent_part}"
            return compressed
        except Exception:
            # If compression fails, just trim and return recent half
            return f"[Earlier context truncated]\n\n{recent_part}"

    # ── Main Process ───────────────────────────────────────────────────────────
    async def process(
        self,
        user_message: str,
        session_id: str,
        file_path: Optional[str] = None,
        force_agent: bool = False,
    ) -> dict:
        """
        Full v2 pipeline:
          raw_input
            → Tamil normalize (Tanglish → Tamil)
            → Language detect
            → Intent detect
            → Model route
            → Agent OR Tool OR RAG+LLM
            → Memory store
            → Response + observability metadata
        """
        t_start = time.perf_counter()

        # ── 1. Tamil Intelligence — normalize input ────────────────────────────
        normalized_message, tamil_meta = tamil_intelligence.normalize_for_llm(user_message)
        lang_enum = Language(tamil_meta["detected_language"])
        lang_hint = tamil_intelligence.get_response_language_hint(lang_enum)
        lang_code = tamil_meta["detected_language"]

        logger.info(
            "Lang=%s | Tanglish=%s | normalized='%s…'",
            lang_code,
            tamil_meta["tanglish_converted"],
            normalized_message[:40],
        )

        # ── 2. Intent detection ────────────────────────────────────────────────
        intent_result = await intent_engine.detect(normalized_message)
        intent = intent_result["intent"]
        confidence = intent_result["confidence"]
        logger.info("Intent: %s (%.2f)", intent, confidence)

        # ── 3. Model routing ───────────────────────────────────────────────────
        routing_info = model_router.get_routing_info(normalized_message, intent)
        selected_model = routing_info["model"]

        # Temporarily override model for this request
        original_model = ollama_client.model
        ollama_client.model = selected_model

        # ── 4. Memory retrieval + context compression ──────────────────────────
        raw_history = await sqlite_memory.get_context(session_id)
        history = await self._compress_context_if_needed(raw_history, session_id)

        # Task 3: extract typed facts from message, retrieve all for prompt
        await memory_store.extract_and_save(session_id, user_message)
        typed_facts = await memory_store.retrieve_facts(session_id)

        response_text = ""
        source = "llm"
        agent_steps = []
        is_agent_run = False

        try:
            # ── 5. Route to Agent / Tool / RAG+LLM ────────────────────────────
            if force_agent or (intent not in TOOL_INTENTS and agent._is_complex(normalized_message)):
                # Multi-step agent path
                plan = await agent.run(normalized_message, force_agent=force_agent)
                response_text = plan.final_response
                agent_steps = [
                    {
                        "step_id": s.step_id,
                        "action": s.action,
                        "duration_ms": round(s.duration_ms, 1),
                        "error": s.error,
                    }
                    for s in plan.steps
                ]
                is_agent_run = plan.is_agent
                source = "agent"

            elif intent in TOOL_INTENTS:
                # Direct tool execution
                result = await tool_engine.execute(intent, normalized_message)
                response_text = result.get("result", "Tool returned no output.")
                source = "tool"

            else:
                # RAG + LLM path
                rag_context = rag_engine.build_context(normalized_message)
                system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                    lang_hint=lang_hint,
                    typed_facts=typed_facts,
                    context=(
                        f"Relevant knowledge:\n{rag_context}" if rag_context else ""
                    ),
                    history=history,
                )
                response_text = await ollama_client.generate(
                    prompt=normalized_message,
                    system=system_prompt,
                    temperature=0.7,
                    max_tokens=512,
                )
                source = "rag+llm" if rag_context else "llm"

        finally:
            # Always restore original model
            ollama_client.model = original_model

        # ── 6. Save to memory ──────────────────────────────────────────────────
        await sqlite_memory.add_turn(session_id, "user", user_message)
        await sqlite_memory.add_turn(session_id, "assistant", response_text)

        # ── 7. Build response with observability metadata ──────────────────────
        total_ms = (time.perf_counter() - t_start) * 1000

        return {
            "response": response_text,
            "intent": intent,
            "confidence": confidence,
            "language": lang_code,
            "source": source,
            "session_id": session_id,
            # Phase 2 metadata
            "model_used": selected_model,
            "routing": routing_info,
            "tanglish_converted": tamil_meta["tanglish_converted"],
            "normalized_input": normalized_message if tamil_meta["tanglish_converted"] else None,
            "agent": {
                "is_agent": is_agent_run,
                "steps": agent_steps,
            } if is_agent_run else None,
            "duration_ms": round(total_ms, 1),
        }


# Singleton
orchestrator = Orchestrator()
