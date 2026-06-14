import pytest
from ai.action_planner import action_planner, TrustLevel
from ai.command_parser import DesktopAction

def test_safe_trust_level():
    action = DesktopAction(
        tool="desktop.open_app",
        params={"app": "vscode"},
        confidence=0.9
    )
    plan = action_planner.plan(action)
    assert plan.trust_level == TrustLevel.SAFE
    assert plan.strategy.value == "execute"

def test_caution_trust_level():
    action = DesktopAction(
        tool="files.create_folder",
        params={"name": "test"},
        confidence=0.9
    )
    plan = action_planner.plan(action)
    assert plan.trust_level == TrustLevel.CAUTION
    assert plan.strategy.value == "await_approval"

def test_dangerous_trust_level():
    action = DesktopAction(
        tool="files.delete",
        params={"path": "important.txt"},
        confidence=0.9
    )
    plan = action_planner.plan(action)
    assert plan.trust_level == TrustLevel.DANGEROUS
    assert plan.strategy.value == "double_confirm"

def test_low_confidence_requires_approval():
    # Even a SAFE action requires approval if confidence is too low (< 0.7)
    action = DesktopAction(
        tool="desktop.open_app",
        params={"app": "unknown"},
        confidence=0.5
    )
    plan = action_planner.plan(action)
    assert plan.strategy.value == "await_approval"
