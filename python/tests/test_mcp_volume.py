"""
Integration tests for the enhanced get_volume_config MCP tool.

Tests cover:
- Basic functionality (required fields, weekly_distribution structure)
- Tier fallback chain (tier_override takes precedence)
- Trigger simulation (trigger_overrides bypass DB)
- Calendar awareness (New Year's, paydays, weekend boosts)
- Historical reconstruction (past/future week_type)
- Hash computation (deterministic, correct format)
- Health override

Reference: Phase 2 of volume_utils refactoring
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add mcp_server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))

from volume_utils import (
    TIERS,
    TIER_ORDER,
    DAY_NAMES,
    compute_volume_config_hash,
    get_week_dates,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db_connection():
    """Mock database connection returning test data."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn


@pytest.fixture
def mock_creator_row():
    """Standard creator row data for tests."""
    return {
        "page_type": "paid",
        "content_category": "softcore",
        "current_fan_count": 5000,
        "current_message_net": 2500,
        "current_posts_net": 500,
    }


@pytest.fixture
def mock_volume_row():
    """Standard volume assignment row."""
    return {
        "volume_level": "STANDARD",
        "ppv_per_day": 5,
        "bump_per_day": 3,
    }


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================

class TestBasicFunctionality:
    """Tests for core get_volume_config functionality."""

    def test_weekly_distribution_has_seven_days(self, mock_db_connection, mock_creator_row):
        """Weekly distribution must contain exactly 7 days."""
        from main import get_volume_config

        # Mock the database
        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 10, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2026-01-06")

        assert "error" not in result, f"Got error: {result.get('error')}"
        assert "weekly_distribution" in result
        assert len(result["weekly_distribution"]) == 7

        # Verify all day names present
        expected_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        assert set(result["weekly_distribution"].keys()) == expected_days

    def test_required_fields_present(self, mock_db_connection, mock_creator_row):
        """All required response fields must be present."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 10, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2026-01-06")

        required_fields = [
            "creator_id", "week_start", "tier", "tier_source", "tier_confidence",
            "base_ranges", "trigger_multiplier", "triggers_applied",
            "health", "bump_multiplier", "content_category",
            "weekly_distribution", "calendar_boosts",
            "temporal_context", "metadata"
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_invalid_week_start_format(self):
        """Invalid week_start format returns error."""
        from main import get_volume_config

        with patch("main.validate_creator_id", return_value=(True, "test")):
            result = get_volume_config("test", "2026/01/06")  # Wrong format

        assert "error" in result
        assert "Invalid week_start format" in result["error"]

    def test_invalid_creator_id(self):
        """Invalid creator_id returns error."""
        from main import get_volume_config

        with patch("main.validate_creator_id", return_value=(False, "Invalid characters")):
            result = get_volume_config("!!!invalid!!!", "2026-01-06")

        assert "error" in result
        assert "Invalid creator_id" in result["error"]


# =============================================================================
# TIER FALLBACK CHAIN TESTS
# =============================================================================

class TestTierFallbackChain:
    """Tests for the 4-level tier determination fallback chain."""

    def test_tier_override_takes_precedence(self, mock_db_connection, mock_creator_row):
        """tier_override must override all other tier sources."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "MINIMAL", "ppv_per_day": 1, "bump_per_day": 1},  # DB says MINIMAL
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        tier_override="PREMIUM"  # Force PREMIUM
                    )

        assert result["tier"] == "PREMIUM"
        assert result["tier_source"] == "override"
        assert result["tier_confidence"] == "high"

    def test_tier_override_invalid_tier_ignored(self, mock_db_connection, mock_creator_row):
        """Invalid tier_override should be ignored and fallback used."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        tier_override="INVALID_TIER"  # Not in TIER_ORDER
                    )

        # Should fall back to volume_assignments
        assert result["tier"] == "STANDARD"
        assert result["tier_source"] == "volume_assignments"

    def test_volume_assignments_used_when_available(self, mock_db_connection, mock_creator_row):
        """Level 1: volume_assignments table is preferred source."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,  # Creator row
            {"volume_level": "HIGH_VALUE", "ppv_per_day": 7, "bump_per_day": 4},  # Volume assignment
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2026-01-06")

        assert result["tier"] == "HIGH_VALUE"
        assert result["tier_source"] == "volume_assignments"
        assert result["tier_confidence"] == "high"


