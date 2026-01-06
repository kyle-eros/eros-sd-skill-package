"""EROS v1.0 Test Infrastructure - Mock clients and test data factories (<150 lines)."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CreatorConfig:
    """Configuration for generating test creator data."""
    creator_id: str = "alexia"
    page_type: str = "paid"
    is_active: bool = True
    fan_count: int = 5000
    mm_revenue_monthly: float | None = 1500.0  # STANDARD tier
    vault_types: list[str] = field(default_factory=lambda: ["lingerie", "b/g", "solo", "shower", "gym"])
    avoid_types: list[str] = field(default_factory=list)
    saturation: int = 45
    decline_weeks: int = 0
    content_category: str = "softcore"


class TestDataFactory:
    """Generate test data for various scenarios."""

    STANDARD = CreatorConfig()
    HIGH_VALUE = CreatorConfig(
        creator_id="grace_bennett", mm_revenue_monthly=5000.0, fan_count=15000,
        vault_types=["lingerie", "b/g", "solo", "shower", "gym", "outdoor", "cosplay"],
    )
    FREE_PAGE = CreatorConfig(
        creator_id="luna_free", page_type="free", mm_revenue_monthly=300.0,
        fan_count=2000, content_category="lifestyle"
    )
    EMPTY_VAULT = CreatorConfig(creator_id="empty_vault", vault_types=[])
    ALL_AVOID = CreatorConfig(
        creator_id="all_avoid",
        vault_types=["lingerie", "b/g"],
        avoid_types=["lingerie", "b/g"],
    )
    DEATH_SPIRAL = CreatorConfig(
        creator_id="struggling", decline_weeks=5, saturation=80, mm_revenue_monthly=100.0
    )

    @classmethod
    def get_config(cls, name: str) -> CreatorConfig:
        return getattr(cls, name.upper(), cls.STANDARD)


class MockMCPClient:
    """Mock MCP client returning realistic test data."""

    def __init__(self, config: CreatorConfig | None = None):
        self.config = config or TestDataFactory.STANDARD
        self.call_log: list[str] = []

    def _log(self, method: str): self.call_log.append(method)

    async def get_creator_profile(self, creator_id: str) -> dict:
        self._log("get_creator_profile")
        c = self.config
        return {
            "creator_id": creator_id, "page_type": c.page_type, "is_active": c.is_active,
            "current_fan_count": c.fan_count, "mm_revenue_monthly": c.mm_revenue_monthly,
            "content_category": c.content_category, "base_price": 15.00,
            "has_active_experiments": False,
        }

    async def get_volume_config(self, creator_id: str, week_start: str) -> dict:
        self._log("get_volume_config")
        return {
            "tier": "STANDARD", "fused_saturation": self.config.saturation,
            "fused_opportunity": 100 - self.config.saturation, "previous_tier": None,
        }

    async def get_vault_availability(self, creator_id: str) -> dict:
        self._log("get_vault_availability")
        return {"available_types": [{"type_name": t} for t in self.config.vault_types]}

    async def get_content_type_rankings(self, creator_id: str) -> dict:
        self._log("get_content_type_rankings")
        types = []
        for i, t in enumerate(self.config.vault_types):
            tier = "AVOID" if t in self.config.avoid_types else ("TOP" if i < 2 else "MID")
            types.append({
                "type_name": t, "performance_tier": tier, "rps": 180 - i * 20,
                "conversion_rate": 5.5 - i * 0.5, "sends_last_30d": 10 + i,
            })
        return {"content_types": types}

    async def get_persona_profile(self, creator_id: str) -> dict:
        self._log("get_persona_profile")
        return {"primary_tone": "GFE", "secondary_tone": "playful", "archetype": "girl_next_door"}

    async def get_active_volume_triggers(self, creator_id: str) -> dict:
        self._log("get_active_volume_triggers")
        return []

    async def get_performance_trends(self, creator_id: str, period: str) -> dict:
        self._log("get_performance_trends")
        return {
            "saturation_score": self.config.saturation,
            "opportunity_score": 100 - self.config.saturation,
            "consecutive_decline_weeks": self.config.decline_weeks,
        }

    async def save_schedule(self, creator_id: str, week_start: str,
                            items: list, validation_certificate: dict | None = None) -> dict:
        self._log("save_schedule")
        return {"schedule_id": 12345, "template_id": 12345, "items_saved": len(items)}


class MockTaskTool:
    """Mock Task tool simulating agent responses."""

    def __init__(self, vault_types: list[str] | None = None, avoid_types: list[str] | None = None,
                 quality_score: int = 90, force_reject: bool = False):
        self.vault_types = vault_types or ["lingerie", "b/g", "solo", "shower", "gym"]
        self.avoid_types = avoid_types or []
        self.quality_score = quality_score
        self.force_reject = force_reject
        self.call_log: list[tuple[str, str]] = []

    async def invoke(self, subagent_type: str, prompt: str, model: str = "sonnet") -> dict:
        self.call_log.append((subagent_type, model))
        if subagent_type == "schedule-generator":
            return self._gen_schedule()
        elif subagent_type == "schedule-validator":
            return self._gen_certificate()
        return {"error": f"Unknown agent: {subagent_type}"}

    def _gen_schedule(self) -> dict:
        items, types = [], ["ppv_unlock", "bump_normal", "link_drop", "dm_farm", "renew_on_post"]
        for i, st in enumerate(types * 3):
            ct = self.vault_types[i % len(self.vault_types)] if self.vault_types else "unknown"
            items.append({
                "send_type_key": st, "caption_id": 1000 + i, "content_type": ct,
                "scheduled_date": "2026-01-06", "scheduled_time": f"{10 + i}:23",
                "price": 15.00 if "ppv" in st else None,
                "flyer_required": 1 if st in ("ppv_unlock", "bundle") else 0,
                "channel_key": "mass_message",
            })
        followups = [{"parent_item_index": 0, "send_type_key": "ppv_followup",
                      "scheduled_time": "10:51", "delay_minutes": 28}]
        return {"items": items, "followups": followups}

    def _gen_certificate(self) -> dict:
        status = "REJECTED" if self.force_reject else (
            "APPROVED" if self.quality_score >= 75 else "NEEDS_REVIEW" if self.quality_score >= 60 else "REJECTED")
        ts = datetime.now().isoformat()
        h = hashlib.sha256(ts.encode()).hexdigest()[:16]
        return {
            "certificate_version": "3.0", "creator_id": "test", "validation_timestamp": ts,
            "schedule_hash": f"sha256:{h}", "avoid_types_hash": f"sha256:{h[:8]}",
            "vault_types_hash": f"sha256:{h[8:16]}", "items_validated": 16,
            "quality_score": self.quality_score, "validation_status": status,
            "checks_performed": {"vault_compliance": True, "avoid_tier_exclusion": True,
                                 "send_type_diversity": True, "timing_validation": True},
            "violations_found": {"vault": 0, "avoid_tier": 0, "critical": 0},
            "upstream_proof_verified": True, "certificate_signature": f"vg-{h[:8]}-{ts[:10]}",
        }


__all__ = ["CreatorConfig", "TestDataFactory", "MockMCPClient", "MockTaskTool"]
