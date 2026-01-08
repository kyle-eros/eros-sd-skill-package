"""Tests for optimized get_creator_profile MCP tool.

Tests the bundled response structure, 3-level MM revenue fallback,
creator validation, and backward compatibility.
"""
import pytest
import sys
from pathlib import Path

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp_server.main import (
    get_creator_profile,
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
            assert metadata["mcp_calls_saved"] == 3  # analytics + volume + rankings


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
