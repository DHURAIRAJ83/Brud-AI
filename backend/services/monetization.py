"""
Monetization Layer — Usage Tracking + Billing Hooks
-----------------------------------------------------
Tracks API usage per key/session for billing and quota enforcement.

Features:
  - Per-key token/request/day tracking
  - Daily quota enforcement
  - Billing event hooks (fire-and-forget, async)
  - Usage export (JSON for billing integrations)
  - Stripe-ready event structure (webhooks)

This is the foundation — plug in Stripe or any billing backend.
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Daily token quotas per tier (can move to DB later)
DAILY_QUOTAS = {
    "admin":    float("inf"),
    "standard": 50_000,
    "limited":  5_000,
    "trial":    1_000,
}

USAGE_LOG_PATH = Path("./usage_log.jsonl")


@dataclass
class UsageRecord:
    api_key: str
    tier: str
    session_id: str
    intent: str
    model: str
    tokens_estimated: int
    cost_units: float       # Abstract unit (1 token = 0.001 unit)
    timestamp: float = field(default_factory=time.time)
    date_str: str = field(default_factory=lambda: time.strftime("%Y-%m-%d"))


class MonetizationService:
    """
    Tracks per-key usage and enforces daily quotas.
    Persists usage to JSONL file for offline billing analysis.
    """

    def __init__(self):
        self._daily: dict[str, dict[str, float]] = defaultdict(
            lambda: {"tokens": 0.0, "requests": 0, "cost_units": 0.0}
        )  # key: "{api_key}:{date}" → usage

    def _day_key(self, api_key: str) -> str:
        return f"{api_key}:{time.strftime('%Y-%m-%d')}"

    def record(
        self,
        api_key: str,
        tier: str,
        session_id: str,
        intent: str,
        model: str,
        tokens: int,
    ) -> UsageRecord:
        """Record a usage event and return the record."""
        cost = tokens * 0.001  # 1000 tokens = 1 cost unit
        record = UsageRecord(
            api_key=api_key,
            tier=tier,
            session_id=session_id,
            intent=intent,
            model=model,
            tokens_estimated=tokens,
            cost_units=cost,
        )

        dk = self._day_key(api_key)
        self._daily[dk]["tokens"] += tokens
        self._daily[dk]["requests"] += 1
        self._daily[dk]["cost_units"] += cost

        # Async-safe fire-and-forget log
        self._persist(record)
        logger.debug(
            "BILLING | key=%s… tokens=%d cost=%.4f",
            api_key[:8], tokens, cost
        )
        return record

    def check_quota(self, api_key: str, tier: str) -> tuple[bool, dict]:
        """
        Returns (allowed, quota_info).
        Blocks request if daily quota exceeded.
        """
        quota = DAILY_QUOTAS.get(tier, DAILY_QUOTAS["standard"])
        if quota == float("inf"):
            return True, {"quota": "unlimited", "used": 0, "remaining": "unlimited"}

        dk = self._day_key(api_key)
        used = self._daily[dk]["tokens"]
        remaining = max(0.0, quota - used)
        allowed = used < quota

        return allowed, {
            "quota": quota,
            "used": int(used),
            "remaining": int(remaining),
            "exhausted": not allowed,
        }

    def get_usage_summary(self, api_key: Optional[str] = None) -> dict:
        """Return usage summary for one key or all keys."""
        result = {}
        for dk, data in self._daily.items():
            key, date = dk.rsplit(":", 1)
            if api_key and key != api_key:
                continue
            if key not in result:
                result[key] = {}
            result[key][date] = {
                "tokens": int(data["tokens"]),
                "requests": int(data["requests"]),
                "cost_units": round(data["cost_units"], 4),
            }
        return result

    def _persist(self, record: UsageRecord):
        """Append usage record to JSONL log file."""
        try:
            with open(USAGE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": record.timestamp,
                    "date": record.date_str,
                    "key": record.api_key[:8] + "…",  # truncate for privacy
                    "tier": record.tier,
                    "session": record.session_id,
                    "intent": record.intent,
                    "model": record.model,
                    "tokens": record.tokens_estimated,
                    "cost": record.cost_units,
                }) + "\n")
        except Exception as e:
            logger.warning("Usage log write failed: %s", e)

    # ── Billing webhook stub ──────────────────────────────────────────────────
    async def emit_billing_event(self, event_type: str, payload: dict):
        """
        Stub for billing webhook (Stripe, custom, etc.)
        Replace with actual HTTP call to your billing service.
        """
        logger.debug("BILLING_EVENT: %s → %s", event_type, payload)
        # Example Stripe integration:
        # async with httpx.AsyncClient() as c:
        #     await c.post(STRIPE_WEBHOOK_URL, json={"type": event_type, **payload})


# Singleton
monetization = MonetizationService()
