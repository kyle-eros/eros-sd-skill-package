"""EROS Preflight Engine v1.0 - Deterministic context generation."""
from __future__ import annotations
import asyncio, hashlib, math, random
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

# --- Constants (from DOMAIN_KNOWLEDGE.md) ---
TIERS = {
    "MINIMAL": (0, 149, (1,2), (1,2), (1,1)),
    "LITE": (150, 799, (2,4), (2,4), (1,2)),
    "STANDARD": (800, 2999, (4,6), (4,6), (2,3)),
    "HIGH_VALUE": (3000, 7999, (6,9), (5,8), (2,4)),
    "PREMIUM": (8000, float("inf"), (8,12), (6,10), (3,5)),
}  # (min, max, rev, eng, ret)
TIER_ORDER = list(TIERS.keys())
PRIME_HOURS = {
    "monday": [(12,14),(19,22),(10,11)], "tuesday": [(12,14),(20,23),(10,11)],
    "wednesday": [(12,14),(20,23),(18,19)], "thursday": [(12,14),(20,23),(18,19)],
    "friday": [(12,14),(21,24),(17,19)], "saturday": [(11,14),(22,25),(16,18)],
    "sunday": [(11,14),(20,23),(16,18)],
}
HOLIDAYS = {(1,1),(2,14),(7,4),(10,31),(12,25)}
BUMP_MULT = {"lifestyle": 1.0, "softcore": 1.5, "amateur": 2.0, "explicit": 2.67}

@dataclass(frozen=True, slots=True)
class CreatorContext:
    """Complete context for schedule generation."""
    creator_id: str
    page_type: str
    vault_types: tuple[str, ...]
    avoid_types: tuple[str, ...]
    top_content_types: tuple[dict, ...]
    volume_config: dict
    persona: dict
    active_triggers: tuple[dict, ...]
    pricing_config: dict
    timing_slots: dict
    health: dict
    generated_at: str = ""
    preflight_duration_ms: float = 0
    mcp_calls_made: int = 0

class MCPClient(Protocol):
    """Protocol for MCP client - matches eros-db server tools (15 total)."""

    # Creator tools (5)
    async def get_creator_profile(
        self,
        creator_id: str,
        include_analytics: bool = True,
        include_volume: bool = True,
        include_content_rankings: bool = True,
        include_vault: bool = True,
        include_persona: bool = True,  # v1.5.0: Persona now bundled
    ) -> dict: ...
    async def get_active_creators(self, limit: int = 100, tier: str = None) -> dict: ...
    async def get_allowed_content_types(self, creator_id: str, include_category: bool = True) -> dict: ...
    async def get_content_type_rankings(self, creator_id: str) -> dict: ...
    async def get_persona_profile(self, creator_id: str) -> dict: ...

    # Schedule tools (5)
    async def get_volume_config(self, creator_id: str, week_start: str) -> dict: ...
    async def get_active_volume_triggers(self, creator_id: str) -> dict: ...
    async def get_performance_trends(self, creator_id: str, period: str = "14d") -> dict: ...
    async def save_schedule(self, creator_id: str, week_start: str, items: list, validation_certificate: dict = None) -> dict: ...
    async def save_volume_triggers(self, creator_id: str, triggers: list) -> dict: ...

    # Caption tools (3)
    async def get_batch_captions_by_content_types(self, creator_id: str, content_types: list, limit_per_type: int = 5) -> dict: ...
    async def get_send_type_captions(self, creator_id: str, send_type: str, limit: int = 10) -> dict: ...
    async def validate_caption_structure(self, caption_text: str, send_type: str) -> dict: ...

    # Config tools (2)
    async def get_send_types(self, page_type: str = None) -> dict: ...
    async def get_send_types_constraints(self, page_type: str = None) -> dict:
        """Lightweight send types for schedule generation (9 fields, ~2k tokens)."""
        ...

