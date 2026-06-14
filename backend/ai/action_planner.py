"""
Action Planner — Agent Decision Engine
-----------------------------------------
Determines HOW a parsed desktop command should be executed:
  - Direct execution (SAFE actions)
  - Queue for user approval (CAUTION actions)
  - Double confirmation (DANGEROUS actions)
  - Multi-step decomposition (complex workflows)
  - Rejection (blocked/impossible actions)

Trust Levels:
  SAFE      → Auto-execute: open_app, search, list_files, screen.capture
  CAUTION   → User approval: create_folder, rename, git_commit
  DANGEROUS → Double confirmation: delete, run_script, registry_edit

Future expansion:
  - Multi-step plans (e.g., "create project and open in VS Code")
  - Context-aware decisions (e.g., "close all apps" needs confirmation)
  - Learning from user patterns (auto-approve frequent CAUTION actions)
"""

import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from ai.command_parser import DesktopAction

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────────────────

class ExecutionStrategy(str, Enum):
    EXECUTE = "execute"                 # Direct execution (SAFE)
    AWAIT_APPROVAL = "await_approval"   # Needs user confirmation (CAUTION)
    DOUBLE_CONFIRM = "double_confirm"   # Needs explicit "yes" twice (DANGEROUS)
    DECOMPOSE = "decompose"             # Break into sub-steps
    REJECT = "reject"                   # Block the action
    PASSTHROUGH = "passthrough"         # Not a desktop command → chat/LLM


