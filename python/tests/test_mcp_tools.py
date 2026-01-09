"""Tests for optimized get_creator_profile MCP tool.

Tests the bundled response structure, 3-level MM revenue fallback,
creator validation, and backward compatibility.
"""
import pytest
import sys
from pathlib import Path

# Add mcp_server to path for both package import and internal module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))

from mcp_server.main import (
    get_creator_profile,
    get_active_creators,
    get_content_type_rankings,
    validate_creator_id,
    resolve_creator_id,
    get_mm_revenue_with_fallback
)


class TestValidateCreatorId:
    """Tests for validate_creator_id helper."""

    def test_valid_creator_id(self):
        """Test valid creator_id passes validation."""
        is_valid, result = validate_creator_id("maya_hill")
        assert is_valid is True
        assert result == "maya_hill"

    def test_valid_with_hyphen(self):
        """Test creator_id with hyphen is valid."""
        is_valid, result = validate_creator_id("jade-lee")
        assert is_valid is True
        assert result == "jade-lee"

    def test_empty_creator_id(self):
        """Test empty creator_id fails validation."""
        is_valid, result = validate_creator_id("")
        assert is_valid is False
        assert "empty" in result.lower()

    def test_none_creator_id(self):
        """Test None creator_id fails validation."""
        is_valid, result = validate_creator_id(None)
        assert is_valid is False

    def test_too_short(self):
        """Test single-char creator_id fails."""
        is_valid, result = validate_creator_id("a")
        assert is_valid is False
        assert "length" in result.lower()

    def test_invalid_characters(self):
        """Test creator_id with special chars fails."""
        is_valid, result = validate_creator_id("maya@hill")
        assert is_valid is False
        assert "invalid" in result.lower()

    def test_strips_whitespace(self):
        """Test whitespace is stripped."""
        is_valid, result = validate_creator_id("  maya_hill  ")
        assert is_valid is True
        assert result == "maya_hill"


class TestResolveCreatorId:
    """Tests for resolve_creator_id helper."""

    def test_returns_found_structure(self):
        """Test returns dict with found key."""
        result = resolve_creator_id("nonexistent_creator_12345")
        assert "found" in result
        assert isinstance(result["found"], bool)

    def test_invalid_format_returns_error(self):
        """Test invalid format returns error."""
        result = resolve_creator_id("")
        assert result["found"] is False
        assert "error" in result


