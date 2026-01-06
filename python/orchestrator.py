"""EROS v1.0 Orchestrator - Minimal 3-phase pipeline coordinator (<250 lines).

Replaces v4.0's 2,468-line god object with clean 3-phase architecture:
  Phase 1: Preflight (deterministic) - Python via PreflightEngine
  Phase 2: Generator (Sonnet agent) - LLM schedule generation
  Phase 3: Validator (Opus agent) - LLM hard gate validation

Usage:
    result = await generate_schedule(mcp_client, task_tool, "alexia", "2026-01-06")
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, TypedDict

from .preflight import CreatorContext, PreflightEngine
from .feedback import FeedbackCapture, LearningSignal


# --- Type Definitions ---
class PhaseMetrics(TypedDict):
    phase: str
    duration_ms: float
    mcp_calls: int
    status: str
    error: str | None


@dataclass
class PipelineResult:
    """Final output of the 3-phase pipeline."""
    success: bool
    creator_id: str
    week_start: str
    schedule_id: int | None = None
    validation_status: str = ""
    quality_score: int = 0
    total_items: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class MCPClient(Protocol):
    async def get_creator_profile(self, creator_id: str) -> dict: ...
    async def get_volume_config(self, creator_id: str, week_start: str) -> dict: ...
    async def get_vault_availability(self, creator_id: str) -> dict: ...
    async def get_content_type_rankings(self, creator_id: str) -> dict: ...
    async def get_persona_profile(self, creator_id: str) -> dict: ...
    async def get_active_volume_triggers(self, creator_id: str) -> dict: ...
    async def get_performance_trends(self, creator_id: str, period: str) -> dict: ...
    async def save_schedule(self, creator_id: str, week_start: str,
                            items: list, validation_certificate: dict | None = None) -> dict: ...


class TaskTool(Protocol):
    async def invoke(self, subagent_type: str, prompt: str, model: str = "sonnet") -> dict: ...


# --- Orchestrator ---
class EROSOrchestrator:
    """Minimal 3-phase schedule generator coordinator."""

    def __init__(self, mcp_client: MCPClient, task_tool: TaskTool,
                 learnings_path: str = "LEARNINGS.md"):
        self.mcp = mcp_client
        self.task_tool = task_tool
        self.preflight = PreflightEngine(mcp_client)
        self.feedback = FeedbackCapture(learnings_path)

    async def run(self, creator_id: str, week_start: str) -> PipelineResult:
        """Execute 3-phase pipeline: Preflight -> Generator -> Validator -> Save."""
        start = datetime.now()
        metrics: dict[str, Any] = {}
        errors: list[str] = []
        context: CreatorContext | None = None
        schedule: dict = {}
        certificate: dict = {}

        # PHASE 1: Preflight
        t0 = datetime.now()
        try:
            context = await self._run_preflight(creator_id, week_start)
            metrics["preflight"] = {"phase": "preflight", "status": "success",
                "duration_ms": (datetime.now() - t0).total_seconds() * 1000,
                "mcp_calls": context.mcp_calls_made, "error": None}
        except Exception as e:
            metrics["preflight"] = {"phase": "preflight", "status": "failed",
                "duration_ms": (datetime.now() - t0).total_seconds() * 1000, "mcp_calls": 0, "error": str(e)}
            errors.append(f"Preflight: {e}")
            return PipelineResult(False, creator_id, week_start, errors=errors, metrics=metrics)

        # PHASE 2: Generator
        t0 = datetime.now()
        try:
            schedule = await self._invoke_generator(context)
            metrics["generator"] = {"phase": "generator", "status": "success",
                "duration_ms": (datetime.now() - t0).total_seconds() * 1000, "mcp_calls": 2, "error": None}
        except Exception as e:
            metrics["generator"] = {"phase": "generator", "status": "failed",
                "duration_ms": (datetime.now() - t0).total_seconds() * 1000, "mcp_calls": 0, "error": str(e)}
            errors.append(f"Generator: {e}")
            return PipelineResult(False, creator_id, week_start, errors=errors, metrics=metrics)

        # PHASE 3: Validator
        t0 = datetime.now()
        try:
            certificate = await self._invoke_validator(context, schedule)
            metrics["validator"] = {"phase": "validator", "status": "success",
                "duration_ms": (datetime.now() - t0).total_seconds() * 1000, "mcp_calls": 3, "error": None}
            # Capture validation feedback
            signals = self.feedback.capture_validation_result(creator_id, certificate, schedule)
            if signals:
                self.feedback.persist_signals(signals)
                metrics["learnings_captured"] = len(signals)
        except Exception as e:
            metrics["validator"] = {"phase": "validator", "status": "failed",
                "duration_ms": (datetime.now() - t0).total_seconds() * 1000, "mcp_calls": 0, "error": str(e)}
            errors.append(f"Validator: {e}")
            return PipelineResult(False, creator_id, week_start, errors=errors, metrics=metrics)

        status = certificate.get("validation_status", "REJECTED")
        score = certificate.get("quality_score", 0)
        items = schedule.get("items", []) + schedule.get("followups", [])

        # SAVE (if approved)
        schedule_id = None
        if status in ("APPROVED", "NEEDS_REVIEW"):
            t0 = datetime.now()
            try:
                result = await self._save_schedule(creator_id, week_start, schedule, certificate)
                schedule_id = result.get("schedule_id") or result.get("template_id")
                metrics["save"] = {"phase": "save", "status": "success",
                    "duration_ms": (datetime.now() - t0).total_seconds() * 1000, "mcp_calls": 1, "error": None}
            except Exception as e:
                metrics["save"] = {"phase": "save", "status": "failed",
                    "duration_ms": (datetime.now() - t0).total_seconds() * 1000, "mcp_calls": 0, "error": str(e)}
                errors.append(f"Save: {e}")

        metrics["total_duration_ms"] = (datetime.now() - start).total_seconds() * 1000
        return PipelineResult(success=status != "REJECTED", creator_id=creator_id, week_start=week_start,
            schedule_id=schedule_id, validation_status=status, quality_score=score,
            total_items=len(items), metrics=metrics, errors=errors)

    # --- Phase Methods ---
    async def _run_preflight(self, creator_id: str, week_start: str) -> CreatorContext:
        return await self.preflight.execute(creator_id, week_start)

    async def _invoke_generator(self, ctx: CreatorContext) -> dict:
        prompt = self._build_generator_prompt(ctx)
        return await self.task_tool.invoke("schedule-generator", prompt, model="sonnet")

    async def _invoke_validator(self, ctx: CreatorContext, schedule: dict) -> dict:
        prompt = self._build_validator_prompt(ctx, schedule)
        return await self.task_tool.invoke("schedule-validator", prompt, model="opus")

    async def _save_schedule(self, creator_id: str, week_start: str, schedule: dict, cert: dict) -> dict:
        items = schedule.get("items", []) + schedule.get("followups", [])
        return await self.mcp.save_schedule(creator_id, week_start, items, cert)

    # --- Prompt Builders ---
    def _build_generator_prompt(self, ctx: CreatorContext) -> str:
        vol = ctx.volume_config
        return f"""You are schedule-generator. Build a weekly schedule for {ctx.creator_id}.

