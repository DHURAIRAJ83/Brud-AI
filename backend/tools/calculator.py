"""
Calculator Tool
---------------
Evaluates safe mathematical expressions.
Uses Python's AST-based eval (no exec / no arbitrary code).
Falls back to LLM for word problems.
"""

import ast
import logging
import operator
import re

logger = logging.getLogger(__name__)

# Allowed operators
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    """Recursively evaluate an AST node (no builtins, no imports)."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported unary operator")
        return op(_safe_eval(node.operand))
    else:
        raise ValueError(f"Unsupported expression: {type(node).__name__}")


def _extract_expression(text: str) -> str:
    """Extract a math expression from natural language."""
    # Look for patterns like "calculate 2 + 3" or "what is 10 * 5"
    patterns = [
        r"(?:calculate|compute|eval|what is|கணக்கு)\s+(.+)",
        r"(\d[\d\s\+\-\*\/\.\(\)\^%]+\d)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return text.strip()


async def calculate_tool(user_message: str, **_) -> str:
    expr_str = _extract_expression(user_message)
    # Replace ^ with ** for exponentiation
    expr_str = expr_str.replace("^", "**")

    try:
        tree = ast.parse(expr_str, mode="eval")
        result = _safe_eval(tree.body)
        # Format nicely
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"Result: {expr_str} = **{result}**"
    except Exception as e:
        logger.info("Direct eval failed (%s), falling back to LLM", e)

    # Fallback: ask LLM to solve word problem
    from ai.ollama_client import ollama_client
    answer = await ollama_client.generate(
        prompt=f"Solve this math problem step by step:\n{user_message}\n\nAnswer:",
        temperature=0.1,
        max_tokens=256,
    )
    return answer
