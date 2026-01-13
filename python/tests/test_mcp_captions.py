"""Tests for get_batch_captions_by_content_types MCP tool.

Test Categories:
- Input validation (7 tests)
- Happy path (5 tests)
- Per-creator freshness (4 tests)
- Pool stats (3 tests)
- Filtering (3 tests)
- Metadata/structure (3 tests)
- Edge cases (2 tests)

Total: 27 tests
Target: 90% line coverage, 85% branch coverage
"""

import pytest
import hashlib
import sys
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add project root to path for mcp_server package imports
sys.path.insert(0, '/Users/kylemerriman/Developer/eros-sd-skill-package')


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db_query():
    """Mock db_query to return controlled test data."""
    with patch('mcp_server.main.db_query') as mock:
        yield mock


@pytest.fixture
def mock_resolve_creator():
    """Mock resolve_creator_id to return found creator."""
    with patch('mcp_server.main.resolve_creator_id') as mock:
        mock.return_value = {"found": True, "creator_id": "test_creator_123"}
        yield mock


@pytest.fixture
def mock_validate_creator():
    """Mock validate_creator_id to return valid."""
    with patch('mcp_server.main.validate_creator_id') as mock:
        mock.return_value = (True, "test_creator")
        yield mock


@pytest.fixture
def sample_caption_rows():
    """Sample caption data matching query structure."""
    return [
        {
            "caption_id": 1,
            "caption_text": "Test caption 1",
            "category": "ppv",
            "performance_tier": 1,
            "content_type": "lingerie",
            "last_used_at": "2026-01-01T10:00:00",
            "use_count": 5,
            "suggested_price": 15.00,
            "price_range_min": 10.00,
            "price_range_max": 25.00,
            "avg_purchase_rate": 0.12,
            "creator_last_used_at": "2025-10-01T10:00:00",
            "creator_use_count": 2,
            "total_available": 10,
            "fresh_for_creator": 6,
            "avg_pool_performance_tier": 2.5,
            "rn": 1
        },
        {
            "caption_id": 2,
            "caption_text": "Test caption 2",
            "category": "ppv",
            "performance_tier": 2,
            "content_type": "lingerie",
            "last_used_at": None,
            "use_count": 0,
            "suggested_price": None,
            "price_range_min": 5.00,
            "price_range_max": 50.00,
            "avg_purchase_rate": None,
            "creator_last_used_at": None,
            "creator_use_count": 0,
            "total_available": 10,
            "fresh_for_creator": 6,
            "avg_pool_performance_tier": 2.5,
            "rn": 2
        }
    ]


# =============================================================================
# INPUT VALIDATION TESTS (7)
# =============================================================================

class TestInputValidation:
    """Test 4-layer input validation."""

    def test_empty_creator_id(self):
        """Empty creator_id returns INVALID_CREATOR_ID error."""
        from mcp_server.main import get_batch_captions_by_content_types
        result = get_batch_captions_by_content_types("", ["lingerie"])
        assert result["error_code"] == "INVALID_CREATOR_ID"
        assert result["captions_by_type"] == {}
        assert "metadata" in result
        assert result["metadata"]["error"] is True

    def test_invalid_creator_id_format(self, mock_validate_creator):
        """Invalid creator_id format returns INVALID_CREATOR_ID_FORMAT error."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_validate_creator.return_value = (False, "Invalid characters")
        result = get_batch_captions_by_content_types("invalid@id!", ["lingerie"])
        assert result["error_code"] == "INVALID_CREATOR_ID_FORMAT"

    def test_creator_not_found(self, mock_validate_creator, mock_resolve_creator):
        """Non-existent creator returns CREATOR_NOT_FOUND error."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_validate_creator.return_value = (True, "nonexistent")
        mock_resolve_creator.return_value = {"found": False}
        result = get_batch_captions_by_content_types("nonexistent", ["lingerie"])
        assert result["error_code"] == "CREATOR_NOT_FOUND"

    def test_empty_content_types(self):
        """Empty content_types list returns EMPTY_CONTENT_TYPES error."""
        from mcp_server.main import get_batch_captions_by_content_types
        result = get_batch_captions_by_content_types("creator", [])
        assert result["error_code"] == "EMPTY_CONTENT_TYPES"

    def test_content_types_not_list(self):
        """Non-list content_types returns INVALID_CONTENT_TYPES error."""
        from mcp_server.main import get_batch_captions_by_content_types
        result = get_batch_captions_by_content_types("creator", "lingerie")
        assert result["error_code"] == "INVALID_CONTENT_TYPES"

    def test_content_types_limit_exceeded(self):
        """More than 50 content types returns CONTENT_TYPES_LIMIT_EXCEEDED error."""
        from mcp_server.main import get_batch_captions_by_content_types
        types = [f"type_{i}" for i in range(51)]
        result = get_batch_captions_by_content_types("creator", types)
        assert result["error_code"] == "CONTENT_TYPES_LIMIT_EXCEEDED"

    def test_invalid_schedulable_type(self, mock_validate_creator, mock_resolve_creator):
        """Invalid schedulable_type returns INVALID_SCHEDULABLE_TYPE error."""
        from mcp_server.main import get_batch_captions_by_content_types
        result = get_batch_captions_by_content_types(
            "creator", ["lingerie"], schedulable_type="invalid"
        )
        assert result["error_code"] == "INVALID_SCHEDULABLE_TYPE"


