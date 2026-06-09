"""
Agent Route — POST /api/agent/run
Exposes the multi-step agent directly for complex tasks.
"""

import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ai.agent import agent, AgentPlan
from ai.memory_system import memory_system

router = APIRouter()


class AgentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    force_agent: bool = Field(False, description="Force multi-step even for simple queries")


class StepResult(BaseModel):
    step_id: int
    action: str
    output: str
    duration_ms: float
    error: Optional[str] = None


class AgentResponse(BaseModel):
    final_response: str
    steps: list[StepResult]
    total_duration_ms: float
    step_count: int
    session_id: str
    is_multi_step: bool


@router.post("/agent/run", response_model=AgentResponse, summary="Run multi-step AI agent")
async def run_agent(request: AgentRequest):
    """
    Execute a complex query through the multi-step agent.

    The agent will:
    1. Plan the steps needed
    2. Execute each step sequentially
    3. Synthesize a final combined response

    Example multi-step queries:
    - "Analyze this PDF, give me key points, and translate to Tamil"
    - "Calculate the area, then summarize what it means"
    """
    session_id = request.session_id or str(uuid.uuid4())

    try:
        plan: AgentPlan = await agent.run(
            request.query,
            force_agent=request.force_agent
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    memory_system.add_turn(session_id, "user", request.query)
    memory_system.add_turn(session_id, "assistant", plan.final_response)

    return AgentResponse(
        final_response=plan.final_response,
        steps=[
            StepResult(
                step_id=s.step_id,
                action=s.action,
                output=s.output,
                duration_ms=s.duration_ms,
                error=s.error,
            )
            for s in plan.steps
        ],
        total_duration_ms=plan.total_duration_ms,
        step_count=len(plan.steps),
        session_id=session_id,
        is_multi_step=plan.is_agent,
    )