class TrustLevel(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"


# ── Planning Result ───────────────────────────────────────────────────────────

class ActionPlan(BaseModel):
    """Result of the action planner — what to do with a parsed command."""
    action: DesktopAction
    strategy: ExecutionStrategy
    trust_level: TrustLevel
    reason: str = ""
    confirmation_message: str = ""      # Message to show user for approval
    sub_steps: list[dict] = Field(default_factory=list)  # For DECOMPOSE strategy
    blocked_reason: str = ""            # For REJECT strategy


# ── Trust Level Classification ────────────────────────────────────────────────

TOOL_TRUST: dict[str, TrustLevel] = {
    # ── SAFE — Auto-execute ────────────────────────────────────────────────
    "desktop.open_app":     TrustLevel.SAFE,
    "desktop.list_apps":    TrustLevel.SAFE,
    "browser.open":         TrustLevel.SAFE,
    "browser.search":       TrustLevel.SAFE,
    "files.list":           TrustLevel.SAFE,
    "files.search":         TrustLevel.SAFE,
    "files.read":           TrustLevel.SAFE,
    "screen.capture":       TrustLevel.SAFE,
    "screen.ocr":           TrustLevel.SAFE,
    "process.list":         TrustLevel.SAFE,
    "chat":                 TrustLevel.SAFE,

    # ── CAUTION — User approval ────────────────────────────────────────────
    "desktop.close_app":    TrustLevel.CAUTION,
    "files.create_folder":  TrustLevel.CAUTION,
    "files.rename":         TrustLevel.CAUTION,
    "files.move":           TrustLevel.CAUTION,
    "files.copy":           TrustLevel.CAUTION,
    "git.commit":           TrustLevel.CAUTION,
    "git.push":             TrustLevel.CAUTION,
    "git.pull":             TrustLevel.CAUTION,
    "vscode.create_project": TrustLevel.CAUTION,
    "vscode.create_file":   TrustLevel.CAUTION,

    # ── DANGEROUS — Double confirmation ────────────────────────────────────
    "files.delete":         TrustLevel.DANGEROUS,
    "process.kill":         TrustLevel.DANGEROUS,
    "script.execute":       TrustLevel.DANGEROUS,
    "git.force_push":       TrustLevel.DANGEROUS,

    # ── BLOCKED — Never execute ────────────────────────────────────────────
    "system.shutdown":      TrustLevel.BLOCKED,
    "system.restart":       TrustLevel.BLOCKED,
    "system.registry_edit": TrustLevel.BLOCKED,
    "system.format":        TrustLevel.BLOCKED,
}

# Confirmation messages in Tamil + English
CONFIRMATION_MESSAGES: dict[str, str] = {
    "desktop.close_app": "'{app}' application-ஐ மூட வேண்டுமா? | Close '{app}'?",
    "files.create_folder": "'{name}' என்ற folder உருவாக்கவா? | Create folder '{name}'?",
    "files.rename": "File-ஐ rename செய்யவா? | Rename the file?",
    "files.delete": "⚠️ '{path}' DELETE செய்யப்படும்! உறுதியா? | ⚠️ '{path}' will be DELETED! Are you sure?",
    "process.kill": "⚠️ '{name}' process-ஐ kill செய்யவா? | Kill process '{name}'?",
    "script.execute": "⚠️ Script execute செய்ய permission வேண்டும்! | Script execution requires permission!",
    "git.commit": "Git commit செய்யவா? | Commit changes?",
    "git.push": "Git push செய்யவா? | Push changes to remote?",
}

BLOCKED_MESSAGES: dict[str, str] = {
    "system.shutdown": "🚫 System shutdown blocked for safety | பாதுகாப்புக்காக System shutdown தடுக்கப்பட்டது",
    "system.restart": "🚫 System restart blocked for safety | பாதுகாப்புக்காக System restart தடுக்கப்பட்டது",
    "system.format": "🚫 Disk format is permanently blocked | Disk format நிரந்தரமாக தடுக்கப்பட்டுள்ளது",
    "system.registry_edit": "🚫 Registry editing is blocked | Registry editing தடுக்கப்பட்டுள்ளது",
}


# ── Multi-step Detection ──────────────────────────────────────────────────────

MULTI_STEP_SIGNALS = [
    " and ", " then ", " பின்னர் ", " அதன்பிறகு ", " also ",
    " after that ", " மற்றும் ", " plus ",
]


# ── Action Planner ────────────────────────────────────────────────────────────

class ActionPlanner:
    """
    Decides execution strategy for parsed desktop commands.
    Core decision engine of the Rudran AI Agent.
    """

    def plan(self, action: DesktopAction) -> ActionPlan:
        """
        Analyze a parsed action and determine execution strategy.

        Returns an ActionPlan with:
          - strategy: how to execute (direct, approval, decompose, reject)
          - trust_level: SAFE/CAUTION/DANGEROUS/BLOCKED
          - confirmation_message: what to show user (for approval)
        """

        # ── Non-desktop commands → passthrough to chat ─────────────────────
        if not action.is_desktop_command or action.tool == "chat":
            return ActionPlan(
                action=action,
                strategy=ExecutionStrategy.PASSTHROUGH,
                trust_level=TrustLevel.SAFE,
                reason="Not a desktop command — handled by chat/LLM",
            )

        # ── Check trust level ──────────────────────────────────────────────
        trust = TOOL_TRUST.get(action.tool, TrustLevel.CAUTION)

        # ── BLOCKED → Reject ──────────────────────────────────────────────
        if trust == TrustLevel.BLOCKED:
            return ActionPlan(
                action=action,
                strategy=ExecutionStrategy.REJECT,
                trust_level=TrustLevel.BLOCKED,
                reason="Action is permanently blocked for safety",
                blocked_reason=BLOCKED_MESSAGES.get(
                    action.tool,
                    "🚫 This action is blocked | இந்த செயல் தடுக்கப்பட்டுள்ளது"
                ),
            )

        # ── Check for multi-step commands ──────────────────────────────────
        if self._is_multi_step(action.raw_input):
            from ai.command_parser import command_parser
            parts = command_parser.decompose_multi_step(action.raw_input)
            sub_steps = []
            max_trust = TrustLevel.SAFE
            
            for part in parts:
                sub_action = command_parser.rule_parser.parse(part, action.source_language)
                if not sub_action:
                    sub_action = DesktopAction(
                        tool="chat",
                        params={"message": part},
                        confidence=0.5,
                        source_language=action.source_language,
                        raw_input=part,
                        is_desktop_command=False
                    )
                sub_plan = self.plan(sub_action)
                sub_steps.append({
                    "action": sub_action.dict(),
                    "strategy": sub_plan.strategy.value,
                    "trust_level": sub_plan.trust_level.value,
                    "confirmation_message": sub_plan.confirmation_message
                })
                # Max trust level resolution
                if sub_plan.trust_level == TrustLevel.DANGEROUS:
                    max_trust = TrustLevel.DANGEROUS
                elif sub_plan.trust_level == TrustLevel.CAUTION and max_trust != TrustLevel.DANGEROUS:
                    max_trust = TrustLevel.CAUTION
            
            return ActionPlan(
                action=action,
                strategy=ExecutionStrategy.DECOMPOSE,
                trust_level=max_trust,
                reason="Multi-step command decomposed into sub-steps",
                sub_steps=sub_steps
            )

        # ── Low confidence → request approval regardless ───────────────────
        if action.confidence < 0.7:
            confirmation = self._build_confirmation(action, trust)
            return ActionPlan(
                action=action,
                strategy=ExecutionStrategy.AWAIT_APPROVAL,
                trust_level=trust,
                reason=f"Low confidence ({action.confidence:.2f}) — requesting confirmation",
                confirmation_message=confirmation,
            )

        # ── SAFE → Direct execution ────────────────────────────────────────
        if trust == TrustLevel.SAFE:
            return ActionPlan(
                action=action,
                strategy=ExecutionStrategy.EXECUTE,
                trust_level=TrustLevel.SAFE,
                reason="Safe action — auto-executing",
            )

        # ── CAUTION → User approval ───────────────────────────────────────
        if trust == TrustLevel.CAUTION:
            confirmation = self._build_confirmation(action, trust)
            return ActionPlan(
                action=action,
                strategy=ExecutionStrategy.AWAIT_APPROVAL,
                trust_level=TrustLevel.CAUTION,
                reason="Caution-level action — requires user approval",
                confirmation_message=confirmation,
            )

        # ── DANGEROUS → Double confirmation ────────────────────────────────
        confirmation = self._build_confirmation(action, trust)
        return ActionPlan(
            action=action,
            strategy=ExecutionStrategy.DOUBLE_CONFIRM,
            trust_level=TrustLevel.DANGEROUS,
            reason="Dangerous action — requires double confirmation",
            confirmation_message=f"⚠️ DANGEROUS: {confirmation}",
        )

    def _is_multi_step(self, text: str) -> bool:
        """Detect if a command is multi-step."""
        lower = text.lower()
        return any(signal in lower for signal in MULTI_STEP_SIGNALS)

    def _build_confirmation(self, action: DesktopAction, trust: TrustLevel) -> str:
        """Build a bilingual confirmation message."""
        template = CONFIRMATION_MESSAGES.get(action.tool, "")
        if template:
            try:
                return template.format(**action.params)
            except KeyError:
                return template

        # Generic confirmation
        tool_display = action.tool.replace(".", " → ")
        params_display = ", ".join(f"{k}={v}" for k, v in action.params.items())
        return f"Execute {tool_display}({params_display})? | {tool_display} செயல்படுத்தவா?"

    def get_trust_summary(self) -> dict:
        """Return a summary of trust level classifications for all tools."""
        summary: dict[str, list[str]] = {
            TrustLevel.SAFE.value: [],
            TrustLevel.CAUTION.value: [],
            TrustLevel.DANGEROUS.value: [],
            TrustLevel.BLOCKED.value: [],
        }
        for tool, trust in TOOL_TRUST.items():
            summary[trust.value].append(tool)
        return summary


# Singleton
action_planner = ActionPlanner()
