"""EROS v1.0 Performance Tracker for Delayed Feedback Collection (<150 lines).

Collects learning signals 7-14 days after schedule deployment.
Outperformer: RPS > median * 1.2 | Underperformer: RPS < median * 0.7
Confidence: MEDIUM if sample_size >= 10, LOW otherwise.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .feedback import FeedbackCapture, LearningSignal


class MCPClient(Protocol):
    """MCP client protocol for performance tracking."""
    async def get_performance_trends(self, creator_id: str, period: str) -> dict: ...


@dataclass(frozen=True, slots=True)
class SchedulePerformance:
    """Aggregated performance metrics for a deployed schedule."""
    schedule_id: int
    creator_id: str
    deployed_date: str
    rps: float
    median_rps: float
    conversion_rate: float
    baseline_conversion: float
    open_rate: float
    baseline_open_rate: float
    sample_size: int


class PerformanceTracker:
    """Tracks schedule performance and generates learning signals 7-14 days post-deployment."""

    MATURITY_DAYS = 7

    def __init__(self, mcp: MCPClient, feedback: FeedbackCapture):
        """Initialize with MCP client and feedback capture system."""
        self._mcp, self._feedback = mcp, feedback

    async def collect_feedback(self, schedule_id: int, deployed_date: str) -> list[LearningSignal]:
        """Collect feedback for a single schedule if mature (>= 7 days old)."""
        if not self._is_mature(deployed_date):
            return []
        performance = await self._fetch_performance(schedule_id, deployed_date)
        if not performance:
            return []
        signals = self._analyze_performance(performance)
        if signals:
            self._feedback.persist_signals(signals)
        return signals

    async def batch_collect(self, since_date: str, until_date: str) -> dict[str, Any]:
        """Batch collect feedback for all schedules in date range."""
        # Placeholder: Real impl would query schedule_templates for deployed schedules
        return {"schedules_analyzed": 0, "signals_captured": 0, "date_range": f"{since_date} to {until_date}"}

    def _is_mature(self, deployed_date: str) -> bool:
        """Check if schedule is at least 7 days old."""
        try:
            return (datetime.now() - datetime.fromisoformat(deployed_date)).days >= self.MATURITY_DAYS
        except ValueError:
            return False

    async def _fetch_performance(self, schedule_id: int, deployed_date: str) -> SchedulePerformance | None:
        """Fetch performance metrics for a schedule."""
        try:
            creator_id = "unknown"  # Real impl fetches from schedule
            trends = await self._mcp.get_performance_trends(creator_id, "14d")
            if not trends or "error" in trends:
                return None
            return SchedulePerformance(
                schedule_id=schedule_id, creator_id=creator_id, deployed_date=deployed_date,
                rps=trends.get("rps", 0.0), median_rps=trends.get("median_rps", 0.0),
                conversion_rate=trends.get("conversion_rate", 0.0),
                baseline_conversion=trends.get("baseline_conversion", 0.0),
                open_rate=trends.get("open_rate", 0.0),
                baseline_open_rate=trends.get("baseline_open_rate", 0.0),
                sample_size=trends.get("sample_size", 0))
        except Exception:
            return None

    def _analyze_performance(self, perf: SchedulePerformance) -> list[LearningSignal]:
        """Analyze performance and generate learning signals."""
        signals, now = [], datetime.now().isoformat()
        conf = "MEDIUM" if perf.sample_size >= 10 else "LOW"
        base_meta = {"schedule_id": perf.schedule_id, "rps": perf.rps}

        if self._is_outperformer(perf):
            signals.append(LearningSignal(
                timestamp=now, title=f"Outperformer: RPS ${perf.rps:.2f}",
                pattern=f"Schedule {perf.schedule_id} exceeded median by 20%+",
                source="performance", confidence=conf,
                insight=f"RPS ${perf.rps:.2f} vs median ${perf.median_rps:.2f}",
                sample_size=perf.sample_size, applies_to=f"creator:{perf.creator_id}",
                metadata={**base_meta, "rps_ratio": perf.rps / max(perf.median_rps, 0.01)}))

        if self._is_underperformer(perf):
            signals.append(LearningSignal(
                timestamp=now, title=f"Underperformer: RPS ${perf.rps:.2f}",
                pattern=f"Schedule {perf.schedule_id} below median by 30%+",
                source="performance", confidence=conf,
                insight=f"RPS ${perf.rps:.2f} vs median ${perf.median_rps:.2f}",
                sample_size=perf.sample_size, applies_to=f"creator:{perf.creator_id}",
                metadata={**base_meta, "rps_ratio": perf.rps / max(perf.median_rps, 0.01)}))

        if perf.baseline_open_rate > 0:
            delta = ((perf.open_rate - perf.baseline_open_rate) / perf.baseline_open_rate) * 100
            if delta <= -10:
                signals.append(LearningSignal(
                    timestamp=now, title=f"Open Rate Decline: {delta:.1f}%",
                    pattern=f"Schedule {perf.schedule_id} open rate dropped significantly",
                    source="performance", confidence=conf,
                    insight=f"Open rate {perf.open_rate:.1%} vs baseline {perf.baseline_open_rate:.1%}",
                    sample_size=perf.sample_size, applies_to=f"creator:{perf.creator_id}",
                    metadata={**base_meta, "open_rate_delta_pct": delta}))
        return signals

    def _is_outperformer(self, perf: SchedulePerformance) -> bool:
        """RPS > median * 1.2 (20% above median)."""
        return perf.median_rps > 0 and perf.rps > perf.median_rps * 1.2

    def _is_underperformer(self, perf: SchedulePerformance) -> bool:
        """RPS < median * 0.7 (30% below median)."""
        return perf.median_rps > 0 and perf.rps < perf.median_rps * 0.7


__all__ = ["PerformanceTracker", "SchedulePerformance"]