class PreflightEngine:
    """Single-pass preflight generating CreatorContext. All logic deterministic."""
    def __init__(self, mcp: MCPClient): self.mcp = mcp

    async def execute(self, creator_id: str, week_start: str) -> CreatorContext:
        start = datetime.now()
        raw = await self._fetch_all(creator_id, week_start)
        profile = raw["creator_profile"]
        if not profile.get("is_active"): raise ValueError(f"Creator {creator_id} not active")

        health = self._calc_health(raw)
        triggers = list(raw.get("active_triggers", [])) + self._detect_triggers(raw)
        volume = self._calc_volume(raw, health, triggers, week_start)
        timing = self._gen_timing(volume, week_start)

        return CreatorContext(
            creator_id=creator_id, page_type=profile.get("page_type", "paid"),
            vault_types=tuple(self._vault_types(raw)), avoid_types=tuple(self._avoid_types(raw)),
            top_content_types=tuple(self._all_content_rankings(raw)), volume_config=volume,
            persona=raw.get("persona", {}),  # v1.5.0: Now from bundled response
            active_triggers=tuple(triggers),
            pricing_config=self._pricing(raw), timing_slots=timing, health=health,
            generated_at=datetime.now().isoformat(),
            preflight_duration_ms=(datetime.now()-start).total_seconds()*1000,
            mcp_calls_made=3)  # v1.5.0: Reduced from 4 via persona bundling

    async def _fetch_all(self, cid: str, ws: str) -> dict:
        """Fetch all creator data with optimized bundled call.

        Uses bundled get_creator_profile for efficiency (saves 5 MCP calls):
        - analytics, volume, content_rankings, vault, and persona all bundled.

        CRITICAL FIX (v1.3.0): Vault data now comes directly from vault_matrix
        instead of being derived from top_content_types. This ensures we catch
        vault content that may not have historical performance data.

        CRITICAL FIX (v1.4.0): Now uses pre-computed avoid_types and top_types
        from bundled response instead of re-computing them.

        OPTIMIZATION (v1.5.0): Persona now bundled into get_creator_profile,
        reducing total MCP calls from 4 to 3.
        """

        # Use bundled get_creator_profile for efficiency (saves 5 MCP calls)
        profile_bundle = await self.mcp.get_creator_profile(
            cid,
            include_analytics=True,
            include_volume=True,
            include_content_rankings=True,
            include_vault=True,
            include_persona=True,  # v1.5.0: Persona now bundled
        )

        # Parallel fetch remaining data not in bundle (only 2 calls now)
        remaining_results = await asyncio.gather(
            self.mcp.get_active_volume_triggers(cid),
            self.mcp.get_performance_trends(cid, "14d"),
            return_exceptions=True
        )

        # Extract vault data (HARD GATE - from vault_matrix)
        vault_data = profile_bundle.get("allowed_content_types", {})

        # Extract rankings data (HARD GATE - from top_content_types with analysis_date filter)
        # NEW: Use new structure if available, fall back to legacy
        rankings_data = profile_bundle.get("content_type_rankings", {})
        if not rankings_data:
            # Legacy fallback
            rankings_data = {
                "rankings": profile_bundle.get("top_content_types", []),
                "avoid_types": profile_bundle.get("avoid_types", []),
                "top_types": profile_bundle.get("top_types", [])
            }

        return {
            "creator_profile": profile_bundle.get("creator", {}),
            "volume_config": profile_bundle.get("volume_assignment", {}),
            "allowed_content_types": vault_data,
            "content_type_rankings": rankings_data,  # Now includes pre-computed lists
            "analytics_summary": profile_bundle.get("analytics_summary", {}),
            "persona": profile_bundle.get("persona", {}),  # v1.5.0: Now from bundle
            "active_triggers": remaining_results[0] if not isinstance(remaining_results[0], Exception) else [],
            "performance_trends": remaining_results[1] if not isinstance(remaining_results[1], Exception) else {},
            "_bundle_metadata": profile_bundle.get("metadata", {})
        }

    def _calc_health(self, raw: dict) -> dict:
        """Death spiral detection from DOMAIN_KNOWLEDGE.md Section 7."""
        vol = raw.get("volume_config", {}); pt = raw.get("performance_trends", {})
        sat = vol.get("fused_saturation", pt.get("saturation_score", 50))
        opp = vol.get("fused_opportunity", pt.get("opportunity_score", 50))
        decline = pt.get("consecutive_decline_weeks", 0)

        if decline >= 4: status, adj = "DEATH_SPIRAL", -1
        elif decline >= 2: status, adj = "WARNING", 0
        else: status, adj = "HEALTHY", (1 if sat < 30 else 0)

        return {"status": status, "score": round(max(0, min(100, 100-decline*15-sat*0.3)), 1),
                "consecutive_decline_weeks": decline, "saturation_score": sat,
                "opportunity_score": opp, "volume_adjustment": adj}

    def _detect_triggers(self, raw: dict) -> list[dict]:
        """5 trigger types from DOMAIN_KNOWLEDGE.md Section 8."""
        triggers = []; exp = (datetime.now().date() + timedelta(days=7)).isoformat()
        for ct in raw.get("content_type_rankings", {}).get("content_types", []):
            name = ct.get("type_name", ct.get("content_type", ""))
            rps = ct.get("rps", ct.get("revenue_per_send", 0))
            conv = ct.get("conversion_rate", 0)
            uses = ct.get("sends_last_30d", ct.get("send_count", 10))
            wow = ct.get("wow_rps_change", 0)
            orc = ct.get("open_rate_7d_change", 0)
            dec = ct.get("declining_rps_days", 0)
            n = ct.get("sends_analyzed", uses)
            conf = "high" if n > 10 else "moderate" if n >= 5 else "low"

            # HIGH_PERFORMER: RPS > $200 AND conversion > 6% → +20%
            if rps > 200 and conv > 6:
                triggers.append({"content_type": name, "trigger_type": "HIGH_PERFORMER",
                    "adjustment_multiplier": 1.20, "confidence": conf,
                    "reason": f"RPS ${rps:.0f}, conv {conv:.1f}%", "expires_at": exp})
            # EMERGING_WINNER: RPS > $150 AND <3 uses/30d → +30%
            elif rps > 150 and uses < 3:
                triggers.append({"content_type": name, "trigger_type": "EMERGING_WINNER",
                    "adjustment_multiplier": 1.30, "confidence": conf,
                    "reason": f"RPS ${rps:.0f}, {uses} uses/30d", "expires_at": exp})
            # TRENDING_UP: WoW RPS +15% → +10%
            elif wow >= 15:
                triggers.append({"content_type": name, "trigger_type": "TRENDING_UP",
                    "adjustment_multiplier": 1.10, "confidence": conf,
                    "reason": f"WoW RPS +{wow:.0f}%", "expires_at": exp})
            # SATURATING: Declining RPS 3+ days → -15%
            elif dec >= 3:
                triggers.append({"content_type": name, "trigger_type": "SATURATING",
                    "adjustment_multiplier": 0.85, "confidence": "moderate",
                    "reason": f"Declining {dec} days", "expires_at": exp})
            # AUDIENCE_FATIGUE: Open rate -10%/7d → -25%
            elif orc <= -10:
                triggers.append({"content_type": name, "trigger_type": "AUDIENCE_FATIGUE",
                    "adjustment_multiplier": 0.75, "confidence": "moderate",
                    "reason": f"Open rate {orc:.0f}%/7d", "expires_at": exp})
        return triggers

    def _calc_volume(self, raw: dict, health: dict, triggers: list, week_start: str) -> dict:
        """Volume with tier smoothing, hysteresis, calendar boosts."""
        p = raw.get("creator_profile", {}); vc = raw.get("volume_config", {})
        rev = p.get("mm_revenue_monthly", p.get("monthly_revenue"))
        if rev is None: rev = p.get("current_fan_count", p.get("fan_count", 1000)) * 2.50

        # Tier with hysteresis (15% buffer)
        tier = self._get_tier(rev, vc.get("previous_tier"))
        t = TIERS[tier]; hadj = health.get("volume_adjustment", 0)
        # Multiplicative stacking: multiple triggers compound (e.g., 1.2 * 0.85 = 1.02)
        tmult = 1.0
        for tr in triggers: tmult *= tr.get("adjustment_multiplier", 1.0)

        def adj(r): b = (r[0]+r[1])/2; return [r[0], max(r[0], min(r[1], round(b*tmult+hadj)))]

        # Weekly distribution with calendar boosts
        wd = datetime.strptime(week_start, "%Y-%m-%d").date()
        dist, boosts = {}, []
        for i in range(7):
            d = wd + timedelta(days=i); dn = d.strftime("%A").lower()
            boost = self._cal_boost(d)
            if boost > 1: boosts.append({"date": d.isoformat(),
                "type": "holiday" if boost >= 1.3 else "payday", "multiplier": boost})
            dm = 1.1 if dn in ["friday","saturday","sunday"] else 1.0
            dist[dn] = {"revenue": round(adj(t[2])[1]*boost*dm),
                        "engagement": round(adj(t[3])[1]*dm), "retention": round(adj(t[4])[1])}

        cat = p.get("content_category", "softcore")
        bm = BUMP_MULT.get(cat, 1.5); bm = min(bm, 1.5) if tier != "MINIMAL" else bm

        return {"tier": tier, "mm_revenue_monthly": rev, "revenue_per_day": list(t[2]),
                "engagement_per_day": list(t[3]), "retention_per_day": list(t[4]),
                "weekly_distribution": dist, "bump_multiplier": bm, "calendar_boosts": boosts,
                "trigger_multiplier": round(tmult, 2), "health_adjustment": hadj}

    def _get_tier(self, rev: float, prev: str | None) -> str:
        """Tier assignment with 15% hysteresis buffer."""
        tier = "MINIMAL"
        for t in TIER_ORDER:
            if rev >= TIERS[t][0]: tier = t
        if prev and TIER_ORDER.index(prev) > TIER_ORDER.index(tier):
            if rev >= TIERS[prev][0] * 0.85: return prev  # Hysteresis
        return tier

    def _cal_boost(self, d: datetime.date) -> float:
        """Calendar boost: payday +20%, holiday +30%."""
        last = monthrange(d.year, d.month)[1]
        pay = d.day in (1, 15, last)
        hol = (d.month, d.day) in HOLIDAYS
        if d.month == 11 and d.weekday() == 3 and 22 <= d.day <= 28: hol = True  # Thanksgiving
        if d.month == 11 and d.weekday() == 4 and 23 <= d.day <= 29: hol = True  # Black Friday
        return 1.30 if hol else 1.20 if pay else 1.0

    def _gen_timing(self, vol: dict, week_start: str) -> dict:
        """Generate timing slots with jitter (avoid :00/:15/:30/:45)."""
        wd = datetime.strptime(week_start, "%Y-%m-%d").date()
        slots = {}
        for i in range(7):
            d = wd + timedelta(days=i); dn = d.strftime("%A").lower()
            dv = vol["weekly_distribution"].get(dn, {})
            ph = PRIME_HOURS.get(dn, PRIME_HOURS["monday"])
            s = []
            s.extend(self._alloc(ph[:2], dv.get("revenue", 4), "revenue"))
            s.extend(self._alloc(ph[2:] + [(9,12),(14,17)], dv.get("engagement", 4), "engagement"))
            s.extend(self._alloc([(8,10),(18,20)], dv.get("retention", 2), "retention"))
            s.sort(key=lambda x: (x["hour"], x["minute"]))
            for idx, x in enumerate(s): x["priority"] = idx + 1
            slots[d.isoformat()] = s
        return slots

    def _alloc(self, hrs: list, cnt: int, cat: str) -> list:
        """Allocate slots across hours with jitter."""
        if not hrs or cnt <= 0: return []
        avail = [h for r in hrs for h in range(r[0], min(r[1], 24))]
        if not avail: return []
        slots = []
        for i in range(cnt):
            h = avail[i % len(avail)]
            if h >= 24: h -= 24
            if 3 <= h < 7: h = 7 if h >= 5 else 23  # Dead zone shift
            m = self._jitter((i * 17) % 60)
            slots.append({"hour": h, "minute": m, "category": cat})
        return slots

    def _jitter(self, base: int) -> int:
        """Jitter ±7-8 min, never land on :00/:15/:30/:45."""
        for _ in range(10):
            j = random.randint(-7, 8)
            r = (base + j) % 60
            if r % 15 != 0: return r
        return (base + 3) % 60 if base % 15 == 0 else base

    def _vault_types(self, raw: dict) -> list[str]:
        """Extract allowed content types from raw data.

        Uses allowed_content_types from bundled get_creator_profile response.
        This is authoritative data from vault_matrix (has_content=1).
        """
        v = raw.get("allowed_content_types", {})

        # Primary source: allowed_type_names list
        type_names = v.get("allowed_type_names", [])
        if type_names:
            return type_names

        # Fallback: extract from allowed_types array
        allowed = v.get("allowed_types", [])
        return [x.get("type_name") for x in allowed if x.get("type_name")]

    def _avoid_types(self, raw: dict) -> list[str]:
        """Extract AVOID tier content types from raw data.

        OPTIMIZATION (v1.4.0): Now uses pre-computed avoid_types from bundled
        response instead of re-iterating through rankings.
        """
        r = raw.get("content_type_rankings", {})

        # Primary: Use pre-computed list (new structure)
        avoid_list = r.get("avoid_types", [])
        if avoid_list:
            return avoid_list

        # Fallback: Compute from rankings (legacy)
        rankings = r.get("rankings", r.get("content_types", []))
        return [
            x.get("type_name", x.get("content_type", ""))
            for x in rankings
            if x.get("performance_tier") == "AVOID"
        ]

    def _all_content_rankings(self, raw: dict) -> list[dict]:
        """Extract all content type rankings with their tiers.

        Returns list of {type_name, performance_tier} for all ranked content types.
        Note: Despite historical name, this returns ALL tiers, not just TOP.

        OPTIMIZATION (v1.4.0): Now uses pre-computed rankings from bundled response.
        """
        r = raw.get("content_type_rankings", {})

        # Primary: Use rankings list (new structure)
        rankings = r.get("rankings", [])
        if rankings:
            return [
                {
                    "type_name": x.get("type_name", ""),
                    "performance_tier": x.get("performance_tier", "MID")
                }
                for x in rankings
            ]

        # Fallback: Use legacy content_types key
        content_types = r.get("content_types", [])
        return [
            {
                "type_name": x.get("type_name", x.get("content_type", "")),
                "performance_tier": x.get("performance_tier", "MID")
            }
            for x in content_types
        ]

    def _pricing(self, raw: dict) -> dict:
        p = raw.get("creator_profile", {})
        return {"base_price": p.get("base_price", p.get("default_ppv_price", 15.00)),
                "fan_count": p.get("current_fan_count", p.get("fan_count", 0)),
                "price_floor": 5.00, "price_ceiling": 50.00,
                "active_ab_experiments": p.get("has_active_experiments", False)}

