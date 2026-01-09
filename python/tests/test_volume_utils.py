"""
Comprehensive tests for volume_utils.py - SINGLE SOURCE OF TRUTH validation.

These tests ensure that the volume_utils module correctly implements all
tier logic, calendar boosts, and calculation functions as specified in
docs/DOMAIN_KNOWLEDGE.md Section 2 (Volume Tiers).

Run with: pytest python/tests/test_volume_utils.py -v
"""
import sys
from datetime import date
from pathlib import Path

import pytest

# Add mcp_server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))

from volume_utils import (
    # Constants
    TIERS,
    TIER_ORDER,
    HYSTERESIS_BUFFER,
    HOLIDAYS,
    PAYDAY_DAYS,
    HOLIDAY_BOOST,
    PAYDAY_BOOST,
    WEEKEND_BOOST,
    PRIME_HOURS,
    DAY_NAMES,
    BUMP_MULT,
    DEATH_SPIRAL_WEEKS,
    WARNING_WEEKS,
    SATURATION_THRESHOLD,
    # Functions
    get_tier,
    get_tier_ranges,
    calc_calendar_boost,
    calc_weekend_boost,
    calc_bump_multiplier,
    calc_health_status,
    compute_volume_config_hash,
    get_week_dates,
    get_day_name,
)


class TestTierConstants:
    """Test that tier constants are correctly defined."""

    def test_tiers_has_all_expected_tiers(self):
        """Verify all 5 tiers exist."""
        expected_tiers = {"MINIMAL", "LITE", "STANDARD", "HIGH_VALUE", "PREMIUM"}
        assert set(TIERS.keys()) == expected_tiers

    def test_tier_order_matches_tiers_keys(self):
        """Verify TIER_ORDER contains all tiers in ascending order."""
        assert set(TIER_ORDER) == set(TIERS.keys())
        # Verify ascending revenue order
        prev_min = -1
        for tier in TIER_ORDER:
            current_min = TIERS[tier][0]
            assert current_min > prev_min, f"{tier} should have higher min than previous"
            prev_min = current_min

    def test_tier_tuple_structure(self):
        """Each tier tuple should have 5 elements: (min, max, rev_range, eng_range, ret_range)."""
        for tier_name, tier_data in TIERS.items():
            assert len(tier_data) == 5, f"{tier_name} should have 5 elements"
            min_rev, max_rev, rev_range, eng_range, ret_range = tier_data
            assert isinstance(min_rev, (int, float)), f"{tier_name} min_rev should be numeric"
            assert isinstance(max_rev, (int, float)), f"{tier_name} max_rev should be numeric"
            assert isinstance(rev_range, tuple) and len(rev_range) == 2
            assert isinstance(eng_range, tuple) and len(eng_range) == 2
            assert isinstance(ret_range, tuple) and len(ret_range) == 2

    def test_hysteresis_buffer_is_15_percent(self):
        """Hysteresis buffer should be 15% (0.15)."""
        assert HYSTERESIS_BUFFER == 0.15

    def test_tier_thresholds_match_domain_knowledge(self):
        """Verify tier thresholds match DOMAIN_KNOWLEDGE.md Section 2."""
        assert TIERS["MINIMAL"][0] == 0
        assert TIERS["LITE"][0] == 150
        assert TIERS["STANDARD"][0] == 800
        assert TIERS["HIGH_VALUE"][0] == 3000
        assert TIERS["PREMIUM"][0] == 8000


