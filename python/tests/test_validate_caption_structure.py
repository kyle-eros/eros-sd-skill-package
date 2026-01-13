"""Tests for validate_caption_structure MCP tool v2.0.0.

Test Categories:
- Input Validation (5 tests): Empty, null, too long, send_type validation
- Error Responses (4 tests): Error schema, error codes, valid_send_types
- Send Type Validation (4 tests): Cache load, cache hit, all types, invalid type
- Category Rules (6 tests): Revenue/engagement/retention thresholds, spam tolerance
- Scoring (4 tests): Length, spam, emoji, repetition penalties
- Metadata (3 tests): Fields present, timing, version
- Integration (2 tests): Full valid, full invalid

Total: 28 tests
Target: 90% line coverage, 85% branch coverage
"""

import pytest
import sys
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add project root to path for imports
sys.path.insert(0, '/Users/kylemerriman/Developer/eros-sd-skill-package')


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db_query():
    """Mock db_query to return controlled test data."""
    with patch('mcp_server.main.db_query') as mock:
        mock.return_value = [
            {"send_type_key": "ppv_unlock", "category": "revenue", "page_type_restriction": "both"},
            {"send_type_key": "bump_normal", "category": "engagement", "page_type_restriction": "both"},
            {"send_type_key": "renew_on_post", "category": "retention", "page_type_restriction": "paid"},
        ]
        yield mock


@pytest.fixture
def clear_cache():
    """Clear send_types cache before each test."""
    import mcp_server.main as main
    main._SEND_TYPES_CACHE = {}
    yield
    main._SEND_TYPES_CACHE = {}


@pytest.fixture
def full_send_types_mock():
    """Full mock of all 22 send_types for comprehensive testing."""
    return [
        # Revenue (9)
        {"send_type_key": "ppv_unlock", "category": "revenue", "page_type_restriction": "both"},
        {"send_type_key": "ppv_wall", "category": "revenue", "page_type_restriction": "free"},
        {"send_type_key": "tip_goal", "category": "revenue", "page_type_restriction": "paid"},
        {"send_type_key": "bundle", "category": "revenue", "page_type_restriction": "both"},
        {"send_type_key": "flash_bundle", "category": "revenue", "page_type_restriction": "both"},
        {"send_type_key": "vip_program", "category": "revenue", "page_type_restriction": "both"},
        {"send_type_key": "game_post", "category": "revenue", "page_type_restriction": "both"},
        {"send_type_key": "snapchat_bundle", "category": "revenue", "page_type_restriction": "both"},
        {"send_type_key": "first_to_tip", "category": "revenue", "page_type_restriction": "both"},
        # Engagement (9)
        {"send_type_key": "link_drop", "category": "engagement", "page_type_restriction": "both"},
        {"send_type_key": "wall_link_drop", "category": "engagement", "page_type_restriction": "both"},
        {"send_type_key": "bump_normal", "category": "engagement", "page_type_restriction": "both"},
        {"send_type_key": "bump_descriptive", "category": "engagement", "page_type_restriction": "both"},
        {"send_type_key": "bump_text_only", "category": "engagement", "page_type_restriction": "both"},
        {"send_type_key": "bump_flyer", "category": "engagement", "page_type_restriction": "both"},
        {"send_type_key": "dm_farm", "category": "engagement", "page_type_restriction": "both"},
        {"send_type_key": "like_farm", "category": "engagement", "page_type_restriction": "both"},
        {"send_type_key": "live_promo", "category": "engagement", "page_type_restriction": "both"},
        # Retention (4)
        {"send_type_key": "renew_on_post", "category": "retention", "page_type_restriction": "paid"},
        {"send_type_key": "renew_on_message", "category": "retention", "page_type_restriction": "paid"},
        {"send_type_key": "ppv_followup", "category": "retention", "page_type_restriction": "both"},
        {"send_type_key": "expired_winback", "category": "retention", "page_type_restriction": "paid"},
    ]


# =============================================================================
# INPUT VALIDATION TESTS (5)
# =============================================================================

