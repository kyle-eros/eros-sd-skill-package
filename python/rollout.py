"""EROS v1.0 Rollout Automation (<150 lines).

6-phase rollout with automated phase advancement and success criteria validation.

Phases:
0. Shadow Mode (Week 1) - Run both, log comparison
1. Canary (Week 2) - 1 creator on v5
2. Early Adopters (Week 3) - 3 creators across tiers
3. Percentage (Week 4-5) - 25% -> 50% -> 75%
4. Full Cutover (Week 6) - 100% traffic
"""
from __future__ import annotations
import json, logging, os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .comparator import ComparisonMetrics
    from .monitoring import PipelineMonitor

logger = logging.getLogger("eros.rollout")

class Phase(IntEnum):
    SHADOW = 0; CANARY = 1; EARLY_ADOPTERS = 2; PERCENTAGE_25 = 3
    PERCENTAGE_50 = 4; PERCENTAGE_75 = 5; FULL_CUTOVER = 6

PHASE_CONFIG = {
    Phase.SHADOW: {"EROS_V5_ENABLED": "true", "EROS_V5_SHADOW_MODE": "true", "EROS_V5_PERCENTAGE": "0", "EROS_V5_CREATORS": ""},
    Phase.CANARY: {"EROS_V5_ENABLED": "true", "EROS_V5_SHADOW_MODE": "false", "EROS_V5_PERCENTAGE": "0", "EROS_V5_CREATORS": "alexia"},
    Phase.EARLY_ADOPTERS: {"EROS_V5_ENABLED": "true", "EROS_V5_SHADOW_MODE": "false", "EROS_V5_PERCENTAGE": "0", "EROS_V5_CREATORS": "alexia,grace_bennett,luna_free"},
    Phase.PERCENTAGE_25: {"EROS_V5_ENABLED": "true", "EROS_V5_SHADOW_MODE": "false", "EROS_V5_PERCENTAGE": "25", "EROS_V5_CREATORS": ""},
    Phase.PERCENTAGE_50: {"EROS_V5_ENABLED": "true", "EROS_V5_SHADOW_MODE": "false", "EROS_V5_PERCENTAGE": "50", "EROS_V5_CREATORS": ""},
    Phase.PERCENTAGE_75: {"EROS_V5_ENABLED": "true", "EROS_V5_SHADOW_MODE": "false", "EROS_V5_PERCENTAGE": "75", "EROS_V5_CREATORS": ""},
    Phase.FULL_CUTOVER: {"EROS_V5_ENABLED": "true", "EROS_V5_SHADOW_MODE": "false", "EROS_V5_PERCENTAGE": "100", "EROS_V5_CREATORS": ""},
}

@dataclass
class PhaseCriteria:
    min_runs: int = 10; min_success_rate: float = 0.95; max_quality_diff: int = 5
    max_failure_rate: float = 0.10; min_duration_hours: int = 48

@dataclass
class PhaseResult:
    phase: Phase; passed: bool; reason: str
    metrics: dict = field(default_factory=dict); timestamp: str = ""

class RolloutManager:
    """Manages 6-phase rollout with automated advancement."""

    def __init__(self, monitor: "PipelineMonitor" = None, comparison_metrics: "ComparisonMetrics" = None):
        self.monitor = monitor
        self.comparison = comparison_metrics
        self.current_phase = Phase.SHADOW
        self.phase_start = datetime.now()
        self.history: list[PhaseResult] = []
        self.criteria = PhaseCriteria()

    def _get_metrics(self) -> dict:
        m = {}
        if self.monitor:
            status = self.monitor.get_status()
            m.update({"success_rate": status["success_rate"], "quality_avg": status["avg_quality"],
                      "total_runs": status["total_runs"]})
        if self.comparison:
            m.update({"v5_better": self.comparison.v5_better, "v5_failed": self.comparison.v5_failed,
                      "avg_quality_diff": self.comparison.avg_quality_diff, "comparison_total": self.comparison.total})
        return m

    def check_phase_criteria(self) -> tuple[bool, str]:
        """Check if current phase success criteria are met."""
        c = self.criteria; m = self._get_metrics()

        # Duration check
        hours = (datetime.now() - self.phase_start).total_seconds() / 3600
        if hours < c.min_duration_hours:
            return False, f"min_duration_not_met ({hours:.1f}/{c.min_duration_hours}h)"

        # Shadow mode specific
        if self.current_phase == Phase.SHADOW and self.comparison:
            if self.comparison.total < c.min_runs:
                return False, f"insufficient_comparisons ({self.comparison.total}/{c.min_runs})"
            fail_rate = self.comparison.v5_failed / max(self.comparison.total, 1)
            if fail_rate > c.max_failure_rate:
                return False, f"v5_failure_rate_too_high ({fail_rate:.2%})"
            if self.comparison.avg_quality_diff < -c.max_quality_diff:
                return False, f"quality_regression ({self.comparison.avg_quality_diff:+.1f})"
            return True, "shadow_criteria_passed"

        # Live traffic phases
        if self.monitor:
            if self.monitor.metrics.total_runs < c.min_runs:
                return False, f"insufficient_runs ({self.monitor.metrics.total_runs}/{c.min_runs})"
            sr = self.monitor.metrics.success_rate()
            if sr < c.min_success_rate:
                return False, f"success_rate_too_low ({sr:.2%})"
            return True, "criteria_passed"

        return True, "no_monitor_configured"

    def advance_phase(self, force: bool = False) -> PhaseResult:
        """Advance to next rollout phase if criteria met."""
        passed, reason = self.check_phase_criteria()
        if not passed and not force:
            result = PhaseResult(self.current_phase, False, reason, self._get_metrics(), datetime.now().isoformat())
            logger.warning(f"Phase {self.current_phase.name} criteria not met: {reason}")
            return result

        if self.current_phase >= Phase.FULL_CUTOVER:
            return PhaseResult(self.current_phase, True, "already_complete", self._get_metrics(), datetime.now().isoformat())

        # Apply next phase config
        next_phase = Phase(self.current_phase + 1)
        config = PHASE_CONFIG[next_phase]
        for k, v in config.items():
            os.environ[k] = v

        self.history.append(PhaseResult(self.current_phase, True, "advanced", self._get_metrics(), datetime.now().isoformat()))
        self.current_phase = next_phase
        self.phase_start = datetime.now()
        logger.info(f"Advanced to phase {next_phase.name}: {config}")
        return PhaseResult(next_phase, True, "phase_activated", self._get_metrics(), datetime.now().isoformat())

    def generate_report(self) -> str:
        m = self._get_metrics(); passed, reason = self.check_phase_criteria()
        hours = (datetime.now() - self.phase_start).total_seconds() / 3600
        return f"""EROS v1.0 Rollout Status Report
================================
Current Phase: {self.current_phase.name}
Phase Duration: {hours:.1f}h
Criteria Met: {passed} ({reason})
Metrics: {json.dumps(m, indent=2)}
History: {len(self.history)} phase transitions"""

    def get_status(self) -> dict:
        passed, reason = self.check_phase_criteria()
        return {"phase": self.current_phase.name, "phase_num": int(self.current_phase), "criteria_passed": passed,
                "criteria_reason": reason, "metrics": self._get_metrics(), "history_count": len(self.history)}

__all__ = ["RolloutManager", "Phase", "PhaseCriteria", "PhaseResult", "PHASE_CONFIG"]
