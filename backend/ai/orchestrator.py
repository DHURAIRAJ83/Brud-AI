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

from fastapi import HTTPException

from ai.agent import agent
from ai.intent_engine import intent_engine
from ai.sqlite_memory import sqlite_memory        # Phase 3: persistent
from ai.memory_store import memory_store          # Task 3: typed persistent memory
from ai.model_router import model_router
from ai.ollama_client import ollama_client
from ai.rag_engine import rag_engine
from ai.tamil_intelligence import tamil_intelligence, Language
from ai.command_parser import command_parser              # Desktop Agent
from ai.action_planner import action_planner, ExecutionStrategy # Desktop Agent
from tools.tool_engine import tool_engine
from services.command_service import command_service
from services.error_translator import error_translator
from services.skills_service import skills_service
from models.command import CommandCreate, CommandStatus, CommandModel, TrustLevel

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
        source: str = "chat",
        voice_auth_session_id: Optional[str] = None,
        user_id: str = "admin-user-123",
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

        # ── 1.5. Desktop Command Pipeline ──────────────────────────────────────
        # Currently defaults to dev_123 for testing, eventually from user context
        DEFAULT_DEVICE_ID = "desktop001" 
        
        desktop_action = await command_parser.parse(user_message)
        if desktop_action.is_desktop_command:
            # Check if this is a direct backend skill activation action
            if desktop_action.tool == "skills.activate":
                skill_id = desktop_action.params.get("skill_id")
                await sqlite_memory.set_active_skill(session_id, skill_id)
                response_text = f"✅ ருத்ரன் தற்போது '{skill_id}' ஆளுமைக்கு (personality) மாறியுள்ளார்."
                
                # Save to memory
                await sqlite_memory.add_turn(session_id, "user", user_message)
                await sqlite_memory.add_turn(session_id, "assistant", response_text)
                
                total_ms = (time.perf_counter() - t_start) * 1000
                return {
                    "response": response_text,
                    "intent": "change_skill",
                    "confidence": desktop_action.confidence,
                    "language": lang_code,
                    "source": "backend_skills",
                    "session_id": session_id,
                    "model_used": "rule-based",
                    "tanglish_converted": tamil_meta["tanglish_converted"],
                    "duration_ms": round(total_ms, 1),
                }

            plan = action_planner.plan(desktop_action)
            
            if plan.strategy == ExecutionStrategy.REJECT:
                response_text = plan.blocked_reason
                source = "desktop_agent"
            elif plan.strategy == ExecutionStrategy.DECOMPOSE:
                try:
                    enqueued_cmds = []
                    requires_approval = plan.trust_level in (TrustLevel.CAUTION, TrustLevel.DANGEROUS) and not voice_auth_session_id
                    
                    for step in plan.sub_steps:
                        sub_act = step["action"]
                        cmd_data = CommandCreate(
                            device_id=DEFAULT_DEVICE_ID,
                            tool=sub_act["tool"],
                            params=sub_act["params"],
                            raw_input=user_message,
                            source_language=lang_code,
                            source=source,
                            voice_auth_session_id=voice_auth_session_id
                        )
                        cmd = await command_service.enqueue_command(user_id, cmd_data, session_id=session_id)
                        
                        if requires_approval and cmd["status"] == CommandStatus.PENDING.value:
                            await CommandModel.update_status(cmd["id"], CommandStatus.AWAITING_APPROVAL)
                            cmd["status"] = CommandStatus.AWAITING_APPROVAL.value
                            
                        enqueued_cmds.append(cmd)
                    
                    if requires_approval:
                        confirms = [s["confirmation_message"] for s in plan.sub_steps if s["confirmation_message"]]
                        confirm_text = " + ".join(confirms) if confirms else "செயல்படுத்தவா? (Execute steps?)"
                        response_text = f"⏳ அனுமதி தேவை: {confirm_text}\nID: {enqueued_cmds[0]['id'][:8]}"
                    else:
                        response_text = f"✅ {len(enqueued_cmds)} கட்டளைகள் வரிசையில் சேர்க்கப்பட்டன."
                    source = "desktop_agent"
                except HTTPException:
                    raise
                except Exception as e:
                    raw_error = str(e)
                    if hasattr(e, "detail"):
                        raw_error = e.detail
                    tamil_error = error_translator.translate(raw_error)
                    response_text = f"❌ பிழை: {tamil_error}"
                    source = "desktop_agent"
            else:
                try:
                    cmd_data = CommandCreate(
                        device_id=DEFAULT_DEVICE_ID,
                        tool=desktop_action.tool,
                        params=desktop_action.params,
                        raw_input=user_message,
                        source_language=lang_code,
                        source=source,
                        voice_auth_session_id=voice_auth_session_id
                    )
                    
                    # Queue it!
                    cmd = await command_service.enqueue_command(user_id, cmd_data, session_id=session_id)
                    
                    if plan.strategy == ExecutionStrategy.AWAIT_APPROVAL:
                        response_text = f"⏳ அனுமதி தேவை: {plan.confirmation_message}\nID: {cmd['id'][:8]}"
                    else:
                        response_text = f"✅ கட்டளை வரிசையில் சேர்க்கப்பட்டது: {desktop_action.tool}"
                    
                    source = "desktop_agent"
                except HTTPException:
                    raise  # Re-propagate voice auth 403s and security 403s
                except Exception as e:
                    # Translate Error! Phase C
                    raw_error = str(e)
                    if hasattr(e, "detail"):
                        raw_error = e.detail
                    
                    tamil_error = error_translator.translate(raw_error)
                    response_text = f"❌ பிழை: {tamil_error}"
                    source = "desktop_agent"
                    
            # Skip the rest of the pipeline
            total_ms = (time.perf_counter() - t_start) * 1000
            
            # Save to memory
            await sqlite_memory.add_turn(session_id, "user", user_message)
            await sqlite_memory.add_turn(session_id, "assistant", response_text)
            
            return {
                "response": response_text,
                "intent": "desktop_command",
                "confidence": desktop_action.confidence,
                "language": lang_code,
                "source": source,
                "session_id": session_id,
                "model_used": "rule-based",
                "tanglish_converted": tamil_meta["tanglish_converted"],
                "desktop": {
                    "tool": desktop_action.tool,
                    "params": desktop_action.params,
                    "trust": plan.trust_level.value,
                    "strategy": plan.strategy.value
                },
                "duration_ms": round(total_ms, 1),
            }


        # ── 2. Intent detection (Fallback to standard chat) ────────────────────
        intent_result = await intent_engine.detect(normalized_message)
        intent = intent_result["intent"]
        confidence = intent_result["confidence"]
        logger.info("Intent: %s (%.2f)", intent, confidence)

        # ── 3. Model routing & Skill resolution ────────────────────────────────
        active_skill_id = await sqlite_memory.get_active_skill(session_id)
        resolved_skill = None
        if active_skill_id:
            resolved_skill = await skills_service.get_resolved_skill(active_skill_id)

        routing_info = model_router.get_routing_info(normalized_message, intent)
        selected_model = routing_info["model"]
        
        # Override model if specified by active skill
        if resolved_skill and resolved_skill.get("model") not in ("auto", "default", None):
            selected_model = resolved_skill["model"]
            routing_info["model"] = selected_model
            routing_info["reason"] = f"Override by skill profile: {active_skill_id}"

        # Temporarily override model for this request
        original_model = ollama_client.model
        ollama_client.model = selected_model

        # ── 4. Memory retrieval + context compression ──────────────────────────
        raw_history = await sqlite_memory.get_context(session_id)
        history = await self._compress_context_if_needed(raw_history, session_id)

        # Task 3: extract typed facts from message, retrieve all for prompt
        await memory_store.extract_and_save(session_id, user_message)
        typed_facts = await memory_store.retrieve_facts(session_id)

        # ── 4.5. Resolve implicit references (Implicit Query Resolution) ────────
        from ai.project_context import project_context_manager
        implicit_context = project_context_manager.resolve_implicit_query(normalized_message)
        implicit_hint = ""
        if implicit_context:
            implicit_hint = (
                f"\n[Implicit Reference Context]: User is referring to the active file '{implicit_context['active_file']}' "
                f"at line {implicit_context['cursor_line']} "
            )
            if implicit_context.get("active_symbol"):
                implicit_hint += f"(enclosing symbol: '{implicit_context['active_symbol']}')"
            implicit_hint += ".\n"

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
                rag_context = await rag_engine.build_context(normalized_message)
                
                # Context / RAG block
                context_block = f"Relevant knowledge:\n{rag_context}" if rag_context else ""
                
                # Check for active skill prompt injection
                if resolved_skill:
                    skill_prompt = resolved_skill["system_prompt"]
                    # Build dynamic prompt with inheritance injected
                    system_prompt = (
                        f"{skill_prompt}\n\n"
                        f"{lang_hint}\n\n"
                        f"{implicit_hint}\n\n"
                        f"{typed_facts}\n\n"
                        f"{context_block}\n\n"
                        f"Conversation so far:\n{history}\n\n"
                        f"Answer helpfully, concisely, and accurately."
                    )
                else:
                    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                        lang_hint=lang_hint + implicit_hint,
                        typed_facts=typed_facts,
                        context=context_block,
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
