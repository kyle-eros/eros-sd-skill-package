"""Tests for get_send_types_constraints MCP tool v2.0.0."""

import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Insert project root for imports
sys.path.insert(0, '/Users/kylemerriman/Developer/eros-sd-skill-package')


# Mock send_types data matching production schema (9 constraint fields)
MOCK_SEND_TYPES = [
    {
        'send_type_key': 'ppv_unlock', 'category': 'revenue',
        'page_type_restriction': 'both', 'max_per_day': 4,
        'max_per_week': None, 'min_hours_between': 2,
        'requires_media': 1, 'requires_price': 1, 'requires_flyer': 1
    },
    {
        'send_type_key': 'ppv_wall', 'category': 'revenue',
        'page_type_restriction': 'free', 'max_per_day': 3,
        'max_per_week': None, 'min_hours_between': 3,
        'requires_media': 1, 'requires_price': 1, 'requires_flyer': 1
    },
    {
        'send_type_key': 'tip_goal', 'category': 'revenue',
        'page_type_restriction': 'paid', 'max_per_day': 2,
        'max_per_week': None, 'min_hours_between': 4,
        'requires_media': 1, 'requires_price': 1, 'requires_flyer': 0
    },
    {
        'send_type_key': 'bump_normal', 'category': 'engagement',
        'page_type_restriction': 'both', 'max_per_day': 5,
        'max_per_week': None, 'min_hours_between': 1,
        'requires_media': 1, 'requires_price': 0, 'requires_flyer': 0
    },
    {
        'send_type_key': 'renew_on_post', 'category': 'retention',
        'page_type_restriction': 'paid', 'max_per_day': 2,
        'max_per_week': None, 'min_hours_between': 12,
        'requires_media': 1, 'requires_price': 0, 'requires_flyer': 0
    },
]


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear module cache before each test."""
    from mcp_server import main
    main._SEND_TYPES_CACHE.clear()
    main._SEND_TYPES_CACHE_META.clear()
    yield
    main._SEND_TYPES_CACHE.clear()
    main._SEND_TYPES_CACHE_META.clear()


@pytest.fixture
def mock_db():
    """Mock db_query to return test data."""
    with patch('mcp_server.main.db_query') as mock:
        mock.return_value = MOCK_SEND_TYPES
        yield mock


class TestInputValidation:
    """Tests for page_type input validation."""

    def test_valid_page_type_paid_lowercase(self, mock_db):
        """Valid lowercase 'paid' should filter correctly."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints(page_type='paid')

        assert 'error' not in result
        assert result['page_type_filter'] == 'paid'
        # ppv_wall (free-only) should be excluded
        assert 'ppv_wall' not in result['all_send_type_keys']
        # tip_goal (paid-only) should be included
        assert 'tip_goal' in result['all_send_type_keys']

    def test_valid_page_type_case_normalized(self, mock_db):
        """'PAID', 'Paid', 'paid' should all work."""
        from mcp_server.main import get_send_types_constraints

        for variant in ['PAID', 'Paid', 'paid', '  paid  ']:
            # Clear cache between tests
            from mcp_server import main
            main._SEND_TYPES_CACHE.clear()
            main._SEND_TYPES_CACHE_META.clear()

            result = get_send_types_constraints(page_type=variant)
            assert 'error' not in result, f"Failed for variant: {variant}"
            assert result['page_type_filter'] == 'paid'

    def test_valid_page_type_free_filters_correctly(self, mock_db):
        """Valid 'free' should exclude paid-only types."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints(page_type='free')

        assert 'error' not in result
        assert result['page_type_filter'] == 'free'
        # ppv_wall (free-only) should be included
        assert 'ppv_wall' in result['all_send_type_keys']
        # tip_goal (paid-only) should be excluded
        assert 'tip_goal' not in result['all_send_type_keys']
        # renew_on_post (paid-only) should be excluded
        assert 'renew_on_post' not in result['all_send_type_keys']

    def test_null_page_type_returns_all(self, mock_db):
        """None page_type should return all send types."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints(page_type=None)

        assert 'error' not in result
        assert result['page_type_filter'] is None
        assert len(result['all_send_type_keys']) == 5  # All mock types

    def test_invalid_page_type_returns_error(self, mock_db):
        """Invalid page_type should return error with code and valid_values."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints(page_type='invalid_value')

        assert 'error' in result
        assert result['error_code'] == 'INVALID_PAGE_TYPE'
        assert 'invalid_value' in result['error']
        assert result['by_category'] == {"revenue": [], "engagement": [], "retention": []}
        assert result['counts']['total'] == 0
        # v2.0.1: valid_values as structured data
        assert 'valid_values' in result
        assert result['valid_values'] == ['paid', 'free', None]


class TestResponseSchema:
    """Tests for v2.0 response schema."""

    def test_by_category_grouping_correct(self, mock_db):
        """Send types should be grouped by category."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints()

        assert 'by_category' in result
        assert 'revenue' in result['by_category']
        assert 'engagement' in result['by_category']
        assert 'retention' in result['by_category']

        # Verify correct grouping
        revenue_keys = [t['send_type_key'] for t in result['by_category']['revenue']]
        assert 'ppv_unlock' in revenue_keys
        assert 'bump_normal' not in revenue_keys

    def test_all_send_type_keys_present(self, mock_db):
        """all_send_type_keys should list all keys."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints()

        assert 'all_send_type_keys' in result
        assert len(result['all_send_type_keys']) == 5
        assert 'ppv_unlock' in result['all_send_type_keys']

    def test_counts_accurate(self, mock_db):
        """counts should match actual groupings."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints()

        assert 'counts' in result
        assert result['counts']['total'] == 5
        assert result['counts']['revenue'] == len(result['by_category']['revenue'])
        assert result['counts']['engagement'] == len(result['by_category']['engagement'])
        assert result['counts']['retention'] == len(result['by_category']['retention'])

    def test_metadata_present(self, mock_db):
        """metadata block should have required fields."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints()

        assert 'metadata' in result
        assert 'fetched_at' in result['metadata']
        assert 'tool_version' in result['metadata']
        assert result['metadata']['tool_version'] == '2.0.0'
        assert 'source' in result['metadata']
        assert 'types_hash' in result['metadata']

    def test_send_types_array_removed(self, mock_db):
        """Old send_types array should NOT be in response."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints()

        assert 'send_types' not in result
        assert 'fields_returned' not in result
        assert '_optimization_note' not in result