# --- CLI ---
if __name__ == "__main__":
    import argparse
    class MockMCP:
        async def get_creator_profile(self, c, include_analytics=True, include_volume=True, include_content_rankings=True, include_vault=True):
            response = {
                "found": True,
                "creator": {"is_active": True, "page_type": "paid", "current_fan_count": 5000},
                "analytics_summary": {"mm_revenue_30d": 2500, "mm_revenue_confidence": "medium"},
                "volume_assignment": {"volume_level": "STANDARD", "revenue_per_day": [4, 6]},
                "top_content_types": [{"type_name": "lingerie", "performance_tier": "TOP", "rps": 180}],
                "metadata": {"mcp_calls_saved": 4}
            }
            if include_vault:
                response["allowed_content_types"] = {
                    "allowed_types": [
                        {"type_name": "lingerie", "type_category": "softcore", "is_explicit": True},
                        {"type_name": "b/g", "type_category": "explicit", "is_explicit": True},
                        {"type_name": "solo", "type_category": "softcore", "is_explicit": True}
                    ],
                    "allowed_type_names": ["lingerie", "b/g", "solo"],
                    "type_count": 3,
                    "vault_hash": "sha256:mock12345678"
                }
            return response
        async def get_persona_profile(self, c): return {"primary_tone": "GFE"}
        async def get_active_volume_triggers(self, c): return []
        async def get_performance_trends(self, c, p): return {"saturation_score": 45, "consecutive_decline_weeks": 0}

    async def main(cid: str, ws: str):
        ctx = await PreflightEngine(MockMCP()).execute(cid, ws)
        print(f"CreatorContext: {ctx.creator_id}, Tier: {ctx.volume_config['tier']}, "
              f"Health: {ctx.health['status']}, Triggers: {len(ctx.active_triggers)}, "
              f"Duration: {ctx.preflight_duration_ms:.1f}ms")

    p = argparse.ArgumentParser(description="EROS Preflight v1.0")
    p.add_argument("--creator", required=True); p.add_argument("--week", required=True)
    a = p.parse_args()
    asyncio.run(main(a.creator, a.week))
