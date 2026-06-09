"""
AI Agent System — Multi-Step Autonomous Execution
---------------------------------------------------
Turns complex queries into a plan of steps, executes each tool
sequentially, maintains intermediate state, and synthesizes a
unified final response.

Flow:
  User query
      ↓
  Planner (LLM) → [step1, step2, step3]
      ↓
  Executor → runs each step via Tool/RAG/LLM
      ↓
  Synthesizer (LLM) → combined final answer

CPU Optimization:
  - Planner uses low-temperature, small max_tokens
  - Steps share intermediate memory (no re-computation)
  - Steps capped at MAX_STEPS to prevent runaway chains
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from ai.ollama_client import ollama_client
from ai.rag_engine import rag_engine
from tools.tool_engine import tool_engine

logger = logging.getLogger(__name__)

MAX_STEPS = 5   # CPU guard — never exceed this many LLM calls in one chain

# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class AgentStep:
    step_id: int
    action: str          # tool name or "llm" or "rag"
    input: str           # what to send to the action
    output: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class AgentPlan:
    goal: str
    steps: list[AgentStep] = field(default_factory=list)
    final_response: str = ""
    total_duration_ms: float = 0.0
    is_agent: bool = True


# ── Planner ───────────────────────────────────────────────────────────────────

PLANNER_SYSTEM = """You are a planning AI. Break a complex user request into sequential steps.
Available actions: summarize, calculate, translate, file_read, rag_search, llm_answer

Rules:
1. Reply ONLY with valid JSON array — no extra text.
2. Maximum 5 steps.
3. Each step must have: {"action": "<action>", "input": "<what to pass>"}
4. If request is simple (1 step), return 1-element array.
5. "input" should be a standalone instruction usable without other context.

Example:
[
  {"action": "file_read", "input": "Read the uploaded PDF and extract main points"},
  {"action": "summarize", "input": "Summarize the key points extracted above"},
  {"action": "translate", "input": "Translate the summary to Tamil"}
]"""


class Planner:
    async def plan(self, user_query: str) -> list[dict]:
        """Ask LLM to break query into steps. Returns list of {action, input}."""
        prompt = f"Break this request into steps:\n\n{user_query}\n\nJSON steps:"
        try:
            raw = await ollama_client.generate(
                prompt=prompt,
                system=PLANNER_SYSTEM,
                temperature=0.1,
                max_tokens=300,
            )
            # Extract JSON array
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                steps = json.loads(match.group())
                return steps[:MAX_STEPS]
        except Exception as e:
            logger.warning("Planner fallback (single step): %s", e)

        # Fallback: treat as single llm_answer step
        return [{"action": "llm_answer", "input": user_query}]


# ── Executor ──────────────────────────────────────────────────────────────────

class Executor:
    async def run_step(self, step: AgentStep, context: str = "") -> AgentStep:
        """Execute a single plan step. Injects previous output as context."""
        start = time.perf_counter()
        action = step.action
        inp = step.input

        # Inject previous context into input when relevant
        if context and "[PREV]" not in inp:
            inp = f"{inp}\n\n[Previous step result]:\n{context}"

        try:
            if action in {"summarize", "calculate", "translate", "file_read"}:
                result = await tool_engine.execute(action, inp)
                step.output = result.get("result", "")

            elif action == "rag_search":
                hits = rag_engine.search(inp, top_k=3)
                if hits:
                    step.output = "\n\n".join(h["chunk"] for h in hits)
                else:
                    step.output = "No relevant documents found."

            else:  # llm_answer (default)
                step.output = await ollama_client.generate(
                    prompt=inp,
                    temperature=0.7,
                    max_tokens=512,
                )

        except Exception as e:
            step.error = str(e)
            step.output = f"[Step failed: {e}]"

        step.duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Step %d [%s] → %.0fms | error=%s",
            step.step_id, action, step.duration_ms, step.error
        )
        return step


# ── Synthesizer ───────────────────────────────────────────────────────────────

SYNTHESIZER_SYSTEM = """You are a response synthesizer.
Given intermediate step results, combine them into a single clean, well-structured response.
Preserve Tamil text as-is. Be concise but complete. Do not repeat yourself."""


class Synthesizer:
    async def synthesize(self, goal: str, steps: list[AgentStep]) -> str:
        """Combine multiple step outputs into one final answer."""
        if len(steps) == 1:
            return steps[0].output  # Single step — no synthesis needed

        parts = []
        for i, s in enumerate(steps, 1):
            if s.output and not s.error:
                parts.append(f"Step {i} ({s.action}):\n{s.output}")

        combined = "\n\n---\n\n".join(parts)
        prompt = (
            f"Original request: {goal}\n\n"
            f"Step results:\n{combined}\n\n"
            f"Write a unified, well-structured final response:"
        )
        try:
            return await ollama_client.generate(
                prompt=prompt,
                system=SYNTHESIZER_SYSTEM,
                temperature=0.5,
                max_tokens=600,
            )
        except Exception:
            # Fallback: just join outputs
            return "\n\n".join(
                f"**{s.action.capitalize()}:**\n{s.output}"
                for s in steps if s.output
            )


# ── Agent — ties it all together ──────────────────────────────────────────────

class Agent:
    def __init__(self):
        self.planner = Planner()
        self.executor = Executor()
        self.synthesizer = Synthesizer()

    def _is_complex(self, query: str) -> bool:
        """
        Heuristic: does this query need multi-step reasoning?
        Signals: multiple actions, "and", "+", compound tasks.
        """
        lower = query.lower()
        complexity_signals = [
            " and ", " then ", " also ", " plus ", " after that ",
            "summary + ", "analyze and", "translate and",
            "முக்கிய points", "விவரம் + ", "பின்னர்",
        ]
        return any(sig in lower for sig in complexity_signals) or len(query.split()) > 25

    async def run(self, user_query: str, force_agent: bool = False) -> AgentPlan:
        """
        Main agent entry point.
        Returns AgentPlan with all step details and final response.
        """
        start = time.perf_counter()
        plan = AgentPlan(goal=user_query)

        # Only activate multi-step for genuinely complex queries
        if not force_agent and not self._is_complex(user_query):
            logger.info("Simple query — single-step agent")
            step = AgentStep(step_id=1, action="llm_answer", input=user_query)
            step = await self.executor.run_step(step)
            plan.steps = [step]
            plan.final_response = step.output
            plan.total_duration_ms = (time.perf_counter() - start) * 1000
            plan.is_agent = False
            return plan

        # Complex path: plan → execute → synthesize
        logger.info("Complex query — activating multi-step agent")
        raw_steps = await self.planner.plan(user_query)

        context = ""
        for i, s in enumerate(raw_steps, 1):
            agent_step = AgentStep(
                step_id=i,
                action=s.get("action", "llm_answer"),
                input=s.get("input", user_query),
            )
            agent_step = await self.executor.run_step(agent_step, context)
            plan.steps.append(agent_step)
            context = agent_step.output  # chain: output feeds next step

        plan.final_response = await self.synthesizer.synthesize(user_query, plan.steps)
        plan.total_duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Agent completed %d steps in %.0fms",
            len(plan.steps), plan.total_duration_ms
        )
        return plan


# Singleton
agent = Agent()