class TestCaching:
    """Tests for module-level caching."""

    def test_cache_populated_on_first_call(self, mock_db):
        """First call should populate cache."""
        from mcp_server import main
        from mcp_server.main import get_send_types_constraints

        assert 'all_types' not in main._SEND_TYPES_CACHE
        assert len(main._SEND_TYPES_CACHE) == 0

        result = get_send_types_constraints()

        assert len(main._SEND_TYPES_CACHE) > 0
        assert result['metadata']['source'] == 'database'

    def test_cache_hit_on_second_call(self, mock_db):
        """Second call should use cache."""
        from mcp_server import main
        from mcp_server.main import get_send_types_constraints

        # First call populates cache
        result1 = get_send_types_constraints()
        assert result1['metadata']['source'] == 'database'

        # Second call should hit cache
        result2 = get_send_types_constraints()
        assert result2['metadata']['source'] == 'cache'
        assert result2['metadata']['cached_at'] is not None

        # db_query should only be called once
        assert mock_db.call_count == 1

    def test_types_hash_consistent(self, mock_db):
        """types_hash should be consistent across calls."""
        from mcp_server.main import get_send_types_constraints

        result1 = get_send_types_constraints()
        result2 = get_send_types_constraints(page_type='paid')

        assert result1['metadata']['types_hash'] == result2['metadata']['types_hash']


class TestConstraintFields:
    """Tests for constraint field inclusion."""

    def test_all_nine_constraint_fields_present(self, mock_db):
        """Each send type should have all 9 constraint fields."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints()

        expected_fields = [
            'send_type_key', 'category', 'page_type_restriction',
            'max_per_day', 'max_per_week', 'min_hours_between',
            'requires_media', 'requires_price', 'requires_flyer'
        ]

        for category in result['by_category'].values():
            for send_type in category:
                for field in expected_fields:
                    assert field in send_type, f"Missing field: {field}"
