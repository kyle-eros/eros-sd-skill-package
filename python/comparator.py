"""EROS v1.0 Shadow Mode Comparator (<120 lines).

Runs v4 and v5 pipelines in parallel, compares results, logs differences.
Used to validate v5 produces equivalent or better schedules before cutover.
"""
from __future__ import annotations
import asyncio, json, logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .orchestrator import MCPClient, TaskTool, PipelineResult

logger = logging.getLogger("eros.comparator")

@dataclass
class ComparisonResult:
    creator_id: str
    week_start: str
    v4_duration_ms: float
    v5_duration_ms: float
    items_match: bool
    quality_diff: int  # v5 - v4
    hard_gate_violations: dict = field(default_factory=dict)
    recommendation: str = "equivalent"  # v5_better | equivalent | v4_better | v5_failed
    details: dict = field(default_factory=dict)

@dataclass
class ComparisonMetrics:
    """Tracks comparison metrics over time."""
    total: int = 0; v5_better: int = 0; equivalent: int = 0
    v4_better: int = 0; v5_failed: int = 0
    avg_quality_diff: float = 0.0; avg_speedup: float = 0.0

    def record(self, result: ComparisonResult) -> None:
        self.total += 1
        if result.recommendation == "v5_better": self.v5_better += 1
        elif result.recommendation == "equivalent": self.equivalent += 1
        elif result.recommendation == "v4_better": self.v4_better += 1
        else: self.v5_failed += 1
        # Rolling averages
        self.avg_quality_diff = (self.avg_quality_diff * (self.total - 1) + result.quality_diff) / self.total
        speedup = (result.v4_duration_ms - result.v5_duration_ms) / max(result.v4_duration_ms, 1) * 100
        self.avg_speedup = (self.avg_speedup * (self.total - 1) + speedup) / self.total

_metrics = ComparisonMetrics()

def _extract_items(result: "PipelineResult | dict") -> list:
    if hasattr(result, "metrics"):
        return result.metrics.get("items", [])
    return result.get("items", result.get("schedule", {}).get("items", []))

def _extract_quality(result: "PipelineResult | dict") -> int:
    if hasattr(result, "quality_score"): return result.quality_score
    return result.get("quality_score", result.get("validation", {}).get("quality_score", 0))

def _check_hard_gates(v5_result: "PipelineResult") -> dict:
    """Check if v5 failed any hard gates that v4 passed."""
    violations = {}
    if not v5_result.success:
        for err in v5_result.errors:
            if "VAULT" in err.upper(): violations["vault"] = err
            if "AVOID" in err.upper(): violations["avoid_tier"] = err
            if "DIVERSITY" in err.upper(): violations["diversity"] = err
    return violations

async def compare(v4_result: dict, v5_result: "PipelineResult", creator_id: str, week_start: str) -> ComparisonResult:
    """Compare v4 and v5 pipeline results."""
    v4_items = _extract_items(v4_result); v5_items = _extract_items(v5_result)
    v4_quality = _extract_quality(v4_result); v5_quality = v5_result.quality_score
    v4_ms = v4_result.get("duration_ms", v4_result.get("metrics", {}).get("total_duration_ms", 0))
    v5_ms = v5_result.metrics.get("total_duration_ms", 0)

    items_match = abs(len(v4_items) - len(v5_items)) <= len(v4_items) * 0.1  # ±10%
    quality_diff = v5_quality - v4_quality
    hard_gates = _check_hard_gates(v5_result)

    if not v5_result.success:
        rec = "v5_failed"
    elif hard_gates:
        rec = "v5_failed"
    elif quality_diff >= 5 and items_match:
        rec = "v5_better"
    elif quality_diff <= -5:
        rec = "v4_better"
    else:
        rec = "equivalent"

    result = ComparisonResult(creator_id, week_start, v4_ms, v5_ms, items_match, quality_diff, hard_gates, rec,
        {"v4_items": len(v4_items), "v5_items": len(v5_items), "v4_quality": v4_quality, "v5_quality": v5_quality})

    _metrics.record(result)
    logger.info(f"Shadow comparison: {creator_id} - {rec} (quality_diff={quality_diff:+d}, v4={v4_ms:.0f}ms, v5={v5_ms:.0f}ms)")
    return result

async def run_shadow_comparison(mcp: "MCPClient", task: "TaskTool", creator_id: str, week_start: str,
                                 v4_runner: Callable) -> "PipelineResult":
    """Run both pipelines in parallel, compare, return v4 result (production)."""
    from .orchestrator import generate_schedule as v5_generate

    v4_task = asyncio.create_task(v4_runner(creator_id, week_start))
    v5_task = asyncio.create_task(v5_generate(mcp, task, creator_id, week_start))

    v4_result, v5_result = await asyncio.gather(v4_task, v5_task, return_exceptions=True)

    if isinstance(v4_result, Exception):
        logger.error(f"V4 failed in shadow mode: {v4_result}")
        raise v4_result

    if isinstance(v5_result, Exception):
        logger.warning(f"V5 failed in shadow mode (continuing with v4): {v5_result}")
        from .orchestrator import PipelineResult
        v5_result = PipelineResult(False, creator_id, week_start, errors=[str(v5_result)])

    await compare(v4_result, v5_result, creator_id, week_start)
    return v4_result  # Shadow mode returns v4 for production

def get_metrics() -> ComparisonMetrics:
    return _metrics

def generate_report() -> str:
    m = _metrics
    return f"""Shadow Mode Comparison Report
Total: {m.total} | v5_better: {m.v5_better} | equivalent: {m.equivalent} | v4_better: {m.v4_better} | v5_failed: {m.v5_failed}
Avg quality diff: {m.avg_quality_diff:+.1f} | Avg speedup: {m.avg_speedup:.1f}%"""

__all__ = ["ComparisonResult", "ComparisonMetrics", "compare", "run_shadow_comparison", "get_metrics", "generate_report"]