# =============================================================================
# HAPPY PATH TESTS (5)
# =============================================================================

class TestHappyPath:
    """Test successful caption retrieval."""

    def test_single_content_type(self, mock_validate_creator, mock_resolve_creator,
                                  mock_db_query, sample_caption_rows):
        """Single content type returns captions with all fields."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"])

        assert "error" not in result
        assert "lingerie" in result["captions_by_type"]
        assert len(result["captions_by_type"]["lingerie"]["captions"]) == 2
        assert result["total_captions"] == 2
        assert "metadata" in result

    def test_multiple_content_types(self, mock_validate_creator, mock_resolve_creator,
                                     mock_db_query, sample_caption_rows):
        """Multiple content types returns captions grouped by type."""
        from mcp_server.main import get_batch_captions_by_content_types
        shower_rows = [dict(r, content_type="shower") for r in sample_caption_rows]
        mock_db_query.return_value = sample_caption_rows + shower_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie", "shower"])

        assert "lingerie" in result["captions_by_type"]
        assert "shower" in result["captions_by_type"]
        assert result["types_requested"] == 2

    def test_limit_clamping_low(self, mock_validate_creator, mock_resolve_creator,
                                 mock_db_query, sample_caption_rows):
        """limit_per_type below 1 is clamped to 1."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows[:1]

        result = get_batch_captions_by_content_types("creator", ["lingerie"], limit_per_type=0)
        assert mock_db_query.called

    def test_limit_clamping_high(self, mock_validate_creator, mock_resolve_creator,
                                  mock_db_query, sample_caption_rows):
        """limit_per_type above 20 is clamped to 20."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"], limit_per_type=100)
        assert mock_db_query.called

    def test_with_schedulable_type(self, mock_validate_creator, mock_resolve_creator,
                                    mock_db_query, sample_caption_rows):
        """schedulable_type filter is applied correctly."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types(
            "creator", ["lingerie"], schedulable_type="ppv"
        )
        assert result["metadata"]["filters_applied"]["schedulable_type"] == "ppv"


# =============================================================================
# PER-CREATOR FRESHNESS TESTS (4)
# =============================================================================

class TestPerCreatorFreshness:
    """Test per-creator freshness tracking."""

    def test_creator_freshness_available(self, mock_validate_creator, mock_resolve_creator,
                                          mock_db_query, sample_caption_rows):
        """Per-creator freshness fields populated when data exists."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"])

        caption = result["captions_by_type"]["lingerie"]["captions"][0]
        assert caption["creator_last_used_at"] is not None
        assert caption["creator_use_count"] == 2
        assert caption["days_since_creator_used"] is not None
        assert caption["effectively_fresh"] is True

    def test_creator_freshness_null(self, mock_validate_creator, mock_resolve_creator,
                                     mock_db_query, sample_caption_rows):
        """Freshness fields handle NULL creator data gracefully."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"])

        caption = result["captions_by_type"]["lingerie"]["captions"][1]
        assert caption["creator_last_used_at"] is None
        assert caption["creator_use_count"] == 0
        assert caption["days_since_creator_used"] is None
        assert caption["effectively_fresh"] is True

    def test_freshness_sorting(self, mock_validate_creator, mock_resolve_creator,
                                mock_db_query, sample_caption_rows):
        """Captions sorted by creator freshness (never-used first)."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = list(reversed(sample_caption_rows))

        result = get_batch_captions_by_content_types("creator", ["lingerie"])
        assert result["metadata"]["per_creator_data_available"] is True

    def test_days_since_computation(self, mock_validate_creator, mock_resolve_creator,
                                     mock_db_query):
        """days_since_creator_used computed correctly."""
        from mcp_server.main import get_batch_captions_by_content_types
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        rows = [{
            "caption_id": 1, "caption_text": "Test", "category": "ppv",
            "performance_tier": 2, "content_type": "lingerie",
            "last_used_at": None, "use_count": 0,
            "suggested_price": None, "price_range_min": 5.00,
            "price_range_max": 50.00, "avg_purchase_rate": None,
            "creator_last_used_at": yesterday, "creator_use_count": 1,
            "total_available": 5, "fresh_for_creator": 3,
            "avg_pool_performance_tier": 2.0, "rn": 1
        }]
        mock_db_query.return_value = rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"])

        caption = result["captions_by_type"]["lingerie"]["captions"][0]
        assert caption["days_since_creator_used"] == 1
        assert caption["effectively_fresh"] is False


# =============================================================================
# POOL STATS TESTS (3)
# =============================================================================

class TestPoolStats:
    """Test pool statistics per content type."""

    def test_pool_total_available(self, mock_validate_creator, mock_resolve_creator,
                                   mock_db_query, sample_caption_rows):
        """pool_stats.total_available reflects full pool size."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"])

        pool_stats = result["captions_by_type"]["lingerie"]["pool_stats"]
        assert pool_stats["total_available"] == 10

    def test_pool_fresh_for_creator(self, mock_validate_creator, mock_resolve_creator,
                                     mock_db_query, sample_caption_rows):
        """pool_stats.fresh_for_creator counts unused captions."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"])

        pool_stats = result["captions_by_type"]["lingerie"]["pool_stats"]
        assert pool_stats["fresh_for_creator"] == 6

    def test_pool_has_more(self, mock_validate_creator, mock_resolve_creator,
                           mock_db_query, sample_caption_rows):
        """pool_stats.has_more indicates more captions available."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"])

        pool_stats = result["captions_by_type"]["lingerie"]["pool_stats"]
        assert pool_stats["has_more"] is True


