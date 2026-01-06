"""EROS v1.0 Production Monitoring (<100 lines).

Tracks pipeline metrics, health checks, and rollback trigger conditions.

SLOs:
- Success rate: Warning <95%, Critical <90%, Rollback <85% for 5 min
- P95 latency: Warning >90s, Critical >120s, Rollback >180s for 3 runs
- Hard gate violations: Warning >2%, Critical >5%, Rollback >10%
- Quality score avg: Warning <80, Critical <75, Rollback <70 for 10 runs
"""
from __future__ import annotations
import json, logging, time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .orchestrator import PipelineResult

logger = logging.getLogger("eros.monitoring")

class Severity(Enum):
    INFO = "info"; WARNING = "warning"; CRITICAL = "critical"

class HealthStatus(Enum):
    HEALTHY = "healthy"; DEGRADED = "degraded"; UNHEALTHY = "unhealthy"

@dataclass
class SLOConfig:
    success_rate_warn: float = 0.95; success_rate_crit: float = 0.90; success_rate_rollback: float = 0.85
    latency_p95_warn: float = 90000; latency_p95_crit: float = 120000; latency_p95_rollback: float = 180000
    hard_gate_rate_warn: float = 0.02; hard_gate_rate_crit: float = 0.05; hard_gate_rate_rollback: float = 0.10
    quality_avg_warn: int = 80; quality_avg_crit: int = 75; quality_avg_rollback: int = 70
    rollback_window: int = 10  # last N runs for rollback decision

@dataclass
class PipelineMetrics:
    """Sliding window metrics for SLO evaluation."""
    window_size: int = 100
    executions: deque = field(default_factory=lambda: deque(maxlen=100))
    total_runs: int = 0; total_success: int = 0; total_hard_gate_violations: int = 0

    def record(self, result: "PipelineResult") -> None:
        self.total_runs += 1
        entry = {"success": result.success, "duration_ms": result.metrics.get("total_duration_ms", 0),
                 "quality_score": result.quality_score, "hard_gate": any("VAULT" in e or "AVOID" in e for e in result.errors),
                 "timestamp": time.time()}
        self.executions.append(entry)
        if result.success: self.total_success += 1
        if entry["hard_gate"]: self.total_hard_gate_violations += 1

    def success_rate(self, window: int = None) -> float:
        w = list(self.executions)[-window:] if window else list(self.executions)
        return sum(1 for e in w if e["success"]) / max(len(w), 1)

    def p95_latency(self, window: int = None) -> float:
        w = list(self.executions)[-window:] if window else list(self.executions)
        if not w: return 0
        latencies = sorted(e["duration_ms"] for e in w)
        idx = int(len(latencies) * 0.95)
        return latencies[min(idx, len(latencies) - 1)]

    def hard_gate_rate(self, window: int = None) -> float:
        w = list(self.executions)[-window:] if window else list(self.executions)
        return sum(1 for e in w if e.get("hard_gate")) / max(len(w), 1)

    def avg_quality(self, window: int = None) -> float:
        w = list(self.executions)[-window:] if window else list(self.executions)
        scores = [e["quality_score"] for e in w if e["success"]]
        return sum(scores) / max(len(scores), 1)

class PipelineMonitor:
    """Production monitoring with SLO-based health checks."""
    def __init__(self, config: SLOConfig = None):
        self.config = config or SLOConfig()
        self.metrics = PipelineMetrics(window_size=self.config.rollback_window * 10)

    def record_execution(self, result: "PipelineResult") -> None:
        self.metrics.record(result)
        self._log_execution(result)

    def _log_execution(self, result: "PipelineResult") -> None:
        log = {"creator": result.creator_id, "success": result.success, "quality": result.quality_score,
               "duration_ms": result.metrics.get("total_duration_ms", 0), "items": result.total_items}
        logger.info(f"Pipeline execution: {json.dumps(log)}")

    def check_health(self) -> HealthStatus:
        c = self.config; m = self.metrics
        if m.total_runs < 5: return HealthStatus.HEALTHY
        sr = m.success_rate(); lat = m.p95_latency(); hgr = m.hard_gate_rate(); qa = m.avg_quality()
        if sr < c.success_rate_crit or lat > c.latency_p95_crit or hgr > c.hard_gate_rate_crit or qa < c.quality_avg_crit:
            return HealthStatus.UNHEALTHY
        if sr < c.success_rate_warn or lat > c.latency_p95_warn or hgr > c.hard_gate_rate_warn or qa < c.quality_avg_warn:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def should_rollback(self) -> tuple[bool, str]:
        c = self.config; m = self.metrics; w = c.rollback_window
        if m.total_runs < w: return False, "insufficient_data"
        sr = m.success_rate(w); lat = m.p95_latency(w); hgr = m.hard_gate_rate(w); qa = m.avg_quality(w)
        if sr < c.success_rate_rollback: return True, f"success_rate_{sr:.2f}"
        if lat > c.latency_p95_rollback: return True, f"latency_p95_{lat:.0f}ms"
        if hgr > c.hard_gate_rate_rollback: return True, f"hard_gate_rate_{hgr:.2f}"
        if qa < c.quality_avg_rollback: return True, f"quality_avg_{qa:.1f}"
        return False, "healthy"

    def get_status(self) -> dict:
        m = self.metrics
        return {"health": self.check_health().value, "total_runs": m.total_runs, "success_rate": m.success_rate(),
                "p95_latency_ms": m.p95_latency(), "hard_gate_rate": m.hard_gate_rate(), "avg_quality": m.avg_quality(),
                "should_rollback": self.should_rollback()}

__all__ = ["PipelineMonitor", "PipelineMetrics", "SLOConfig", "HealthStatus", "Severity"]