# =============================================================================
# TRIGGER SIMULATION TESTS
# =============================================================================

class TestTriggerSimulation:
    """Tests for trigger_overrides simulation feature."""

    def test_trigger_overrides_bypass_db(self, mock_db_connection, mock_creator_row):
        """trigger_overrides should bypass DB lookup entirely."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        # Even if DB returns triggers, they should be ignored
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"trigger_type": "DB_TRIGGER", "adjustment_multiplier": 0.5}
        ]

        simulated_triggers = [
            {"trigger_type": "HIGH_PERFORMER", "adjustment_multiplier": 1.2},
            {"trigger_type": "CONTENT_HOT", "adjustment_multiplier": 1.1},
        ]

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        trigger_overrides=simulated_triggers,
                        include_trigger_breakdown=True
                    )

        # Should use simulated triggers, not DB
        assert result["triggers_applied"] == 2
        assert result["trigger_multiplier"] == pytest.approx(1.2 * 1.1, rel=1e-4)
        assert result["temporal_context"]["data_accuracy"]["triggers"] == "simulated"

        # Trigger details should show simulated triggers
        assert result["trigger_details"] is not None
        assert len(result["trigger_details"]) == 2
        assert result["trigger_details"][0]["trigger_type"] == "HIGH_PERFORMER"

    def test_empty_trigger_overrides_gives_no_triggers(self, mock_db_connection, mock_creator_row):
        """Empty trigger_overrides list should result in no triggers (bypass DB)."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"trigger_type": "DB_TRIGGER", "adjustment_multiplier": 1.5}
        ]

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        trigger_overrides=[]  # Empty list means no triggers
                    )

        assert result["triggers_applied"] == 0
        assert result["trigger_multiplier"] == 1.0
        assert result["temporal_context"]["data_accuracy"]["triggers"] == "simulated"


# =============================================================================
# CALENDAR AWARENESS TESTS
# =============================================================================

