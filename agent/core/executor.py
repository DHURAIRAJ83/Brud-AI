"""
Action Executor
---------------
Routes commands to registered handlers and executes them.
"""

import logging
import time
import asyncio
from typing import Dict, Any

from actions.registry import action_registry
from core.reporter import Reporter

logger = logging.getLogger(__name__)

class ActionExecutor:
    def __init__(self, reporter: Reporter):
        self.reporter = reporter

    async def execute(self, command: dict):
        """Execute a command and report the result."""
        command_id = command["id"]
        tool = command["tool"]
        params = command.get("params", {})

        logger.info(f"Executing command: {tool} with params: {params}")

        # Report start
        execution_id = await self.reporter.report_start(command_id)
        if not execution_id:
            logger.error(f"Could not start execution for {command_id}")
            return

        handler = action_registry.get_handler(tool)
        if not handler:
            error_msg = f"No handler registered for tool: {tool}"
            logger.error(error_msg)
            await self.reporter.report_result(execution_id, "error", {}, error=error_msg)
            return

        start_time = time.perf_counter()
        try:
            # Execute the handler
            if asyncio.iscoroutinefunction(handler):
                result = await handler(params)
            else:
                result = handler(params)

            duration_ms = (time.perf_counter() - start_time) * 1000
            await self.reporter.report_result(execution_id, "success", result, duration_ms=duration_ms)

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(f"Execution failed for {tool}: {e}")
            await self.reporter.report_result(execution_id, "error", {}, error=str(e), duration_ms=duration_ms)
