"""Unit tests for EROS v1.0 Preflight Engine (<200 lines)."""
from __future__ import annotations
import pytest
from datetime import datetime
from ..preflight import PreflightEngine, TIERS, TIER_ORDER
from .mocks import MockMCPClient, TestDataFactory, CreatorConfig


class TestVolumeTiers:
    """Volume tier assignment from DOMAIN_KNOWLEDGE.md Section 2."""

    @pytest.fixture
    def engine(self):
        return PreflightEngine(MockMCPClient())

    def test_minimal_tier(self, engine):
        """Revenue < $150 -> MINIMAL."""
        assert engine._get_tier(0, None) == "MINIMAL"
        assert engine._get_tier(100, None) == "MINIMAL"
        assert engine._get_tier(149, None) == "MINIMAL"

    def test_lite_tier(self, engine):
        """$150-$799 -> LITE."""
        assert engine._get_tier(150, None) == "LITE"
        assert engine._get_tier(500, None) == "LITE"
        assert engine._get_tier(799, None) == "LITE"

    def test_standard_tier(self, engine):
        """$800-$2999 -> STANDARD."""
        assert engine._get_tier(800, None) == "STANDARD"
        assert engine._get_tier(1500, None) == "STANDARD"
        assert engine._get_tier(2999, None) == "STANDARD"

    def test_high_value_tier(self, engine):
        """$3000-$7999 -> HIGH_VALUE."""
        assert engine._get_tier(3000, None) == "HIGH_VALUE"
        assert engine._get_tier(5000, None) == "HIGH_VALUE"
        assert engine._get_tier(7999, None) == "HIGH_VALUE"

    def test_premium_tier(self, engine):
        """$8000+ -> PREMIUM."""
        assert engine._get_tier(8000, None) == "PREMIUM"
        assert engine._get_tier(15000, None) == "PREMIUM"
        assert engine._get_tier(100000, None) == "PREMIUM"

    def test_tier_hysteresis(self, engine):
        """15% buffer prevents flip-flopping."""
        # At $750 with prev=STANDARD ($800 threshold), 85% = $680, so stays STANDARD
        assert engine._get_tier(750, "STANDARD") == "STANDARD"
        # At $600 with prev=STANDARD, below 85% threshold ($680), drops to LITE
        assert engine._get_tier(600, "STANDARD") == "LITE"
        # At $140 with prev=LITE ($150 threshold), 85% = $127.50, stays LITE
        assert engine._get_tier(140, "LITE") == "LITE"


class TestHealthDetection:
    """Death spiral detection from DOMAIN_KNOWLEDGE.md Section 7."""

    def test_healthy_status(self):
        """< 2 weeks decline -> HEALTHY."""
        engine = PreflightEngine(MockMCPClient(CreatorConfig(decline_weeks=0)))
        health = engine._calc_health({"performance_trends": {"consecutive_decline_weeks": 0}})
        assert health["status"] == "HEALTHY"

    def test_warning_status(self):
        """2-3 weeks decline -> WARNING."""
        engine = PreflightEngine(MockMCPClient())
        health = engine._calc_health({"performance_trends": {"consecutive_decline_weeks": 2}})
        assert health["status"] == "WARNING"
        health = engine._calc_health({"performance_trends": {"consecutive_decline_weeks": 3}})
        assert health["status"] == "WARNING"

    def test_death_spiral_status(self):
        """4+ weeks decline -> DEATH_SPIRAL."""
        engine = PreflightEngine(MockMCPClient())
        health = engine._calc_health({"performance_trends": {"consecutive_decline_weeks": 4}})
        assert health["status"] == "DEATH_SPIRAL"
        health = engine._calc_health({"performance_trends": {"consecutive_decline_weeks": 6}})
        assert health["status"] == "DEATH_SPIRAL"


class TestTriggerDetection:
    """5 trigger types from DOMAIN_KNOWLEDGE.md Section 8."""

    @pytest.fixture
    def engine(self):
        return PreflightEngine(MockMCPClient())

    def test_high_performer_trigger(self, engine):
        """RPS > $200 AND conversion > 6% -> HIGH_PERFORMER +20%."""
        raw = {"content_type_rankings": {"content_types": [
            {"type_name": "lingerie", "rps": 250, "conversion_rate": 7.0, "sends_last_30d": 15}
        ]}}
        triggers = engine._detect_triggers(raw)
        hp = [t for t in triggers if t["trigger_type"] == "HIGH_PERFORMER"]
        assert len(hp) == 1
        assert hp[0]["adjustment_multiplier"] == 1.20

    def test_trending_up_trigger(self, engine):
        """WoW RPS +15% -> TRENDING_UP +10%."""
        raw = {"content_type_rankings": {"content_types": [
            {"type_name": "lingerie", "rps": 100, "conversion_rate": 4.0, "wow_rps_change": 20}
        ]}}
        triggers = engine._detect_triggers(raw)
        tu = [t for t in triggers if t["trigger_type"] == "TRENDING_UP"]
        assert len(tu) == 1
        assert tu[0]["adjustment_multiplier"] == 1.10

    def test_emerging_winner_trigger(self, engine):
        """RPS > $150 AND <3 uses/30d -> EMERGING_WINNER +30%."""
        raw = {"content_type_rankings": {"content_types": [
            {"type_name": "lingerie", "rps": 180, "conversion_rate": 4.0, "sends_last_30d": 2}
        ]}}
        triggers = engine._detect_triggers(raw)
        ew = [t for t in triggers if t["trigger_type"] == "EMERGING_WINNER"]
        assert len(ew) == 1
        assert ew[0]["adjustment_multiplier"] == 1.30

    def test_saturating_trigger(self, engine):
        """Declining RPS 3+ days -> SATURATING -15%."""
        raw = {"content_type_rankings": {"content_types": [
            {"type_name": "lingerie", "rps": 100, "conversion_rate": 4.0, "declining_rps_days": 4}
        ]}}
        triggers = engine._detect_triggers(raw)
        sat = [t for t in triggers if t["trigger_type"] == "SATURATING"]
        assert len(sat) == 1
        assert sat[0]["adjustment_multiplier"] == 0.85

    def test_audience_fatigue_trigger(self, engine):
        """Open rate -10%/7d -> AUDIENCE_FATIGUE -25%."""
        raw = {"content_type_rankings": {"content_types": [
            {"type_name": "lingerie", "rps": 100, "conversion_rate": 4.0, "open_rate_7d_change": -15}
        ]}}
        triggers = engine._detect_triggers(raw)
        af = [t for t in triggers if t["trigger_type"] == "AUDIENCE_FATIGUE"]
        assert len(af) == 1
        assert af[0]["adjustment_multiplier"] == 0.75