class TestGetTier:
    """Test tier calculation with hysteresis."""

    def test_minimal_tier_at_zero(self):
        """Zero revenue should be MINIMAL."""
        assert get_tier(0) == "MINIMAL"

    def test_minimal_tier_at_boundary(self):
        """Revenue at 149 should be MINIMAL."""
        assert get_tier(149) == "MINIMAL"

    def test_lite_tier_at_boundary(self):
        """Revenue at 150 should be LITE."""
        assert get_tier(150) == "LITE"

    def test_standard_tier_at_boundary(self):
        """Revenue at 800 should be STANDARD."""
        assert get_tier(800) == "STANDARD"

    def test_high_value_tier_at_boundary(self):
        """Revenue at 3000 should be HIGH_VALUE."""
        assert get_tier(3000) == "HIGH_VALUE"

    def test_premium_tier_at_boundary(self):
        """Revenue at 8000 should be PREMIUM."""
        assert get_tier(8000) == "PREMIUM"

    def test_premium_tier_high_revenue(self):
        """Very high revenue should be PREMIUM."""
        assert get_tier(50000) == "PREMIUM"

    def test_negative_revenue_becomes_minimal(self):
        """Negative revenue should be treated as MINIMAL."""
        assert get_tier(-100) == "MINIMAL"

    def test_hysteresis_retains_higher_tier_within_buffer(self):
        """Revenue within 15% of previous tier minimum should retain previous tier."""
        # STANDARD minimum is 800, 15% buffer = 680
        # Revenue of 750 is within buffer (>= 680), should retain STANDARD
        assert get_tier(750, previous_tier="STANDARD") == "STANDARD"

    def test_hysteresis_drops_tier_below_buffer(self):
        """Revenue below 15% buffer should drop to calculated tier."""
        # STANDARD minimum is 800, 15% buffer = 680
        # Revenue of 600 is below buffer, should drop to LITE
        assert get_tier(600, previous_tier="STANDARD") == "LITE"

    def test_hysteresis_only_applies_when_dropping(self):
        """Hysteresis should not apply when tier would increase."""
        # Previous tier is LITE, but revenue qualifies for STANDARD
        assert get_tier(1000, previous_tier="LITE") == "STANDARD"

    def test_hysteresis_with_invalid_previous_tier(self):
        """Invalid previous tier should be ignored."""
        assert get_tier(750, previous_tier="INVALID") == "LITE"

    def test_hysteresis_with_none_previous_tier(self):
        """None previous tier should use calculated tier."""
        assert get_tier(750, previous_tier=None) == "LITE"


class TestGetTierRanges:
    """Test tier range retrieval."""

    def test_standard_tier_ranges(self):
        """STANDARD tier should have correct ranges."""
        ranges = get_tier_ranges("STANDARD")
        assert ranges["revenue"] == (4, 6)
        assert ranges["engagement"] == (4, 6)
        assert ranges["retention"] == (2, 3)

    def test_minimal_tier_ranges(self):
        """MINIMAL tier should have correct ranges."""
        ranges = get_tier_ranges("MINIMAL")
        assert ranges["revenue"] == (1, 2)
        assert ranges["engagement"] == (1, 2)
        assert ranges["retention"] == (1, 1)

    def test_premium_tier_ranges(self):
        """PREMIUM tier should have correct ranges."""
        ranges = get_tier_ranges("PREMIUM")
        assert ranges["revenue"] == (8, 12)
        assert ranges["engagement"] == (6, 10)
        assert ranges["retention"] == (3, 5)

    def test_invalid_tier_defaults_to_minimal(self):
        """Invalid tier should return MINIMAL ranges."""
        ranges = get_tier_ranges("INVALID")
        assert ranges["revenue"] == (1, 2)

    def test_all_tiers_return_valid_ranges(self):
        """All tiers should return valid range dicts."""
        for tier in TIER_ORDER:
            ranges = get_tier_ranges(tier)
            assert "revenue" in ranges
            assert "engagement" in ranges
            assert "retention" in ranges
            assert all(isinstance(r, tuple) and len(r) == 2 for r in ranges.values())