class TestCalendarAwareness:
    """Tests for calendar boost calculations."""

    def test_new_years_day_holiday_boost(self, mock_db_connection, mock_creator_row):
        """New Year's Day (Jan 1) should get 1.30x holiday boost."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        # Week starting Dec 28, 2025 includes Jan 1, 2026
        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2025-12-29")

        # Find New Year's Day in calendar_boosts
        ny_boost = next(
            (b for b in result["calendar_boosts"] if b["date"] == "2026-01-01"),
            None
        )
        assert ny_boost is not None, "New Year's Day should have a calendar boost"
        assert ny_boost["boost"] == pytest.approx(1.30, rel=1e-2)
        assert ny_boost["reason"] == "holiday"

    def test_payday_boost_fifteenth(self, mock_db_connection, mock_creator_row):
        """15th of month should get 1.20x payday boost."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        # Week starting Jan 12, 2026 includes Jan 15 (Thursday)
        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2026-01-12")

        payday_boost = next(
            (b for b in result["calendar_boosts"] if b["date"] == "2026-01-15"),
            None
        )
        assert payday_boost is not None, "Jan 15 should have a payday boost"
        assert payday_boost["boost"] == pytest.approx(1.20, rel=1e-2)
        assert payday_boost["reason"] == "payday"

    def test_weekend_boost_applied(self, mock_db_connection, mock_creator_row):
        """Friday/Saturday/Sunday should have weekend_boost > 1.0."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2026-01-05")  # Monday start

        # Check weekend days have boost > 1.0
        for day in ["friday", "saturday", "sunday"]:
            assert result["weekly_distribution"][day]["weekend_boost"] == pytest.approx(1.10, rel=1e-2), \
                f"{day} should have 1.10x weekend boost"

        # Check weekdays have no weekend boost
        for day in ["monday", "tuesday", "wednesday", "thursday"]:
            assert result["weekly_distribution"][day]["weekend_boost"] == pytest.approx(1.0, rel=1e-2), \
                f"{day} should have no weekend boost"


# =============================================================================
# TEMPORAL CONTEXT TESTS
# =============================================================================

class TestTemporalContext:
    """Tests for past/current/future week_type detection."""

    def test_past_week_detection(self, mock_db_connection, mock_creator_row):
        """Week entirely in the past should have week_type='past'."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        # Use a week from 2020 which is definitely in the past
        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2020-01-06")

        assert result["temporal_context"]["week_type"] == "past"

    def test_future_week_detection(self, mock_db_connection, mock_creator_row):
        """Week entirely in the future should have week_type='future'."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        # Use a week far in the future
        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2030-01-06")

        assert result["temporal_context"]["week_type"] == "future"


# =============================================================================
# HASH COMPUTATION TESTS
# =============================================================================

class TestHashComputation:
    """Tests for deterministic hash computation."""

    def test_hash_format_correct(self, mock_db_connection, mock_creator_row):
        """Hash should be in format 'sha256:<16-hex-chars>'."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2026-01-06")

        config_hash = result["metadata"]["volume_config_hash"]
        assert config_hash.startswith("sha256:"), f"Hash should start with 'sha256:', got: {config_hash}"

        hex_part = config_hash.replace("sha256:", "")
        assert len(hex_part) == 16, f"Hash hex part should be 16 chars, got: {len(hex_part)}"
        assert all(c in "0123456789abcdef" for c in hex_part), "Hash should be lowercase hex"

    def test_hash_deterministic(self, mock_db_connection, mock_creator_row):
        """Same inputs should produce same hash."""
        from main import get_volume_config

        def setup_mock():
            mock_db_connection.execute.return_value.fetchone.side_effect = [
                mock_creator_row,
                {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
                {"send_count": 5, "avg_view_rate": 0.5},
            ]
            mock_db_connection.execute.return_value.fetchall.return_value = []

        # First call
        setup_mock()
        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result1 = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        tier_override="STANDARD"
                    )

        # Second call with same parameters
        setup_mock()
        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result2 = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        tier_override="STANDARD"
                    )

        assert result1["metadata"]["volume_config_hash"] == result2["metadata"]["volume_config_hash"]

    def test_hash_changes_with_tier(self):
        """Different tiers should produce different hashes."""
        hash1 = compute_volume_config_hash(
            tier="STANDARD",
            trigger_multiplier=1.0,
            health_adjustment=0,
            week_start="2026-01-06",
            boost_dates=[]
        )
        hash2 = compute_volume_config_hash(
            tier="PREMIUM",
            trigger_multiplier=1.0,
            health_adjustment=0,
            week_start="2026-01-06",
            boost_dates=[]
        )
        assert hash1 != hash2, "Different tiers should produce different hashes"

    def test_hash_changes_with_trigger_multiplier(self):
        """Different trigger multipliers should produce different hashes."""
        hash1 = compute_volume_config_hash(
            tier="STANDARD",
            trigger_multiplier=1.0,
            health_adjustment=0,
            week_start="2026-01-06",
            boost_dates=[]
        )
        hash2 = compute_volume_config_hash(
            tier="STANDARD",
            trigger_multiplier=1.2,
            health_adjustment=0,
            week_start="2026-01-06",
            boost_dates=[]
        )
        assert hash1 != hash2, "Different trigger multipliers should produce different hashes"


# =============================================================================
# HEALTH OVERRIDE TESTS
# =============================================================================

class TestHealthOverride:
    """Tests for health_override simulation feature."""

    def test_health_override_applied(self, mock_db_connection, mock_creator_row):
        """health_override should override calculated health status."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 28, "avg_view_rate": 0.5},  # Would calculate high saturation
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        health_override = {
            "status": "DEATH_SPIRAL",
            "saturation_score": 95,
            "opportunity_score": 5,
            "decline_weeks": 6,
            "volume_adjustment": -1
        }

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        health_override=health_override
                    )

        assert result["health"]["status"] == "DEATH_SPIRAL"
        assert result["health"]["saturation_score"] == 95
        assert result["health"]["decline_weeks"] == 6
        assert result["health"]["volume_adjustment"] == -1
        assert result["temporal_context"]["data_accuracy"]["health"] == "simulated"

    def test_health_override_affects_volumes(self, mock_db_connection, mock_creator_row):
        """Health volume_adjustment should affect calculated daily volumes."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        # Get baseline without health override
        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    baseline = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        health_override={"status": "HEALTHY", "volume_adjustment": 0}
                    )

        # Reset mock for second call
        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        # With +2 volume adjustment (hypothetical healthy opportunity)
        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    boosted = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        health_override={"status": "HEALTHY", "volume_adjustment": 2}
                    )

        # Monday revenue should be higher with +2 adjustment
        baseline_monday_rev = baseline["weekly_distribution"]["monday"]["revenue"]
        boosted_monday_rev = boosted["weekly_distribution"]["monday"]["revenue"]

        assert boosted_monday_rev >= baseline_monday_rev, \
            f"Positive health adjustment should increase volumes: {baseline_monday_rev} -> {boosted_monday_rev}"