class TestTimingGeneration:
    """Timing slot generation from DOMAIN_KNOWLEDGE.md Section 5."""

    @pytest.fixture
    def engine(self):
        return PreflightEngine(MockMCPClient())

    def test_jitter_avoids_round_minutes(self, engine):
        """Jitter should never land on :00/:15/:30/:45."""
        for base in range(60):
            for _ in range(20):
                result = engine._jitter(base)
                assert result % 15 != 0, f"Jitter landed on {result} from base {base}"

    def test_dead_zone_shift(self, engine):
        """3-7 AM hours shifted to safe times."""
        vol = {"weekly_distribution": {"monday": {"revenue": 2, "engagement": 2, "retention": 1}}}
        slots = engine._gen_timing(vol, "2026-01-05")  # Monday
        for date_slots in slots.values():
            for slot in date_slots:
                hour = slot["hour"]
                assert not (3 <= hour < 7), f"Slot in dead zone: {hour}:00"

    def test_prime_hours_allocation(self, engine):
        """Revenue slots should be in prime hours (12-2pm, 7-10pm for Monday)."""
        vol = {"weekly_distribution": {"monday": {"revenue": 4, "engagement": 2, "retention": 1}}}
        slots = engine._gen_timing(vol, "2026-01-05")
        monday_slots = slots.get("2026-01-05", [])
        rev_slots = [s for s in monday_slots if s["category"] == "revenue"]
        prime_hours = {12, 13, 19, 20, 21}  # Monday prime hours
        prime_count = sum(1 for s in rev_slots if s["hour"] in prime_hours)
        assert prime_count >= len(rev_slots) // 2, "Most revenue slots should be in prime hours"


class TestCalendarBoosts:
    """Calendar awareness from DOMAIN_KNOWLEDGE.md Section 12."""

    @pytest.fixture
    def engine(self):
        return PreflightEngine(MockMCPClient())

    def test_payday_boost(self, engine):
        """1st, 15th, last day = +20%."""
        from datetime import date
        assert engine._cal_boost(date(2026, 1, 1)) == 1.30  # New Year's holiday
        assert engine._cal_boost(date(2026, 1, 15)) == 1.20  # Payday
        assert engine._cal_boost(date(2026, 1, 31)) == 1.20  # Last day
        assert engine._cal_boost(date(2026, 1, 10)) == 1.0  # Normal day

    def test_holiday_boost(self, engine):
        """Fixed holidays = +30%."""
        from datetime import date
        assert engine._cal_boost(date(2026, 1, 1)) == 1.30   # New Year's
        assert engine._cal_boost(date(2026, 2, 14)) == 1.30  # Valentine's
        assert engine._cal_boost(date(2026, 7, 4)) == 1.30   # July 4th
        assert engine._cal_boost(date(2026, 10, 31)) == 1.30 # Halloween
        assert engine._cal_boost(date(2026, 12, 25)) == 1.30 # Christmas


@pytest.mark.asyncio
class TestPreflightExecution:
    """End-to-end preflight execution tests."""

    async def test_execute_success(self):
        """Happy path preflight execution."""
        mcp = MockMCPClient(TestDataFactory.STANDARD)
        engine = PreflightEngine(mcp)
        ctx = await engine.execute("alexia", "2026-01-06")
        assert ctx.creator_id == "alexia"
        assert ctx.page_type == "paid"
        assert len(ctx.vault_types) > 0
        assert ctx.volume_config["tier"] in TIER_ORDER
        # v1.1.0: Reduced from 7 to 4 MCP calls via bundled get_creator_profile
        assert ctx.mcp_calls_made == 4

    async def test_execute_inactive_creator_fails(self):
        """Inactive creator raises ValueError."""
        cfg = CreatorConfig(is_active=False)
        mcp = MockMCPClient(cfg)
        engine = PreflightEngine(mcp)
        with pytest.raises(ValueError, match="not active"):
            await engine.execute("inactive", "2026-01-06")