class TestCalcCalendarBoost:
    """Test calendar boost calculations."""

    def test_new_years_day_boost(self):
        """New Year's Day should get holiday boost."""
        assert calc_calendar_boost(date(2026, 1, 1)) == HOLIDAY_BOOST

    def test_valentines_day_boost(self):
        """Valentine's Day should get holiday boost."""
        assert calc_calendar_boost(date(2026, 2, 14)) == HOLIDAY_BOOST

    def test_independence_day_boost(self):
        """Independence Day should get holiday boost."""
        assert calc_calendar_boost(date(2026, 7, 4)) == HOLIDAY_BOOST

    def test_halloween_boost(self):
        """Halloween should get holiday boost."""
        assert calc_calendar_boost(date(2026, 10, 31)) == HOLIDAY_BOOST

    def test_christmas_boost(self):
        """Christmas should get holiday boost."""
        assert calc_calendar_boost(date(2026, 12, 25)) == HOLIDAY_BOOST

    def test_thanksgiving_2026_boost(self):
        """Thanksgiving 2026 (Nov 26) should get holiday boost."""
        # In 2026, November 1 is Sunday, so 4th Thursday is Nov 26
        assert calc_calendar_boost(date(2026, 11, 26)) == HOLIDAY_BOOST

    def test_black_friday_2026_boost(self):
        """Black Friday 2026 (Nov 27) should get holiday boost."""
        # Day after Thanksgiving 2026
        assert calc_calendar_boost(date(2026, 11, 27)) == HOLIDAY_BOOST

    def test_first_of_month_payday_boost(self):
        """1st of month should get payday boost."""
        # Using a date that's not also a holiday
        assert calc_calendar_boost(date(2026, 3, 1)) == PAYDAY_BOOST

    def test_fifteenth_of_month_payday_boost(self):
        """15th of month should get payday boost."""
        assert calc_calendar_boost(date(2026, 3, 15)) == PAYDAY_BOOST

    def test_last_day_of_month_payday_boost(self):
        """Last day of month should get payday boost."""
        # March has 31 days
        assert calc_calendar_boost(date(2026, 3, 31)) == PAYDAY_BOOST
        # February 2026 has 28 days (not a leap year)
        assert calc_calendar_boost(date(2026, 2, 28)) == PAYDAY_BOOST

    def test_regular_day_no_boost(self):
        """Regular day should have no boost."""
        assert calc_calendar_boost(date(2026, 1, 8)) == 1.0

    def test_regular_mid_month_no_boost(self):
        """Mid-month non-payday should have no boost."""
        assert calc_calendar_boost(date(2026, 3, 10)) == 1.0


class TestCalcWeekendBoost:
    """Test weekend boost calculations."""

    def test_friday_boost(self):
        """Friday should get weekend boost."""
        # Jan 9, 2026 is Friday
        assert calc_weekend_boost(date(2026, 1, 9)) == WEEKEND_BOOST

    def test_saturday_boost(self):
        """Saturday should get weekend boost."""
        # Jan 10, 2026 is Saturday
        assert calc_weekend_boost(date(2026, 1, 10)) == WEEKEND_BOOST

    def test_sunday_boost(self):
        """Sunday should get weekend boost."""
        # Jan 11, 2026 is Sunday
        assert calc_weekend_boost(date(2026, 1, 11)) == WEEKEND_BOOST

    def test_monday_no_boost(self):
        """Monday should not get weekend boost."""
        # Jan 5, 2026 is Monday
        assert calc_weekend_boost(date(2026, 1, 5)) == 1.0

    def test_thursday_no_boost(self):
        """Thursday should not get weekend boost."""
        # Jan 8, 2026 is Thursday
        assert calc_weekend_boost(date(2026, 1, 8)) == 1.0


class TestCalcBumpMultiplier:
    """Test bump multiplier calculations."""

    def test_lifestyle_category(self):
        """Lifestyle category should have 1.0 multiplier."""
        assert calc_bump_multiplier("lifestyle", "STANDARD") == 1.0
        assert calc_bump_multiplier("lifestyle", "MINIMAL") == 1.0

    def test_softcore_category(self):
        """Softcore category should have 1.5 multiplier."""
        assert calc_bump_multiplier("softcore", "STANDARD") == 1.5
        assert calc_bump_multiplier("softcore", "MINIMAL") == 1.5

    def test_amateur_category_capped(self):
        """Amateur category should be capped at 1.5 for non-MINIMAL tiers."""
        assert calc_bump_multiplier("amateur", "STANDARD") == 1.5
        assert calc_bump_multiplier("amateur", "HIGH_VALUE") == 1.5

    def test_amateur_category_uncapped_minimal(self):
        """Amateur category should be 2.0 for MINIMAL tier."""
        assert calc_bump_multiplier("amateur", "MINIMAL") == 2.0

    def test_explicit_category_capped(self):
        """Explicit category should be capped at 1.5 for non-MINIMAL tiers."""
        assert calc_bump_multiplier("explicit", "STANDARD") == 1.5
        assert calc_bump_multiplier("explicit", "PREMIUM") == 1.5

    def test_explicit_category_uncapped_minimal(self):
        """Explicit category should be 2.67 for MINIMAL tier."""
        assert calc_bump_multiplier("explicit", "MINIMAL") == 2.67

    def test_unknown_category_defaults_to_1_5(self):
        """Unknown category should default to 1.5."""
        assert calc_bump_multiplier("unknown", "STANDARD") == 1.5
        assert calc_bump_multiplier("unknown", "MINIMAL") == 1.5