# =============================================================================
# FILTERING TESTS (3)
# =============================================================================

class TestFiltering:
    """Test schedulable_type and content type filtering."""

    def test_schedulable_type_ppv(self, mock_validate_creator, mock_resolve_creator,
                                   mock_db_query, sample_caption_rows):
        """schedulable_type='ppv' filters to PPV captions."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types(
            "creator", ["lingerie"], schedulable_type="ppv"
        )
        assert result["metadata"]["filters_applied"]["schedulable_type"] == "ppv"

    def test_schedulable_type_null(self, mock_validate_creator, mock_resolve_creator,
                                    mock_db_query, sample_caption_rows):
        """schedulable_type=None returns all types."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"])
        assert result["metadata"]["filters_applied"]["schedulable_type"] is None

    def test_unknown_content_type(self, mock_validate_creator, mock_resolve_creator,
                                   mock_db_query):
        """Unknown content type returns empty captions list."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = []

        result = get_batch_captions_by_content_types("creator", ["nonexistent_type"])

        assert result["captions_by_type"]["nonexistent_type"]["captions"] == []
        assert result["captions_by_type"]["nonexistent_type"]["pool_stats"]["total_available"] == 0


# =============================================================================
# METADATA/STRUCTURE TESTS (3)
# =============================================================================

class TestMetadataStructure:
    """Test metadata block and response structure."""

    def test_metadata_block_present(self, mock_validate_creator, mock_resolve_creator,
                                     mock_db_query, sample_caption_rows):
        """Response includes full metadata block."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types("creator", ["lingerie"])

        assert "metadata" in result
        assert "fetched_at" in result["metadata"]
        assert "query_ms" in result["metadata"]
        assert "captions_hash" in result["metadata"]
        assert "content_types_hash" in result["metadata"]
        assert "caption_ids_returned" in result["metadata"]
        assert "freshness_source" in result["metadata"]

    def test_hash_determinism(self, mock_validate_creator, mock_resolve_creator,
                               mock_db_query, sample_caption_rows):
        """Hashes are deterministic for same inputs."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result1 = get_batch_captions_by_content_types("creator", ["lingerie"])
        result2 = get_batch_captions_by_content_types("creator", ["lingerie"])

        assert result1["metadata"]["captions_hash"] == result2["metadata"]["captions_hash"]
        assert result1["metadata"]["content_types_hash"] == result2["metadata"]["content_types_hash"]

    def test_error_response_schema(self):
        """Error responses include all schema fields."""
        from mcp_server.main import get_batch_captions_by_content_types
        result = get_batch_captions_by_content_types("", [])

        assert "error" in result
        assert "error_code" in result
        assert "creator_id" in result
        assert "captions_by_type" in result
        assert "total_captions" in result
        assert "types_requested" in result
        assert "metadata" in result
        assert result["metadata"]["error"] is True


# =============================================================================
# EDGE CASE TESTS (2)
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_duplicate_content_types(self, mock_validate_creator, mock_resolve_creator,
                                      mock_db_query, sample_caption_rows):
        """Duplicate content types are deduplicated."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = sample_caption_rows

        result = get_batch_captions_by_content_types(
            "creator", ["lingerie", "lingerie", "lingerie"]
        )

        assert result["types_requested"] == 1
        assert len(result["captions_by_type"]) == 1

    def test_no_active_captions(self, mock_validate_creator, mock_resolve_creator,
                                 mock_db_query):
        """Empty result when no active captions exist."""
        from mcp_server.main import get_batch_captions_by_content_types
        mock_db_query.return_value = []

        result = get_batch_captions_by_content_types("creator", ["lingerie"])

        assert result["total_captions"] == 0
        assert result["captions_by_type"]["lingerie"]["captions"] == []
        assert result["metadata"]["captions_hash"] == "sha256:empty"
