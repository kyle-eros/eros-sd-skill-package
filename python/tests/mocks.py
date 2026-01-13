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
    # NEW: Persona configuration for test scenarios
    persona_tone: str = "playful"           # NEW
    persona_secondary: str | None = "bratty" # NEW
    emoji_frequency: str = "moderate"        # NEW
    slang_level: str = "light"              # NEW


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

    async def get_creator_profile(self, creator_id: str, include_analytics: bool = True,
                                   include_volume: bool = True, include_content_rankings: bool = True,
                                   include_vault: bool = True, include_persona: bool = True) -> dict:
        """Mock bundled creator profile."""
        self._log("get_creator_profile")
        c = self.config

        response = {
            "found": True,
            "creator": {
                "creator_id": creator_id, "page_type": c.page_type, "is_active": c.is_active,
                "current_fan_count": c.fan_count, "mm_revenue_monthly": c.mm_revenue_monthly,
                "content_category": c.content_category, "base_price": 15.00,
                "has_active_experiments": False,
            },
            "metadata": {"mcp_calls_saved": 5}
        }

        if include_analytics:
            response["analytics_summary"] = {
                "mm_revenue_30d": c.mm_revenue_monthly or 0,
                "mm_revenue_confidence": "medium"
            }

        if include_volume:
            response["volume_assignment"] = {
                "volume_level": "STANDARD",
                "revenue_per_day": [4, 6]
            }

        if include_content_rankings:
            rankings = []
            avoid_types = []
            top_types = []

            for i, t in enumerate(c.vault_types):
                tier = "AVOID" if t in c.avoid_types else ("TOP" if i < 2 else "MID")
                rankings.append({
                    "type_name": t,
                    "performance_tier": tier,
                    "rps": 180.0 - i * 20,
                    "conversion_rate": 5.5 - i * 0.5,
                    "sends_last_30d": 10 + i,
                    "total_earnings": 1000.0 - i * 100,
                    "confidence_score": 0.85
                })
                if tier == "AVOID":
                    avoid_types.append(t)
                elif tier == "TOP":
                    top_types.append(t)

            # Compute avoid_types_hash
            avoid_input = "|".join(sorted(avoid_types))
            avoid_types_hash = f"sha256:{hashlib.sha256(avoid_input.encode()).hexdigest()[:16]}"

            response["content_type_rankings"] = {
                "rankings": rankings,
                "avoid_types": avoid_types,
                "top_types": top_types,
                "total_types": len(rankings),
                "avoid_types_hash": avoid_types_hash,
                "analysis_date": "2026-01-07",
                "data_age_days": 1,
                "is_stale": False
            }

            # Backward compatibility (deprecated)
            response["top_content_types"] = rankings
            response["avoid_types"] = avoid_types
            response["top_types"] = top_types

        if include_vault:
            allowed_result = await self.get_allowed_content_types(creator_id)
            response["allowed_content_types"] = {
                "allowed_types": allowed_result["allowed_types"],
                "allowed_type_names": allowed_result["allowed_type_names"],
                "type_count": allowed_result["type_count"],
                "vault_hash": allowed_result["metadata"]["vault_hash"]
            }

        # Add persona section (NEW)
        if include_persona:
            response["persona"] = {
                "persona_id": 1,
                "creator_id": creator_id,
                "primary_tone": c.persona_tone,
                "secondary_tone": c.persona_secondary,
                "emoji_frequency": c.emoji_frequency,
                "slang_level": c.slang_level,
                "avg_sentiment": 0.75,
                "avg_caption_length": 85,
                "favorite_emojis": None,
                "_default": False
            }

        return response

    async def get_volume_config(self, creator_id: str, week_start: str) -> dict:
        self._log("get_volume_config")
        return {
            "tier": "STANDARD", "fused_saturation": self.config.saturation,
            "fused_opportunity": 100 - self.config.saturation, "previous_tier": None,
        }

    async def get_allowed_content_types(self, creator_id: str, include_category: bool = True) -> dict:
        """Mock allowed content types response."""
        self._log("get_allowed_content_types")

        allowed_types = []
        for vt in self.config.vault_types:
            type_data = {"type_name": vt}
            if include_category:
                type_data["type_category"] = "explicit" if vt in ["b/g", "anal", "blowjob"] else "softcore"
                type_data["is_explicit"] = vt not in ["lifestyle", "fitness", "teasing"]
            allowed_types.append(type_data)

        allowed_type_names = [t["type_name"] for t in allowed_types]

        hash_input = "|".join(sorted(allowed_type_names))
        vault_hash = f"sha256:{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"

        return {
            "creator_id": creator_id,
            "allowed_types": allowed_types,
            "allowed_type_names": allowed_type_names,
            "type_count": len(allowed_type_names),
            "metadata": {
                "fetched_at": "2026-01-08T21:00:00",
                "vault_hash": vault_hash,
                "creator_resolved": creator_id
            }
        }

    async def get_content_type_rankings(self, creator_id: str, include_metrics: bool = True) -> dict:
        """Mock content type rankings response with new structure."""
        self._log("get_content_type_rankings")

        rankings = []
        avoid_types = []
        top_types = []

        for i, t in enumerate(self.config.vault_types):
            tier = "AVOID" if t in self.config.avoid_types else ("TOP" if i < 2 else "MID")

            entry = {
                "type_name": t,
                "performance_tier": tier,
            }

            if include_metrics:
                entry.update({
                    "rps": 180.0 - i * 20,
                    "conversion_rate": 5.5 - i * 0.5,
                    "sends_last_30d": 10 + i,
                    "total_earnings": 1000.0 - i * 100,
                    "confidence_score": 0.85
                })

            rankings.append(entry)

            if tier == "AVOID":
                avoid_types.append(t)
            elif tier == "TOP":
                top_types.append(t)

        # Compute hashes
        rankings_input = "|".join(sorted([r["type_name"] for r in rankings]))
        rankings_hash = f"sha256:{hashlib.sha256(rankings_input.encode()).hexdigest()[:16]}"

        avoid_input = "|".join(sorted(avoid_types))
        avoid_types_hash = f"sha256:{hashlib.sha256(avoid_input.encode()).hexdigest()[:16]}"

        return {
            "creator_id": creator_id,
            "rankings": rankings,
            "avoid_types": avoid_types,
            "top_types": top_types,
            "total_types": len(rankings),
            "metadata": {
                "fetched_at": "2026-01-08T21:00:00",
                "rankings_hash": rankings_hash,
                "avoid_types_hash": avoid_types_hash,
                "creator_resolved": creator_id,
                "analysis_date": "2026-01-07",
                "data_age_days": 1,
                "is_stale": False
            }
        }

    async def get_persona_profile(self, creator_id: str) -> dict:
        """Return persona matching DB schema structure."""
        self._log("get_persona_profile")
        return {
            "persona_id": 1,
            "creator_id": creator_id,
            "primary_tone": self.config.persona_tone,
            "secondary_tone": self.config.persona_secondary,
            "emoji_frequency": self.config.emoji_frequency,
            "slang_level": self.config.slang_level,
            "avg_sentiment": 0.75,
            "avg_caption_length": 85,
            "favorite_emojis": None,
            "last_analyzed": "2025-12-01T00:00:00",
            "validation_status": "unvalidated",
            "_default": False
        }

    async def get_active_volume_triggers(self, creator_id: str) -> dict:
        self._log("get_active_volume_triggers")
        return {"triggers": [], "count": 0}

    async def get_performance_trends(self, creator_id: str, period: str = "14d") -> dict:
        """Mock get_performance_trends matching new contract."""
        self._log("get_performance_trends")

        # Use config values for test control
        saturation = self.config.saturation
        decline_weeks = self.config.decline_weeks

        # Calculate health status (matches volume_utils.calc_health_status logic)
        if decline_weeks >= 4:
            health_status = "DEATH_SPIRAL"
            volume_adjustment = -1
        elif decline_weeks >= 2:
            health_status = "WARNING"
            volume_adjustment = 0
        else:
            health_status = "HEALTHY"
            volume_adjustment = 1 if saturation < 30 else 0

        return {
            # Original fields (backwards compat)
            "creator_id": creator_id,
            "creator_id_resolved": creator_id,
            "period": period,
            "health_status": health_status,
            "avg_rps": 15.50,
            "avg_conversion": 4.2,
            "avg_open_rate": 45.5,
            "total_earnings": 1550.00,
            "total_sends": 100,
            "saturation_score": saturation,
            "opportunity_score": 100 - saturation,
            "date_range": {
                "start": "2026-01-01T00:00:00Z",
                "end": "2026-01-14T23:59:59Z"
            },

            # New fields from refactor
            "consecutive_decline_weeks": decline_weeks,
            "volume_adjustment": volume_adjustment,
            "revenue_trend_pct": 8.5,
            "engagement_trend_pct": 12.0,
            "trend_period": "wow",
            "data_confidence": "high",
            "insufficient_data": False,

            # Metadata block
            "metadata": {
                "fetched_at": datetime.now().isoformat() + "Z",
                "trends_hash": "sha256:mock_hash_1234",
                "hash_inputs": [f"creator:{creator_id}", f"period:{period}"],
                "query_ms": 25.5,
                "data_age_days": 1,
                "is_stale": False,
                "has_period_data": True,
                "sends_in_period": 100,
                "period_days": 14,
                "expected_sends": 28,
                "staleness_threshold_days": 14
            }
        }

    async def save_schedule(self, creator_id: str, week_start: str,
                            items: list, validation_certificate: dict | None = None) -> dict:
        """Mock save_schedule v2.0.0 response structure."""
        self._log("save_schedule")

        # Calculate week_end (6 days after week_start)
        from datetime import timedelta
        week_start_dt = datetime.strptime(week_start, "%Y-%m-%d")
        week_end_dt = week_start_dt + timedelta(days=6)
        week_end = week_end_dt.strftime("%Y-%m-%d")

        # Determine status based on certificate
        status = "approved" if validation_certificate else "draft"
        has_certificate = validation_certificate is not None

        # Generate schedule hash
        hash_input = f"{creator_id}|{week_start}|{len(items)}"
        schedule_hash = f"sha256:{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"

        response = {
            "success": True,
            "schedule_id": 99999,
            "template_id": 99999,
            "items_saved": len(items) if items else 0,
            "creator_id": creator_id,
            "creator_id_resolved": f"{creator_id}_001",
            "week_start": week_start,
            "week_end": week_end,
            "status": status,
            "has_certificate": has_certificate,
            "metadata": {
                "saved_at": datetime.now().isoformat() + "Z",
                "query_ms": 10.0,
                "schedule_hash": schedule_hash
            },
            "replaced": False,
            "warnings": []
        }

        # Add certificate_summary if certificate provided
        if validation_certificate:
            response["certificate_summary"] = {
                "validation_status": validation_certificate.get("validation_status", "APPROVED"),
                "quality_score": validation_certificate.get("quality_score", 85),
                "items_validated": validation_certificate.get("items_validated", len(items)),
                "is_fresh": True,
                "age_seconds": 30
            }

        return response


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