class TestInputValidation:
    """Test input validation and error handling."""

    def test_empty_caption_returns_error(self, clear_cache, mock_db_query):
        """Empty string caption returns EMPTY_CAPTION error."""
        from mcp_server.main import validate_caption_structure
        result = validate_caption_structure("", "ppv_unlock")

        assert result["error_code"] == "EMPTY_CAPTION"
        assert result["valid"] is False
        assert result["score"] is None
        assert result["error"] == "Caption text is required"

    def test_whitespace_only_caption_returns_error(self, clear_cache, mock_db_query):
        """Whitespace-only caption returns EMPTY_CAPTION error."""
        from mcp_server.main import validate_caption_structure
        result = validate_caption_structure("   \n\t  ", "ppv_unlock")

        assert result["error_code"] == "EMPTY_CAPTION"
        assert result["valid"] is False

    def test_caption_exceeds_limit_returns_error(self, clear_cache, mock_db_query):
        """Caption over 2000 chars returns CAPTION_EXCEEDS_LIMIT error."""
        from mcp_server.main import validate_caption_structure
        long_caption = "x" * 2001
        result = validate_caption_structure(long_caption, "ppv_unlock")

        assert result["error_code"] == "CAPTION_EXCEEDS_LIMIT"
        assert result["valid"] is False
        assert "2000" in result["error"]

    def test_caption_at_limit_is_valid(self, clear_cache, mock_db_query):
        """Caption exactly at 2000 chars is valid (not error)."""
        from mcp_server.main import validate_caption_structure
        max_caption = "x" * 2000
        result = validate_caption_structure(max_caption, "ppv_unlock")

        assert "error_code" not in result
        assert result["valid"] is True or result["valid"] is False  # Has score
        assert result["score"] is not None

    def test_valid_caption_passes_input_validation(self, clear_cache, mock_db_query):
        """Valid caption and send_type passes input validation."""
        from mcp_server.main import validate_caption_structure
        result = validate_caption_structure(
            "Hey babe, I just posted something special for you today! Check it out 😘",
            "ppv_unlock"
        )

        assert "error_code" not in result
        assert result["score"] is not None


# =============================================================================
# ERROR RESPONSE TESTS (4)
# =============================================================================

class TestErrorResponses:
    """Test error response schema and content."""

    def test_error_response_has_all_fields(self, clear_cache, mock_db_query):
        """Error responses include all required schema fields."""
        from mcp_server.main import validate_caption_structure
        result = validate_caption_structure("", "ppv_unlock")

        # Required error fields
        assert "error" in result
        assert "error_code" in result

        # Required common fields (set to null/default on error)
        assert "valid" in result
        assert result["valid"] is False
        assert "score" in result
        assert result["score"] is None
        assert "send_type" in result
        assert "category" in result
        assert "caption_length" in result
        assert "issues" in result
        assert "recommendation" in result
        assert "thresholds_applied" in result
        assert "metadata" in result

    def test_error_metadata_has_error_flag(self, clear_cache, mock_db_query):
        """Error responses have metadata.error = True."""
        from mcp_server.main import validate_caption_structure
        result = validate_caption_structure("", "ppv_unlock")

        assert result["metadata"]["error"] is True
        assert result["metadata"]["tool_version"] == "2.0.0"

    def test_invalid_send_type_returns_error(self, clear_cache, mock_db_query):
        """Invalid send_type returns INVALID_SEND_TYPE error."""
        from mcp_server.main import validate_caption_structure
        result = validate_caption_structure("Test caption", "not_a_real_type")

        assert result["error_code"] == "INVALID_SEND_TYPE"
        assert result["valid"] is False
        assert "not_a_real_type" in result["error"]

    def test_invalid_send_type_includes_valid_types(self, clear_cache, mock_db_query):
        """INVALID_SEND_TYPE error includes list of valid types."""
        from mcp_server.main import validate_caption_structure
        result = validate_caption_structure("Test caption", "not_a_real_type")

        assert "valid_send_types" in result
        assert isinstance(result["valid_send_types"], list)
        assert len(result["valid_send_types"]) > 0
        assert "ppv_unlock" in result["valid_send_types"]


# =============================================================================
# SEND TYPE VALIDATION TESTS (4)
# =============================================================================

