"""
Observability System — Request/Response Tracking
--------------------------------------------------
Lightweight observability without heavy dependencies.
Tracks: latency, token estimates, error rates, model usage, intent distribution.

Exposes: GET /api/metrics  →  JSON dashboard
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RequestRecord:
    session_id: str
    intent: str
    model: str
    source: str
    duration_ms: float
    estimated_tokens: int
    error: Optional[str]
    timestamp: float = field(default_factory=time.time)
    is_agent: bool = False


class ObservabilityService:
    """
    Stores recent request records and aggregates metrics.
    Keeps only last 1000 requests in-memory (circular buffer).
    """

    MAX_RECORDS = 1000
    RECENT_WINDOW_S = 300  # 5-minute window for recent stats

    def __init__(self):
        self._records: deque[RequestRecord] = deque(maxlen=self.MAX_RECORDS)
        self._error_count = 0
        self._total_count = 0
        self._start_time = time.time()

    def record(
        self,
        session_id: str,
        intent: str,
        model: str,
        source: str,
        duration_ms: float,
        prompt: str = "",
        response: str = "",
        error: Optional[str] = None,
        is_agent: bool = False,
    ):
        """Log a completed request."""
        # Rough token estimate: ~0.75 words per token
        tokens = int((len(prompt.split()) + len(response.split())) / 0.75)

        rec = RequestRecord(
            session_id=session_id,
            intent=intent,
            model=model,
            source=source,
            duration_ms=duration_ms,
            estimated_tokens=tokens,
            error=error,
            is_agent=is_agent,
        )
        self._records.append(rec)
        self._total_count += 1
        if error:
            self._error_count += 1

        logger.debug(
            "OBS | intent=%s model=%s %.0fms tokens≈%d%s",
            intent, model, duration_ms, tokens,
            f" ERR={error}" if error else "",
        )

    def _recent_records(self) -> list[RequestRecord]:
        cutoff = time.time() - self.RECENT_WINDOW_S
        return [r for r in self._records if r.timestamp >= cutoff]

    def get_metrics(self) -> dict:
        """Aggregate and return all metrics for the dashboard."""
        recent = self._recent_records()
        all_recs = list(self._records)
        uptime_s = int(time.time() - self._start_time)

        # Latency stats
        if all_recs:
            latencies = [r.duration_ms for r in all_recs]
            avg_lat = sum(latencies) / len(latencies)
            p95_lat = sorted(latencies)[int(len(latencies) * 0.95)]
            max_lat = max(latencies)
        else:
            avg_lat = p95_lat = max_lat = 0.0

        # Intent distribution
        intent_dist: dict[str, int] = defaultdict(int)
        for r in all_recs:
            intent_dist[r.intent] += 1

        # Model usage
        model_usage: dict[str, int] = defaultdict(int)
        for r in all_recs:
            model_usage[r.model] += 1

        # Source distribution
        source_dist: dict[str, int] = defaultdict(int)
        for r in all_recs:
            source_dist[r.source] += 1

        # Recent (5-min) stats
        recent_rps = len(recent) / self.RECENT_WINDOW_S if recent else 0

        return {
            "uptime_seconds": uptime_s,
            "total_requests": self._total_count,
            "total_errors": self._error_count,
            "error_rate": round(
                self._error_count / max(self._total_count, 1), 4
            ),
            "latency_ms": {
                "avg": round(avg_lat, 1),
                "p95": round(p95_lat, 1),
                "max": round(max_lat, 1),
            },
            "recent_5min": {
                "request_count": len(recent),
                "requests_per_second": round(recent_rps, 3),
                "total_tokens_estimated": sum(r.estimated_tokens for r in recent),
            },
            "intent_distribution": dict(intent_dist),
            "model_usage": dict(model_usage),
            "source_distribution": dict(source_dist),
            "agent_requests": sum(1 for r in all_recs if r.is_agent),
            "records_buffered": len(self._records),
        }

    def get_recent_errors(self, limit: int = 20) -> list[dict]:
        return [
            {
                "timestamp": r.timestamp,
                "intent": r.intent,
                "model": r.model,
                "error": r.error,
                "duration_ms": r.duration_ms,
            }
            for r in reversed(list(self._records))
            if r.error
        ][:limit]


# Singleton
obs_service = ObservabilityService()