OUTPUT: Return JSON with "items" and "followups" arrays.

CONTEXT:
- page_type: {ctx.page_type}
- vault_types (ONLY use): {json.dumps(list(ctx.vault_types))}
- avoid_types (NEVER use): {json.dumps(list(ctx.avoid_types))}
- volume: tier={vol.get('tier')}, rev={vol.get('revenue_per_day')}, eng={vol.get('engagement_per_day')}, ret={vol.get('retention_per_day')}
- pricing: base=${ctx.pricing_config.get('base_price', 15)}, floor=$5, ceiling=$50

CONSTRAINTS: PPV max 4/day | Followup max 5/day | Min gap 45min | Dead zone 3-7AM | Jitter ±7-8min (avoid :00/:15/:30/:45)

ITEM: {{"send_type_key": "ppv_unlock", "caption_id": 123, "content_type": "lingerie", "scheduled_date": "2026-01-06", "scheduled_time": "19:23", "price": 15.00, "flyer_required": 1, "channel_key": "mass_message"}}
FOLLOWUP: {{"parent_item_index": 0, "send_type_key": "ppv_followup", "scheduled_time": "19:51", "delay_minutes": 28}}

MCP tools: get_batch_captions_by_content_types, get_send_type_captions"""

    def _build_validator_prompt(self, ctx: CreatorContext, schedule: dict) -> str:
        items = schedule.get("items", []) + schedule.get("followups", [])
        return f"""You are schedule-validator. Verify hard gates and generate ValidationCertificate.

INDEPENDENCE: Re-fetch vault/avoid via MCP (get_vault_availability, get_content_type_rankings).

CREATOR: {ctx.creator_id} (page_type: {ctx.page_type})
SCHEDULE: {len(items)} items

HARD GATES (REJECT on violation):
1. VAULT: All content_type must be in vault_types
2. AVOID: No content_type in AVOID tier
3. PAGE_TYPE: Retention types (renew_*, expired_winback) only for PAID
4. DIVERSITY: >= 10 unique send_types, >= 4 revenue, >= 4 engagement, >= 2 retention (PAID)
5. FLYER: ppv_unlock, bundle, flash_bundle need flyer_required=1

SCHEDULE DATA:
{json.dumps(items[:20], indent=1)}{"..." if len(items) > 20 else ""}

OUTPUT ValidationCertificate:
{{"certificate_version": "3.0", "creator_id": "{ctx.creator_id}", "validation_timestamp": "ISO8601",
"schedule_hash": "sha256:...", "items_validated": {len(items)}, "quality_score": 0-100,
"validation_status": "APPROVED|NEEDS_REVIEW|REJECTED",
"checks_performed": {{"vault_compliance": true, "avoid_tier_exclusion": true, "send_type_diversity": true, "timing_validation": true}},
"violations_found": {{"vault": 0, "avoid_tier": 0, "critical": 0}}}}

THRESHOLDS: 85-100=APPROVED, 75-84=APPROVED(notes), 60-74=NEEDS_REVIEW, <60=REJECTED"""


# --- Convenience Function ---
async def generate_schedule(mcp: MCPClient, task: TaskTool, creator_id: str, week_start: str,
                            learnings_path: str = "LEARNINGS.md") -> PipelineResult:
    """Generate a schedule for a creator."""
    return await EROSOrchestrator(mcp, task, learnings_path).run(creator_id, week_start)


__all__ = ["EROSOrchestrator", "PipelineResult", "PhaseMetrics", "MCPClient", "TaskTool", "generate_schedule"]