class TestSendTypeValidation:
    """Test send_type validation and caching."""

    def test_cache_loads_on_first_call(self, clear_cache, mock_db_query):
        """Send types cache loads from database on first call."""
        from mcp_server.main import validate_caption_structure, _SEND_TYPES_CACHE

        # Cache should be empty initially
        assert len(_SEND_TYPES_CACHE) == 0

        validate_caption_structure("Test caption", "ppv_unlock")

        # After first call, cache should be populated
        from mcp_server.main import _SEND_TYPES_CACHE as cache_after
        assert len(cache_after) > 0
        assert mock_db_query.called

    def test_cache_hit_on_second_call(self, clear_cache, mock_db_query):
        """Second call uses cached data (no additional DB query)."""
        from mcp_server.main import validate_caption_structure

        # First call populates cache
        validate_caption_structure("Test caption 1", "ppv_unlock")
        call_count_after_first = mock_db_query.call_count

        # Second call should use cache
        validate_caption_structure("Test caption 2", "ppv_unlock")
        call_count_after_second = mock_db_query.call_count

        # No additional DB call
        assert call_count_after_second == call_count_after_first

    def test_all_22_send_types_valid(self, clear_cache, full_send_types_mock):
        """All 22 send_types are recognized as valid."""
        from mcp_server.main import validate_caption_structure

        with patch('mcp_server.main.db_query', return_value=full_send_types_mock):
            for send_type_row in full_send_types_mock:
                send_type = send_type_row["send_type_key"]
                result = validate_caption_structure("Test caption for validation", send_type)

                assert "error_code" not in result, f"send_type '{send_type}' returned error"
                assert result["category"] == send_type_row["category"]

    def test_cache_hit_field_in_metadata(self, clear_cache, mock_db_query):
        """Metadata includes cache_hit field."""
        from mcp_server.main import validate_caption_structure

        # First call - cache miss
        result1 = validate_caption_structure("Test caption", "ppv_unlock")
        assert result1["metadata"]["cache_hit"] is False

        # Second call - cache hit
        result2 = validate_caption_structure("Test caption", "ppv_unlock")
        assert result2["metadata"]["cache_hit"] is True


# =============================================================================
# CATEGORY RULES TESTS (6)
# =============================================================================

class TestCategoryRules:
    """Test category-aware validation rules."""

    def test_revenue_category_has_higher_min_length(self, clear_cache, mock_db_query):
        """Revenue category requires longer minimum captions."""
        from mcp_server.main import validate_caption_structure

        # 30 chars - below revenue min (40) but above engagement min (15)
        short_caption = "Check out my new content now!"  # 29 chars
        result = validate_caption_structure(short_caption, "ppv_unlock")

        assert result["category"] == "revenue"
        assert result["thresholds_applied"]["min"] == 40
        assert any("too short" in issue.lower() for issue in result["issues"])

    def test_engagement_category_has_lower_min_length(self, clear_cache, mock_db_query):
        """Engagement category allows shorter captions."""
        from mcp_server.main import validate_caption_structure

        # 20 chars - above engagement min (15)
        short_caption = "Hey check this out!"  # 19 chars
        result = validate_caption_structure(short_caption, "bump_normal")

        assert result["category"] == "engagement"
        assert result["thresholds_applied"]["min"] == 15
        # Should NOT have "too short" issue if above min
        assert not any("too short" in issue.lower() for issue in result["issues"])

    def test_retention_category_thresholds(self, clear_cache, mock_db_query):
        """Retention category has intermediate thresholds."""
        from mcp_server.main import validate_caption_structure

        result = validate_caption_structure(
            "Hey! Just wanted to remind you that your subscription is up for renewal.",
            "renew_on_post"
        )

        assert result["category"] == "retention"
        assert result["thresholds_applied"]["min"] == 25
        assert result["thresholds_applied"]["ideal_min"] == 50

    def test_revenue_tolerates_sales_language(self, clear_cache, mock_db_query):
        """Revenue category tolerates 'limited time' (sales language)."""
        from mcp_server.main import validate_caption_structure

        caption_with_sales = "Limited time offer! Check out my exclusive new content before it's gone!"
        result = validate_caption_structure(caption_with_sales, "ppv_unlock")

        assert result["category"] == "revenue"
        # "limited time" should NOT be penalized for revenue
        assert not any("limited time" in issue.lower() for issue in result["issues"])

    def test_engagement_penalizes_sales_language(self, clear_cache, mock_db_query):
        """Engagement category penalizes 'limited time' (sales language)."""
        from mcp_server.main import validate_caption_structure

        caption_with_sales = "Limited time offer! Check out my exclusive new content before it's gone!"
        result = validate_caption_structure(caption_with_sales, "bump_normal")

        assert result["category"] == "engagement"
        # "limited time" SHOULD be penalized for engagement
        assert any("limited time" in issue.lower() for issue in result["issues"])

    def test_thresholds_applied_in_response(self, clear_cache, mock_db_query):
        """Response includes thresholds_applied dict."""
        from mcp_server.main import validate_caption_structure

        result = validate_caption_structure("Test caption for threshold check", "ppv_unlock")

        assert "thresholds_applied" in result
        assert "min" in result["thresholds_applied"]
        assert "ideal_min" in result["thresholds_applied"]
        assert "ideal_max" in result["thresholds_applied"]
        assert "max" in result["thresholds_applied"]


