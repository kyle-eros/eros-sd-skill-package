"""EROS v1.0 Pipeline Router with Feature Flags (<80 lines).

Routes schedule generation requests to v4 or v5 pipeline based on:
1. Global kill switch (EROS_V5_ENABLED)
2. Per-creator allowlist (EROS_V5_CREATORS)
3. Percentage rollout (EROS_V5_PERCENTAGE)
4. Shadow mode (run both, compare results)
5. Automatic fallback on v5 failure
"""
from __future__ import annotations
import hashlib, os
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .orchestrator import MCPClient, TaskTool, PipelineResult

class Pipeline(Enum):
    V4 = "v4"; V5 = "v5"; SHADOW = "shadow"

@dataclass(frozen=True, slots=True)
class RoutingDecision:
    pipeline: Pipeline
    reason: str
    creator_id: str
    shadow_enabled: bool = False

class FeatureFlags:
    """Feature flag resolution from env vars (DB override possible)."""
    def __init__(self, db_flags: dict | None = None):
        self._db = db_flags or {}

    def _get(self, key: str, default: str, cast=str):
        val = self._db.get(key) or os.environ.get(key, default)
        if cast == bool: return str(val).lower() in ("true", "1", "yes")
        if cast == int: return int(val) if val else 0
        if cast == list: return [x.strip() for x in str(val).split(",") if x.strip()]
        return val

    @property
    def v5_enabled(self) -> bool: return self._get("EROS_V5_ENABLED", "false", bool)
    @property
    def v5_creators(self) -> list[str]: return self._get("EROS_V5_CREATORS", "", list)
    @property
    def v5_percentage(self) -> int: return self._get("EROS_V5_PERCENTAGE", "0", int)
    @property
    def shadow_mode(self) -> bool: return self._get("EROS_V5_SHADOW_MODE", "false", bool)
    @property
    def auto_fallback(self) -> bool: return self._get("EROS_V5_AUTO_FALLBACK", "true", bool)

class PipelineRouter:
    """Routes requests to v4 or v5 based on feature flags."""
    def __init__(self, flags: FeatureFlags | None = None):
        self.flags = flags or FeatureFlags()

    def decide(self, creator_id: str) -> RoutingDecision:
        f = self.flags
        if not f.v5_enabled:
            return RoutingDecision(Pipeline.V4, "v5_disabled", creator_id)
        if f.shadow_mode:
            return RoutingDecision(Pipeline.SHADOW, "shadow_mode", creator_id, shadow_enabled=True)
        if creator_id in f.v5_creators:
            return RoutingDecision(Pipeline.V5, "allowlisted", creator_id)
        if f.v5_percentage > 0:
            h = int(hashlib.md5(creator_id.encode()).hexdigest()[:8], 16) % 100
            if h < f.v5_percentage:
                return RoutingDecision(Pipeline.V5, f"percentage_{f.v5_percentage}", creator_id)
        return RoutingDecision(Pipeline.V4, "default", creator_id)

    async def route(self, mcp: "MCPClient", task: "TaskTool", creator_id: str, week_start: str,
                    v4_runner=None, v5_runner=None) -> "PipelineResult":
        """Execute pipeline based on routing decision with optional fallback."""
        from .orchestrator import generate_schedule as v5_generate
        decision = self.decide(creator_id)

        if decision.pipeline == Pipeline.V5:
            try:
                return await v5_generate(mcp, task, creator_id, week_start)
            except Exception as e:
                if self.flags.auto_fallback and v4_runner:
                    return await v4_runner(creator_id, week_start)
                raise

        if decision.pipeline == Pipeline.SHADOW:
            from .comparator import run_shadow_comparison
            return await run_shadow_comparison(mcp, task, creator_id, week_start, v4_runner)

        # V4 default
        if v4_runner:
            return await v4_runner(creator_id, week_start)
        raise RuntimeError("V4 runner required when v5 disabled")

__all__ = ["PipelineRouter", "FeatureFlags", "RoutingDecision", "Pipeline"]