class TestGetMmRevenueWithFallback:
    """Tests for 3-level MM revenue fallback."""

    def test_returns_required_fields(self):
        """Test all required fields present in response."""
        result = get_mm_revenue_with_fallback("test_creator")
        required_fields = [
            "mm_revenue_30d",
            "mm_revenue_confidence",
            "mm_revenue_source",
            "mm_data_age_days",
            "mm_message_count_30d"
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_confidence_is_valid_value(self):
        """Test confidence is one of expected values."""
        result = get_mm_revenue_with_fallback("test_creator")
        valid_confidences = ["high", "medium", "low", "error"]
        assert result["mm_revenue_confidence"] in valid_confidences

    def test_revenue_is_numeric(self):
        """Test revenue is a number."""
        result = get_mm_revenue_with_fallback("test_creator")
        assert isinstance(result["mm_revenue_30d"], (int, float))


class TestGetCreatorProfileOptimized:
    """Tests for optimized get_creator_profile bundled response."""

    def test_creator_not_found(self):
        """Test response for nonexistent creator."""
        result = get_creator_profile("nonexistent_creator_xyz_99999")
        assert result.get("found") is False
        assert "error" in result

    def test_invalid_creator_id(self):
        """Test invalid creator_id returns error."""
        result = get_creator_profile("")
        assert result.get("found") is False
        assert "error" in result

    def test_bundled_response_has_metadata(self):
        """Test bundled response includes metadata section."""
        # Use a real creator from the database
        result = get_creator_profile("maya_hill")
        if result.get("found"):
            assert "metadata" in result
            assert "fetched_at" in result["metadata"]
            assert "data_sources_used" in result["metadata"]

    def test_include_analytics_flag(self):
        """Test include_analytics=True includes analytics_summary."""
        result = get_creator_profile("maya_hill", include_analytics=True)
        if result.get("found"):
            assert "analytics_summary" in result
            assert "mm_revenue_30d" in result.get("analytics_summary", {})
            assert "mm_revenue_confidence" in result.get("analytics_summary", {})

    def test_include_volume_flag(self):
        """Test include_volume=True includes volume_assignment."""
        result = get_creator_profile("maya_hill", include_volume=True)
        if result.get("found"):
            assert "volume_assignment" in result
            assert "volume_level" in result.get("volume_assignment", {})

    def test_include_content_rankings_flag(self):
        """Test include_content_rankings=True includes rankings."""
        result = get_creator_profile("maya_hill", include_content_rankings=True)
        if result.get("found"):
            assert "top_content_types" in result
            assert isinstance(result["top_content_types"], list)
            assert "avoid_types" in result
            assert "top_types" in result

    def test_all_flags_disabled(self):
        """Test minimal response with all flags disabled."""
        result = get_creator_profile(
            "maya_hill",
            include_analytics=False,
            include_volume=False,
            include_content_rankings=False
        )
        if result.get("found"):
            assert "creator" in result
            # Optional sections should not be present
            assert "analytics_summary" not in result
            assert "volume_assignment" not in result
            assert "top_content_types" not in result

    def test_creator_section_structure(self):
        """Test creator section has expected fields."""
        result = get_creator_profile("maya_hill")
        if result.get("found"):
            creator = result.get("creator", {})
            expected_fields = [
                "creator_id", "page_name", "page_type",
                "current_fan_count", "is_active"
            ]
            for field in expected_fields:
                assert field in creator, f"Missing creator field: {field}"

    def test_mcp_calls_saved_metric(self):
        """Test metadata tracks MCP calls saved."""
        result = get_creator_profile(
            "maya_hill",
            include_analytics=True,
            include_volume=True,
            include_content_rankings=True
        )
        if result.get("found"):
            metadata = result.get("metadata", {})
            assert "mcp_calls_saved" in metadata
            assert metadata["mcp_calls_saved"] == 5  # analytics + volume + rankings + vault + persona


class TestBackwardCompatibility:
    """Tests ensuring backward compatibility."""

    def test_old_style_call(self):
        """Test old-style call (just creator_id) still works."""
        result = get_creator_profile("maya_hill")
        # Should not raise, should return valid response
        assert "found" in result

    def test_include_analytics_false_compatible(self):
        """Test explicit include_analytics=False still works."""
        result = get_creator_profile("maya_hill", include_analytics=False)
        assert "found" in result


class TestGetActiveCreatorsOptimized:
    """Tests for optimized get_active_creators with pagination and filters."""

    def test_basic_call_returns_expected_structure(self):
        """Verify response contains all expected fields."""
        result = get_active_creators(limit=5)

        assert "creators" in result
        assert "count" in result
        assert "total_count" in result
        assert "limit" in result
        assert "offset" in result
        assert "metadata" in result
        assert result["limit"] == 5
        assert result["offset"] == 0

    def test_metadata_structure(self):
        """Verify metadata contains expected fields."""
        result = get_active_creators(limit=5)
        metadata = result.get("metadata", {})

        assert "fetched_at" in metadata
        assert "sort" in metadata
        assert "has_more" in metadata
        assert "page_info" in metadata
        assert metadata["sort"]["by"] == "revenue"
        assert metadata["sort"]["order"] == "desc"

    def test_pagination_offset(self):
        """Verify offset pagination works correctly."""
        # Get first page
        page1 = get_active_creators(limit=5, offset=0)
        # Get second page
        page2 = get_active_creators(limit=5, offset=5)

        # Verify different results (if enough data)
        if page1["total_count"] > 5:
            page1_ids = {c["creator_id"] for c in page1["creators"]}
            page2_ids = {c["creator_id"] for c in page2["creators"]}
            assert page1_ids != page2_ids, "Pagination should return different creators"

    def test_tier_filter_valid(self):
        """Verify valid tier filter works."""
        result = get_active_creators(tier="High", limit=100)

        assert "error" not in result
        # All returned creators should have High tier (or None if LEFT JOIN)
        for creator in result["creators"]:
            assert creator.get("volume_tier") == "High"

    def test_tier_filter_invalid_returns_error(self):
        """Verify invalid tier returns validation error."""
        result = get_active_creators(tier="INVALID_TIER", limit=5)

        assert "error" in result
        assert "Invalid tier" in result["error"]
        assert result["count"] == 0

    def test_page_type_filter_valid(self):
        """Verify page_type filter works."""
        result = get_active_creators(page_type="paid", limit=100)

        assert "error" not in result
        for creator in result["creators"]:
            assert creator.get("page_type") == "paid"

    def test_page_type_filter_invalid_returns_error(self):
        """Verify invalid page_type returns validation error."""
        result = get_active_creators(page_type="premium", limit=5)

        assert "error" in result
        assert "Invalid page_type" in result["error"]

    def test_revenue_range_filter(self):
        """Verify min/max revenue filters work."""
        result = get_active_creators(min_revenue=1000, max_revenue=5000, limit=100)

        assert "error" not in result
        for creator in result["creators"]:
            revenue = creator.get("mm_revenue_monthly", 0) or 0
            assert revenue >= 1000, f"Revenue {revenue} below min 1000"
            assert revenue <= 5000, f"Revenue {revenue} above max 5000"

    def test_sort_by_fan_count_desc(self):
        """Verify sorting by fan_count descending."""
        result = get_active_creators(sort_by="fan_count", sort_order="desc", limit=10)

        assert "error" not in result
        fan_counts = [c.get("current_fan_count", 0) or 0 for c in result["creators"]]
        assert fan_counts == sorted(fan_counts, reverse=True), "Should be sorted descending"

    def test_sort_by_name_asc(self):
        """Verify sorting by name ascending."""
        result = get_active_creators(sort_by="name", sort_order="asc", limit=10)

        assert "error" not in result
        names = [c.get("page_name", "") for c in result["creators"]]
        assert names == sorted(names), "Should be sorted alphabetically"

    def test_include_volume_details_false(self):
        """Verify volume_details not included when flag is False."""
        result = get_active_creators(include_volume_details=False, limit=5)

        for creator in result["creators"]:
            assert "volume_details" not in creator

    def test_include_volume_details_true(self):
        """Verify volume_details included when flag is True."""
        result = get_active_creators(include_volume_details=True, limit=20)

        # At least one creator with volume assignment should have details
        creators_with_tier = [c for c in result["creators"] if c.get("volume_tier")]
        if creators_with_tier:
            for creator in creators_with_tier:
                assert "volume_details" in creator
                assert "ppv_per_day" in creator["volume_details"]

    def test_limit_clamping_max(self):
        """Verify limit is clamped to 500 max."""
        result = get_active_creators(limit=1000)

        assert result["limit"] == 500

    def test_limit_clamping_min(self):
        """Verify limit is clamped to 1 min."""
        result = get_active_creators(limit=-5)

        assert result["limit"] == 1

    def test_has_more_pagination_flag(self):
        """Verify has_more is True when more results exist."""
        result = get_active_creators(limit=1)

        if result["total_count"] > 1:
            assert result["metadata"]["has_more"] is True
        else:
            assert result["metadata"]["has_more"] is False

    def test_combined_filters(self):
        """Verify multiple filters work together."""
        result = get_active_creators(
            tier="Mid",
            page_type="paid",
            min_revenue=500,
            sort_by="fan_count",
            sort_order="desc",
            limit=50
        )

        assert "error" not in result
        # Verify filters applied in metadata
        filters = result["metadata"].get("filters_applied", {})
        assert filters.get("tier") == "Mid"
        assert filters.get("page_type") == "paid"
        assert filters.get("min_revenue") == 500

    def test_backward_compatibility_default_params(self):
        """Verify default params match original behavior."""
        # Call with no params (like original implementation)
        result = get_active_creators()

        assert result["limit"] == 100
        assert result["offset"] == 0
        assert result["metadata"]["sort"]["by"] == "revenue"
        assert result["metadata"]["sort"]["order"] == "desc"

    def test_creator_fields_comprehensive(self):
        """Verify all expected creator fields are present."""
        result = get_active_creators(limit=1)

        if result["creators"]:
            creator = result["creators"][0]
            expected_fields = [
                "creator_id", "page_name", "page_type",
                "current_fan_count", "mm_revenue_monthly", "volume_tier"
            ]
            for field in expected_fields:
                assert field in creator, f"Missing field: {field}"

    def test_error_response_structure(self):
        """Verify error response maintains expected structure."""
        # Force an error with invalid tier
        result = get_active_creators(tier="BAD_TIER")

        assert "error" in result
        assert "creators" in result
        assert "count" in result
        assert "metadata" in result
        assert result["creators"] == []
        assert result["count"] == 0


class TestGetContentTypeRankings:
    """Tests for get_content_type_rankings MCP tool."""

    def test_basic_call_returns_expected_structure(self):
        """Verify response contains all expected fields."""
        result = get_content_type_rankings("grace_bennett")

        assert "rankings" in result or "error" in result
        if "error" not in result:
            assert "avoid_types" in result
            assert "top_types" in result
            assert "total_types" in result
            assert "metadata" in result

    def test_metadata_structure(self):
        """Verify metadata contains expected fields."""
        result = get_content_type_rankings("grace_bennett")

        if "error" not in result:
            metadata = result.get("metadata", {})
            assert "fetched_at" in metadata
            assert "rankings_hash" in metadata
            assert "avoid_types_hash" in metadata
            assert "creator_resolved" in metadata
            assert "analysis_date" in metadata
            assert "data_age_days" in metadata
            assert "is_stale" in metadata

    def test_include_metrics_true(self):
        """Verify metrics included by default."""
        result = get_content_type_rankings("grace_bennett", include_metrics=True)

        if "error" not in result and result.get("rankings"):
            ranking = result["rankings"][0]
            assert "rps" in ranking
            assert "conversion_rate" in ranking
            assert "sends_last_30d" in ranking

    def test_include_metrics_false(self):
        """Verify lightweight response without metrics."""
        result = get_content_type_rankings("grace_bennett", include_metrics=False)

        if "error" not in result and result.get("rankings"):
            ranking = result["rankings"][0]
            assert "type_name" in ranking
            assert "performance_tier" in ranking
            # Metrics should NOT be present
            assert "rps" not in ranking

    def test_avoid_types_hash_consistency(self):
        """Verify avoid_types_hash is consistent for same data."""
        result1 = get_content_type_rankings("grace_bennett")
        result2 = get_content_type_rankings("grace_bennett")

        if "error" not in result1 and "error" not in result2:
            hash1 = result1.get("metadata", {}).get("avoid_types_hash")
            hash2 = result2.get("metadata", {}).get("avoid_types_hash")
            assert hash1 == hash2, "Hash should be deterministic"

    def test_creator_not_found(self):
        """Verify error response for invalid creator."""
        result = get_content_type_rankings("nonexistent_creator_xyz")

        assert "error" in result
        assert result["rankings"] == []
        assert result["avoid_types"] == []
        assert result["total_types"] == 0

    def test_analysis_date_filter_applied(self):
        """Verify only latest analysis data is returned."""
        # This test verifies the critical bug fix
        result = get_content_type_rankings("grace_bennett")

        if "error" not in result:
            # All rankings should have same analysis_date (if present)
            analysis_date = result.get("metadata", {}).get("analysis_date")
            # The presence of analysis_date in metadata indicates fix is applied
            assert analysis_date is not None or result["total_types"] == 0


class TestGetCreatorProfilePersonaBundling:
    """Tests for persona bundling in get_creator_profile."""

    def test_include_persona_flag(self):
        """Test include_persona=True includes persona section."""
        result = get_creator_profile("maya_hill", include_persona=True)
        if result.get("found"):
            assert "persona" in result
            persona = result.get("persona", {})
            # Check required persona fields
            assert "primary_tone" in persona
            assert "_default" in persona

    def test_exclude_persona_flag(self):
        """Test include_persona=False excludes persona section."""
        result = get_creator_profile("maya_hill", include_persona=False)
        if result.get("found"):
            assert "persona" not in result

    def test_persona_default_fallback(self):
        """Test persona returns default values for creator without persona record."""
        # Use a creator that might not have a persona configured
        result = get_creator_profile("maya_hill", include_persona=True)
        if result.get("found") and result.get("persona"):
            persona = result["persona"]
            # Should have _default flag
            assert "_default" in persona
            # If default, verify expected default values
            if persona.get("_default"):
                assert persona["primary_tone"] == "playful"
                assert persona["emoji_frequency"] == "moderate"
                assert persona["slang_level"] == "light"

    def test_persona_valid_tone_values(self):
        """Test persona has valid tone values."""
        result = get_creator_profile("maya_hill", include_persona=True)
        if result.get("found") and result.get("persona"):
            persona = result["persona"]
            valid_tones = ("playful", "aggressive", "seductive", "sultry")
            if persona.get("primary_tone"):
                assert persona["primary_tone"] in valid_tones

    def test_persona_valid_emoji_frequency(self):
        """Test persona has valid emoji_frequency values."""
        result = get_creator_profile("maya_hill", include_persona=True)
        if result.get("found") and result.get("persona"):
            persona = result["persona"]
            valid_freq = ("heavy", "moderate", "light", "none")
            if persona.get("emoji_frequency"):
                assert persona["emoji_frequency"] in valid_freq

    def test_persona_valid_slang_level(self):
        """Test persona has valid slang_level values."""
        result = get_creator_profile("maya_hill", include_persona=True)
        if result.get("found") and result.get("persona"):
            persona = result["persona"]
            valid_slang = ("none", "light", "heavy")
            if persona.get("slang_level"):
                assert persona["slang_level"] in valid_slang

    def test_metadata_includes_persona_flag(self):
        """Test metadata includes persona in include_flags."""
        result = get_creator_profile("maya_hill", include_persona=True)
        if result.get("found"):
            metadata = result.get("metadata", {})
            include_flags = metadata.get("include_flags", {})
            assert "persona" in include_flags
            assert include_flags["persona"] is True

    def test_mcp_calls_saved_with_persona(self):
        """Test mcp_calls_saved includes persona bundling."""
        result = get_creator_profile(
            "maya_hill",
            include_analytics=True,
            include_volume=True,
            include_content_rankings=True,
            include_vault=True,
            include_persona=True
        )
        if result.get("found"):
            metadata = result.get("metadata", {})
            # Should be 5 with persona included
            assert metadata.get("mcp_calls_saved") == 5


class TestGetCreatorProfilePersonaBundlingMock:
    """Tests for persona bundling using MockMCPClient."""

    @pytest.mark.asyncio
    async def test_mock_get_creator_profile_includes_persona(self):
        """Verify bundled response includes persona when requested."""
        from .mocks import MockMCPClient, TestDataFactory

        mcp = MockMCPClient(TestDataFactory.STANDARD)

        # With persona (default)
        result = await mcp.get_creator_profile("test_creator")
        assert "persona" in result
        assert result["persona"]["primary_tone"] in ("playful", "aggressive", "seductive", "sultry")
        assert result["persona"]["emoji_frequency"] in ("heavy", "moderate", "light", "none")
        assert result["persona"]["slang_level"] in ("none", "light", "heavy")
        assert "_default" in result["persona"]

    @pytest.mark.asyncio
    async def test_mock_get_creator_profile_excludes_persona_when_disabled(self):
        """Verify persona excluded when include_persona=False."""
        from .mocks import MockMCPClient, TestDataFactory

        mcp = MockMCPClient(TestDataFactory.STANDARD)

        result = await mcp.get_creator_profile("test_creator", include_persona=False)
        assert "persona" not in result

    @pytest.mark.asyncio
    async def test_mock_get_creator_profile_persona_uses_config(self):
        """Verify persona values come from CreatorConfig."""
        from .mocks import MockMCPClient, CreatorConfig

        config = CreatorConfig(
            persona_tone="aggressive",
            emoji_frequency="heavy",
            slang_level="none"
        )
        mcp = MockMCPClient(config)

        result = await mcp.get_creator_profile("test_creator")
        assert result["persona"]["primary_tone"] == "aggressive"
        assert result["persona"]["emoji_frequency"] == "heavy"
        assert result["persona"]["slang_level"] == "none"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