# =============================================================================
# SCORING TESTS (4)
# =============================================================================

class TestScoring:
    """Test scoring penalties."""

    def test_length_penalty_for_short_caption(self, clear_cache, mock_db_query):
        """Too-short caption gets 30 point penalty."""
        from mcp_server.main import validate_caption_structure

        # Engagement has min=15, so 10 char caption is too short
        result = validate_caption_structure("Short msg!", "bump_normal")  # 10 chars

        assert result["score"] < 100
        assert any("too short" in issue.lower() for issue in result["issues"])

    def test_spam_pattern_penalty(self, clear_cache, mock_db_query):
        """Spam patterns reduce score."""
        from mcp_server.main import validate_caption_structure

        # "click here" is a universal spam pattern (-15)
        caption = "Click here to see my new content! It's amazing and you'll love it!"
        result = validate_caption_structure(caption, "bump_normal")

        assert result["score"] < 100
        assert any("click here" in issue.lower() for issue in result["issues"])

    def test_emoji_penalty_excessive(self, clear_cache, mock_db_query):
        """More than 10 emojis gets 15 point penalty."""
        from mcp_server.main import validate_caption_structure

        emoji_heavy = "Check this out! 💕💕💕💕💕💕💕💕💕💕💕"  # 11 emojis
        result = validate_caption_structure(emoji_heavy, "bump_normal")

        assert any("excessive emojis" in issue.lower() for issue in result["issues"])

    def test_repetition_penalty(self, clear_cache, mock_db_query):
        """Repeated words get 10 point penalty."""
        from mcp_server.main import validate_caption_structure

        repetitive = "Amazing amazing amazing content for you to enjoy today!"
        result = validate_caption_structure(repetitive, "bump_normal")

        assert any("repeated words" in issue.lower() for issue in result["issues"])


# =============================================================================
# METADATA TESTS (3)
# =============================================================================

class TestMetadata:
    """Test metadata block."""

    def test_metadata_has_all_fields(self, clear_cache, mock_db_query):
        """Success response metadata has all required fields."""
        from mcp_server.main import validate_caption_structure

        result = validate_caption_structure(
            "Test caption for metadata verification",
            "ppv_unlock"
        )

        assert "metadata" in result
        assert "fetched_at" in result["metadata"]
        assert "tool_version" in result["metadata"]
        assert "query_ms" in result["metadata"]
        assert "cache_hit" in result["metadata"]

    def test_metadata_version_is_2_0_0(self, clear_cache, mock_db_query):
        """Tool version is 2.0.0."""
        from mcp_server.main import validate_caption_structure

        result = validate_caption_structure("Test caption", "ppv_unlock")

        assert result["metadata"]["tool_version"] == "2.0.0"

    def test_metadata_query_ms_is_numeric(self, clear_cache, mock_db_query):
        """query_ms is a numeric value."""
        from mcp_server.main import validate_caption_structure

        result = validate_caption_structure("Test caption", "ppv_unlock")

        assert isinstance(result["metadata"]["query_ms"], (int, float))
        assert result["metadata"]["query_ms"] >= 0


# =============================================================================
# INTEGRATION TESTS (2)
# =============================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_valid_caption_flow(self, clear_cache, mock_db_query):
        """Complete flow for a valid, high-quality caption."""
        from mcp_server.main import validate_caption_structure

        high_quality_caption = (
            "Hey babe! I just posted something really special for you today. "
            "You're going to love what I've been working on - it's my best content yet. "
            "Can't wait to hear what you think! 😘"
        )

        result = validate_caption_structure(high_quality_caption, "ppv_unlock")

        # Should pass with high score
        assert result["valid"] is True
        assert result["score"] >= 85
        assert result["recommendation"] == "PASS"
        assert result["category"] == "revenue"
        assert len(result["issues"]) == 0
        assert result["metadata"]["tool_version"] == "2.0.0"

    def test_full_problematic_caption_flow(self, clear_cache, mock_db_query):
        """Complete flow for a problematic caption."""
        from mcp_server.main import validate_caption_structure

        problematic_caption = "CLICK HERE NOW! BUY NOW! HURRY! LIMITED TIME! 💕💕💕💕💕💕💕💕💕💕💕💕"

        result = validate_caption_structure(problematic_caption, "bump_normal")

        # Should have low score due to multiple issues
        assert result["score"] < 70  # Multiple penalties stack
        assert result["recommendation"] == "REJECT"
        assert len(result["issues"]) > 0
        assert any("spam pattern" in issue.lower() for issue in result["issues"])