class TestCalcHealthStatus:
    """Test health status calculations."""

    def test_death_spiral_at_4_weeks(self):
        """4 weeks of decline should be DEATH_SPIRAL."""
        result = calc_health_status(saturation_score=50, decline_weeks=4)
        assert result["status"] == "DEATH_SPIRAL"
        assert result["volume_adjustment"] == -1

    def test_death_spiral_at_5_weeks(self):
        """5+ weeks of decline should be DEATH_SPIRAL."""
        result = calc_health_status(saturation_score=50, decline_weeks=5)
        assert result["status"] == "DEATH_SPIRAL"
        assert result["volume_adjustment"] == -1

    def test_warning_at_2_weeks(self):
        """2 weeks of decline should be WARNING."""
        result = calc_health_status(saturation_score=50, decline_weeks=2)
        assert result["status"] == "WARNING"
        assert result["volume_adjustment"] == 0

    def test_warning_at_3_weeks(self):
        """3 weeks of decline should be WARNING."""
        result = calc_health_status(saturation_score=50, decline_weeks=3)
        assert result["status"] == "WARNING"
        assert result["volume_adjustment"] == 0

    def test_healthy_with_low_saturation_opportunity(self):
        """Healthy with low saturation should have +1 adjustment."""
        result = calc_health_status(saturation_score=25, decline_weeks=0)
        assert result["status"] == "HEALTHY"
        assert result["volume_adjustment"] == 1

    def test_healthy_with_high_saturation_no_opportunity(self):
        """Healthy with high saturation should have 0 adjustment."""
        result = calc_health_status(saturation_score=50, decline_weeks=0)
        assert result["status"] == "HEALTHY"
        assert result["volume_adjustment"] == 0

    def test_saturation_threshold_boundary(self):
        """Saturation at threshold should have 0 adjustment."""
        result = calc_health_status(saturation_score=30, decline_weeks=0)
        assert result["status"] == "HEALTHY"
        assert result["volume_adjustment"] == 0  # At threshold, no bonus

    def test_none_saturation_defaults_to_50(self):
        """None saturation should default to 50."""
        result = calc_health_status(saturation_score=None, decline_weeks=0)
        assert result["status"] == "HEALTHY"
        assert result["volume_adjustment"] == 0  # 50 >= 30

    def test_none_decline_weeks_defaults_to_0(self):
        """None decline_weeks should default to 0."""
        result = calc_health_status(saturation_score=25, decline_weeks=None)
        assert result["status"] == "HEALTHY"
        assert result["volume_adjustment"] == 1


class TestComputeVolumeConfigHash:
    """Test hash computation for audit trails."""

    def test_hash_format(self):
        """Hash should be in sha256:<16-char-hex> format."""
        result = compute_volume_config_hash(
            tier="STANDARD",
            trigger_multiplier=1.2,
            health_adjustment=0,
            week_start="2026-01-06",
            boost_dates=["2026-01-01"]
        )
        assert result.startswith("sha256:")
        assert len(result) == 23  # "sha256:" (7) + 16 hex chars

    def test_hash_deterministic(self):
        """Same inputs should produce same hash."""
        hash1 = compute_volume_config_hash("STANDARD", 1.2, 0, "2026-01-06", ["2026-01-01"])
        hash2 = compute_volume_config_hash("STANDARD", 1.2, 0, "2026-01-06", ["2026-01-01"])
        assert hash1 == hash2

    def test_hash_changes_with_tier(self):
        """Different tier should produce different hash."""
        hash1 = compute_volume_config_hash("STANDARD", 1.2, 0, "2026-01-06", [])
        hash2 = compute_volume_config_hash("PREMIUM", 1.2, 0, "2026-01-06", [])
        assert hash1 != hash2

    def test_hash_changes_with_multiplier(self):
        """Different trigger multiplier should produce different hash."""
        hash1 = compute_volume_config_hash("STANDARD", 1.2, 0, "2026-01-06", [])
        hash2 = compute_volume_config_hash("STANDARD", 1.3, 0, "2026-01-06", [])
        assert hash1 != hash2

    def test_hash_changes_with_boost_dates(self):
        """Different boost dates should produce different hash."""
        hash1 = compute_volume_config_hash("STANDARD", 1.2, 0, "2026-01-06", ["2026-01-01"])
        hash2 = compute_volume_config_hash("STANDARD", 1.2, 0, "2026-01-06", ["2026-01-15"])
        assert hash1 != hash2

    def test_boost_dates_order_independent(self):
        """Boost dates order should not affect hash (sorted internally)."""
        hash1 = compute_volume_config_hash("STANDARD", 1.2, 0, "2026-01-06", ["2026-01-01", "2026-01-15"])
        hash2 = compute_volume_config_hash("STANDARD", 1.2, 0, "2026-01-06", ["2026-01-15", "2026-01-01"])
        assert hash1 == hash2