# =============================================================================
# INCLUDE TRIGGER BREAKDOWN TESTS
# =============================================================================

class TestIncludeTriggerBreakdown:
    """Tests for include_trigger_breakdown parameter."""

    def test_trigger_details_included_when_requested(self, mock_db_connection, mock_creator_row):
        """trigger_details should be populated when include_trigger_breakdown=True."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {
                "trigger_type": "HIGH_PERFORMER",
                "adjustment_multiplier": 1.15,
                "content_type": None,
                "confidence": 0.85,
                "reason": "30-day RPS above threshold",
                "expires_at": None
            }
        ]

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        include_trigger_breakdown=True
                    )

        assert result["trigger_details"] is not None
        assert len(result["trigger_details"]) == 1
        assert result["trigger_details"][0]["trigger_type"] == "HIGH_PERFORMER"

    def test_trigger_details_none_when_not_requested(self, mock_db_connection, mock_creator_row):
        """trigger_details should be None when include_trigger_breakdown=False."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"trigger_type": "HIGH_PERFORMER", "adjustment_multiplier": 1.15}
        ]

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config(
                        "test_creator",
                        "2026-01-06",
                        include_trigger_breakdown=False  # Default
                    )

        assert result["trigger_details"] is None


# =============================================================================
# WEEKLY DISTRIBUTION STRUCTURE TESTS
# =============================================================================

class TestWeeklyDistributionStructure:
    """Tests for weekly_distribution data structure."""

    def test_each_day_has_required_fields(self, mock_db_connection, mock_creator_row):
        """Each day in weekly_distribution must have all required fields."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2026-01-05")  # Monday

        required_day_fields = [
            "date", "revenue", "engagement", "retention",
            "prime_hours", "calendar_boost", "weekend_boost", "day_multiplier"
        ]

        for day_name, day_data in result["weekly_distribution"].items():
            for field in required_day_fields:
                assert field in day_data, f"Day {day_name} missing required field: {field}"

    def test_dates_are_correct_sequence(self, mock_db_connection, mock_creator_row):
        """Dates in weekly_distribution should be a correct 7-day sequence."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        week_start = "2026-01-05"  # Monday
        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", week_start)

        expected_dates = get_week_dates(week_start)

        for i, day_name in enumerate(DAY_NAMES):
            actual_date = result["weekly_distribution"][day_name]["date"]
            expected_date = expected_dates[i].isoformat()
            assert actual_date == expected_date, \
                f"Day {day_name} has wrong date: expected {expected_date}, got {actual_date}"

    def test_volumes_are_positive_integers(self, mock_db_connection, mock_creator_row):
        """All volume values should be positive integers."""
        from main import get_volume_config

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            mock_creator_row,
            {"volume_level": "STANDARD", "ppv_per_day": 5, "bump_per_day": 3},
            {"send_count": 5, "avg_view_rate": 0.5},
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            with patch("main.validate_creator_id", return_value=(True, "test_creator")):
                with patch("main.resolve_creator_id", return_value={"found": True, "creator_id": "test_creator"}):
                    result = get_volume_config("test_creator", "2026-01-05")

        for day_name, day_data in result["weekly_distribution"].items():
            for vol_type in ["revenue", "engagement", "retention"]:
                vol = day_data[vol_type]
                assert isinstance(vol, int), f"{day_name}.{vol_type} should be int, got {type(vol)}"
                assert vol >= 1, f"{day_name}.{vol_type} should be >= 1, got {vol}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
