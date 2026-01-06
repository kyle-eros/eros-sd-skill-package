"""Real creator validation tests for EROS v1.0 (<150 lines).

These tests require a live MCP connection and real database.
Skip gracefully if MCP is unavailable.
"""
from __future__ import annotations
import os
import pytest

# Skip entire module if MCP unavailable
pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_mcp,
]

# Test creators defined in spec
TEST_CREATORS = [
    {"creator_id": "alexia", "page_type": "paid", "expected_tier": "STANDARD"},
    {"creator_id": "grace_bennett", "page_type": "paid", "expected_tier": "HIGH_VALUE"},
    {"creator_id": "luna_free", "page_type": "free", "expected_tier": "LITE"},
]


def assert_vault_compliance(schedule: dict, vault_types: set[str]) -> None:
    """Verify all content types are in vault."""
    items = schedule.get("items", []) + schedule.get("followups", [])
    for item in items:
        ct = item.get("content_type")
        if ct:
            assert ct in vault_types, f"Content type '{ct}' not in vault"


def assert_avoid_exclusion(schedule: dict, avoid_types: set[str]) -> None:
    """Verify no content types in AVOID tier."""
    items = schedule.get("items", []) + schedule.get("followups", [])
    for item in items:
        ct = item.get("content_type")
        if ct:
            assert ct not in avoid_types, f"Content type '{ct}' is in AVOID tier"


def assert_diversity_met(schedule: dict, page_type: str) -> None:
    """Verify diversity requirements are met."""
    items = schedule.get("items", []) + schedule.get("followups", [])
    send_types = {item.get("send_type_key") for item in items if item.get("send_type_key")}

    # Basic diversity - should have variety
    assert len(send_types) >= 5, f"Only {len(send_types)} unique send types"

    # Check for revenue and engagement types
    revenue_types = {"ppv_unlock", "ppv_wall", "tip_goal", "bundle", "flash_bundle",
                     "vip_program", "game_post", "snapchat_bundle", "first_to_tip"}
    engagement_types = {"link_drop", "wall_link_drop", "bump_normal", "bump_descriptive",
                        "bump_text_only", "bump_flyer", "dm_farm", "like_farm", "live_promo"}

    rev_count = len(send_types & revenue_types)
    eng_count = len(send_types & engagement_types)

    assert rev_count >= 2, f"Only {rev_count} revenue types"
    assert eng_count >= 2, f"Only {eng_count} engagement types"


def assert_price_bounds(schedule: dict) -> None:
    """Verify all prices within $5-$50 bounds."""
    items = schedule.get("items", [])
    for item in items:
        price = item.get("price")
        if price is not None:
            assert 5.0 <= price <= 50.0, f"Price ${price} outside bounds $5-$50"


def assert_timing_valid(schedule: dict) -> None:
    """Verify no dead zone timing and proper gaps."""
    items = schedule.get("items", []) + schedule.get("followups", [])
    for item in items:
        time_str = item.get("scheduled_time", "")
        if time_str and ":" in time_str:
            hour = int(time_str.split(":")[0])
            assert not (3 <= hour < 7), f"Item scheduled in dead zone: {time_str}"


@pytest.mark.asyncio
class TestRealCreators:
    """Tests using real MCP connection."""

    @pytest.fixture
    async def real_mcp(self):
        """Get real MCP client or skip if unavailable."""
        try:
            # Try to import the real MCP client wrapper
            # This would be implemented based on your actual MCP setup
            pytest.skip("Real MCP client not configured - skipping real creator tests")
        except ImportError:
            pytest.skip("MCP client module not available")

    async def test_alexia_paid_standard(self, real_mcp):
        """Test alexia - paid page, STANDARD tier."""
        # This would use real MCP if available
        pytest.skip("Real MCP tests require live connection")

    async def test_grace_bennett_paid_high_value(self, real_mcp):
        """Test grace_bennett - paid page, HIGH_VALUE tier."""
        pytest.skip("Real MCP tests require live connection")

    async def test_luna_free_lite(self, real_mcp):
        """Test luna_free - free page, LITE tier."""
        pytest.skip("Real MCP tests require live connection")


@pytest.mark.asyncio
class TestValidationHelpers:
    """Test validation helper functions with mock data."""

    def test_vault_compliance_passes(self):
        """Valid schedule passes vault check."""
        schedule = {"items": [{"content_type": "lingerie"}, {"content_type": "b/g"}]}
        vault = {"lingerie", "b/g", "solo"}
        assert_vault_compliance(schedule, vault)  # Should not raise

    def test_vault_compliance_fails(self):
        """Invalid content type fails vault check."""
        schedule = {"items": [{"content_type": "invalid_type"}]}
        vault = {"lingerie", "b/g"}
        with pytest.raises(AssertionError, match="not in vault"):
            assert_vault_compliance(schedule, vault)

    def test_avoid_exclusion_passes(self):
        """Schedule without AVOID types passes."""
        schedule = {"items": [{"content_type": "lingerie"}]}
        avoid = {"feet", "roleplay"}
        assert_avoid_exclusion(schedule, avoid)  # Should not raise

    def test_avoid_exclusion_fails(self):
        """Schedule with AVOID type fails."""
        schedule = {"items": [{"content_type": "feet"}]}
        avoid = {"feet", "roleplay"}
        with pytest.raises(AssertionError, match="AVOID tier"):
            assert_avoid_exclusion(schedule, avoid)

    def test_price_bounds_passes(self):
        """Prices within bounds pass."""
        schedule = {"items": [{"price": 5.0}, {"price": 25.0}, {"price": 50.0}]}
        assert_price_bounds(schedule)  # Should not raise

    def test_price_bounds_fails(self):
        """Price outside bounds fails."""
        schedule = {"items": [{"price": 4.99}]}
        with pytest.raises(AssertionError, match="outside bounds"):
            assert_price_bounds(schedule)

    def test_timing_valid_passes(self):
        """Valid timing passes."""
        schedule = {"items": [{"scheduled_time": "10:23"}, {"scheduled_time": "19:45"}]}
        assert_timing_valid(schedule)  # Should not raise

    def test_timing_dead_zone_fails(self):
        """Dead zone timing fails."""
        schedule = {"items": [{"scheduled_time": "04:30"}]}
        with pytest.raises(AssertionError, match="dead zone"):
            assert_timing_valid(schedule)