class TestGetWeekDates:
    """Test week date generation."""

    def test_returns_seven_dates(self):
        """Should return exactly 7 dates."""
        dates = get_week_dates("2026-01-06")
        assert len(dates) == 7

    def test_first_date_is_week_start(self):
        """First date should be the week_start."""
        dates = get_week_dates("2026-01-06")
        assert dates[0] == date(2026, 1, 6)

    def test_dates_are_consecutive(self):
        """Dates should be consecutive days."""
        dates = get_week_dates("2026-01-06")
        for i in range(1, 7):
            assert dates[i] == dates[i-1] + __import__('datetime').timedelta(days=1)

    def test_last_date_is_six_days_after(self):
        """Last date should be 6 days after week_start."""
        dates = get_week_dates("2026-01-06")
        assert dates[6] == date(2026, 1, 12)

    def test_handles_month_boundary(self):
        """Should handle weeks that cross month boundaries."""
        dates = get_week_dates("2026-01-27")
        assert dates[0] == date(2026, 1, 27)
        assert dates[6] == date(2026, 2, 2)


class TestGetDayName:
    """Test day name retrieval."""

    def test_monday(self):
        """Monday should return 'monday'."""
        # Jan 5, 2026 is Monday
        assert get_day_name(date(2026, 1, 5)) == "monday"

    def test_tuesday(self):
        """Tuesday should return 'tuesday'."""
        # Jan 6, 2026 is Tuesday
        assert get_day_name(date(2026, 1, 6)) == "tuesday"

    def test_wednesday(self):
        """Wednesday should return 'wednesday'."""
        # Jan 7, 2026 is Wednesday
        assert get_day_name(date(2026, 1, 7)) == "wednesday"

    def test_thursday(self):
        """Thursday should return 'thursday'."""
        # Jan 8, 2026 is Thursday
        assert get_day_name(date(2026, 1, 8)) == "thursday"

    def test_friday(self):
        """Friday should return 'friday'."""
        # Jan 9, 2026 is Friday
        assert get_day_name(date(2026, 1, 9)) == "friday"

    def test_saturday(self):
        """Saturday should return 'saturday'."""
        # Jan 10, 2026 is Saturday
        assert get_day_name(date(2026, 1, 10)) == "saturday"

    def test_sunday(self):
        """Sunday should return 'sunday'."""
        # Jan 11, 2026 is Sunday
        assert get_day_name(date(2026, 1, 11)) == "sunday"


class TestPrimeHoursConstant:
    """Test PRIME_HOURS constant structure."""

    def test_all_days_present(self):
        """All 7 days should be present in PRIME_HOURS."""
        expected_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        assert set(PRIME_HOURS.keys()) == expected_days

    def test_each_day_has_hour_ranges(self):
        """Each day should have list of (start, end) hour tuples."""
        for day, hours in PRIME_HOURS.items():
            assert isinstance(hours, list), f"{day} should have list of hours"
            assert len(hours) >= 1, f"{day} should have at least one hour range"
            for hour_range in hours:
                assert isinstance(hour_range, tuple) and len(hour_range) == 2
                start, end = hour_range
                assert isinstance(start, int) and isinstance(end, int)
                assert 0 <= start <= 25  # Allow hour 25 for late night
                assert start < end


class TestDayNamesConstant:
    """Test DAY_NAMES constant structure."""

    def test_has_seven_days(self):
        """DAY_NAMES should have exactly 7 entries."""
        assert len(DAY_NAMES) == 7

    def test_starts_with_monday(self):
        """DAY_NAMES should start with monday (matches weekday() convention)."""
        assert DAY_NAMES[0] == "monday"

    def test_ends_with_sunday(self):
        """DAY_NAMES should end with sunday."""
        assert DAY_NAMES[6] == "sunday"

    def test_all_lowercase(self):
        """All day names should be lowercase."""
        for day in DAY_NAMES:
            assert day == day.lower()
