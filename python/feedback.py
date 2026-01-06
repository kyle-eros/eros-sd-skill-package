"""EROS v1.0 Feedback Capture System (<200 lines).

Extracts learning signals from validation, user corrections, and performance.
Persists to LEARNINGS.md for skill improvement.

Sources: validation (HIGH for violations, MEDIUM for quality>=85),
         user (HIGH for corrections), performance (MEDIUM if sample>=10, else LOW)
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from .orchestrator import PipelineResult

LEARNINGS_PATH = Path(__file__).parent.parent / "LEARNINGS.md"
CONFIDENCE = Literal["HIGH", "MEDIUM", "LOW"]
SOURCE = Literal["validation", "user", "performance"]


@dataclass(frozen=True, slots=True)
class LearningSignal:
    """A learning signal extracted from feedback sources."""
    timestamp: str
    title: str
    pattern: str
    source: SOURCE
    confidence: CONFIDENCE
    issue: str = ""
    correction: str = ""
    insight: str = ""
    sample_size: int = 1
    applies_to: str = "all"
    metadata: dict[str, Any] = field(default_factory=dict)


class FeedbackCapture:
    """Captures learning signals and persists to LEARNINGS.md."""

    def __init__(self, learnings_path: Path | None = None):
        self.learnings_path = learnings_path or LEARNINGS_PATH

    def capture_validation_result(self, creator_id: str, certificate: dict, schedule: dict) -> list[LearningSignal]:
        """Extract signals from validation: HIGH for violations, MEDIUM for quality>=85."""
        signals: list[LearningSignal] = []
        now = datetime.now().isoformat()
        status, quality = certificate.get("validation_status", ""), certificate.get("quality_score", 0)
        violations = certificate.get("violations_found", {})

        # HIGH: Hard gate violations
        for code, name in [("vault", "Vault Compliance"), ("avoid_tier", "AVOID Tier"), ("critical", "Critical")]:
            if violations.get(code, 0) > 0:
                signals.append(LearningSignal(
                    timestamp=now, title=f"{name} Violation", source="validation", confidence="HIGH",
                    pattern=f"{name} violation for {creator_id}", issue=f"Count: {violations[code]}",
                    correction=f"Fix {code} compliance in caption selection",
                    applies_to=f"creator:{creator_id}", metadata={"violation_code": f"{code.upper()}_VIOLATION"}))

        # MEDIUM: Quality >= 85 patterns
        if status == "APPROVED" and quality >= 85:
            items = schedule.get("items", [])
            send_types = {i.get("send_type_key") for i in items if i.get("send_type_key")}
            signals.append(LearningSignal(
                timestamp=now, title=f"High Quality Pattern ({quality})", source="validation", confidence="MEDIUM",
                pattern=f"Schedule approved with {quality} quality", insight=f"{len(send_types)} send types used",
                applies_to=f"creator:{creator_id}", metadata={"quality_score": quality}))
        return signals

    def capture_user_correction(self, original: dict, correction: dict, context: dict) -> LearningSignal:
        """Capture user correction as HIGH confidence learning."""
        creator_id = context.get("creator_id", "unknown")
        reason = context.get("reason", "User correction")[:50]
        return LearningSignal(
            timestamp=datetime.now().isoformat(), title=f"User Correction: {reason}",
            pattern=f"Original: {_summarize(original)}", source="user", confidence="HIGH",
            issue=reason, correction=f"Changed to: {_summarize(correction)}",
            applies_to=f"creator:{creator_id}" if creator_id != "unknown" else "all",
            metadata={"original": original, "correction": correction})

    def capture_performance_feedback(self, schedule_id: int, performance: dict) -> list[LearningSignal]:
        """Extract signals from performance: MEDIUM if sample>=10, else LOW."""
        signals: list[LearningSignal] = []
        now = datetime.now().isoformat()
        sample = performance.get("sample_size", 1)
        conf: CONFIDENCE = "MEDIUM" if sample >= 10 else "LOW"

        for metric, thresh in [("rps_delta_pct", 15), ("conversion_delta_pct", 10)]:
            delta = performance.get(metric, 0)
            if abs(delta) >= thresh:
                name = metric.replace("_delta_pct", "").upper()
                direction = "improvement" if delta > 0 else "decline"
                signals.append(LearningSignal(
                    timestamp=now, title=f"{name} {direction.title()}: {delta:+.1f}%",
                    pattern=f"Schedule {schedule_id} {name} change", source="performance", confidence=conf,
                    insight=f"{name} moved {delta:+.1f}% from baseline", sample_size=sample,
                    metadata={"schedule_id": schedule_id, metric: delta}))
        return signals

    def persist_signals(self, signals: list[LearningSignal]) -> int:
        """Persist signals to LEARNINGS.md. Returns count added."""
        if not signals:
            return 0
        content = self.learnings_path.read_text()
        added = 0

        for signal in signals:
            entry = _format_entry(signal)
            header = f"## {signal.confidence} Confidence Learnings"
            pattern = rf"({re.escape(header)}.*?\n>.*?\n)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                content = content[:match.end()] + f"\n{entry}\n" + content[match.end():]
                added += 1

        content = _update_stats(content, signals)
        content = _update_changelog(content, signals)
        self.learnings_path.write_text(content)
        return added


def _summarize(obj: dict, max_len: int = 80) -> str:
    """Brief summary of dict for logging."""
    s = ", ".join(f"{k}={v}" for k, v in list(obj.items())[:4])
    return s[:max_len] + "..." if len(s) > max_len else s


def _format_entry(s: LearningSignal) -> str:
    """Format signal as markdown entry."""
    lines = [f"### [{s.timestamp[:10]}] {s.title}", f"**Pattern**: {s.pattern}"]
    if s.issue: lines.append(f"**Issue**: {s.issue}")
    if s.correction: lines.append(f"**Correction**: {s.correction}")
    if s.insight: lines.append(f"**Insight**: {s.insight}")
    lines.append(f"**Source**: {s.source} | **Sample Size**: {s.sample_size}")
    lines.append(f"**Applies To**: {s.applies_to}")
    return "\n".join(lines)


def _update_stats(content: str, signals: list[LearningSignal]) -> str:
    """Update statistics YAML block."""
    by_conf = {"high": 0, "medium": 0, "low": 0}
    by_src = {"validation": 0, "user": 0, "performance": 0}
    for s in signals:
        by_conf[s.confidence.lower()] += 1
        by_src[s.source] += 1

    for conf, cnt in by_conf.items():
        if cnt > 0:
            content = re.sub(rf"(by_confidence:.*?{conf}: )(\d+)",
                             lambda m: f"{m.group(1)}{int(m.group(2)) + cnt}", content)
    for src, cnt in by_src.items():
        if cnt > 0:
            content = re.sub(rf"(by_source:.*?{src}: )(\d+)",
                             lambda m: f"{m.group(1)}{int(m.group(2)) + cnt}", content)
    content = re.sub(r"(last_7_days:.*?added: )(\d+)",
                     lambda m: f"{m.group(1)}{int(m.group(2)) + len(signals)}", content)
    return content


def _update_changelog(content: str, signals: list[LearningSignal]) -> str:
    """Add entries to changelog table."""
    marker = "| Date | Action | Learning | Confidence | Source |"
    if marker not in content:
        return content
    today = datetime.now().strftime("%Y-%m-%d")
    entries = [f"| {today} | ADDED | {s.title[:30]}{'...' if len(s.title) > 30 else ''} | {s.confidence} | {s.source} |"
               for s in signals]
    pattern = rf"({re.escape(marker)}\n\|[-|]+\|)"
    match = re.search(pattern, content)
    if match:
        content = content[:match.end()] + "\n" + "\n".join(entries) + content[match.end():]
    return content


__all__ = ["FeedbackCapture", "LearningSignal", "CONFIDENCE", "SOURCE"]
