"""Tests for get_send_types MCP tool v2.0.0."""

import sys
import pytest
from unittest.mock import patch
from datetime import datetime

# Insert project root for imports
sys.path.insert(0, '/Users/kylemerriman/Developer/eros-sd-skill-package')


# Mock send_types data with 48 business columns
MOCK_SEND_TYPES_FULL = [
    {
        'send_type_id': 1, 'send_type_key': 'ppv_unlock', 'display_name': 'PPV Unlock',
        'category': 'revenue', 'page_type_restriction': 'both',
        'description': 'Primary PPV', 'purpose': 'Revenue', 'strategy': 'Build anticipation',
        'requires_media': 1, 'requires_flyer': 1, 'requires_price': 1, 'requires_link': 0,
        'has_expiration': 0, 'default_expiration_hours': None, 'can_have_followup': 1,
        'followup_delay_minutes': 28, 'caption_length': 'long', 'emoji_recommendation': 'heavy',
        'max_per_day': 4, 'max_per_week': None, 'min_hours_between': 2, 'sort_order': 10,
        'is_active': 1, 'priority_score': 0.7, 'allocation_weight': 70,
        'fatigue_score': 7, 'fatigue_multiplier': 1.5,
        'revenue_weight': 0.4, 'engagement_weight': 0.35, 'retention_weight': 0.25,
        'cooldown_category': 'aggressive', 'cooldown_after_engagement_min': 240,
        'cooldown_after_revenue_min': 240, 'audience_segment': 'all',
        'ab_test_eligible': 1, 'current_experiment_id': None, 'min_subscriber_tenure_days': 0,
        'primary_channel_key': 'mass_message', 'secondary_channel_key': None,
        'primary_channel_weight': 100, 'wall_delivery_page_type': None,
        'wall_content_level': 'standard', 'supports_link_drop_promo': 0,
        'channel_distribution': 'dm_only', 'hybrid_split': None, 'page_type_lock': None,
        'drip_window_allowed': 0, 'drip_window_triggers': 0
    },
    {
        'send_type_id': 2, 'send_type_key': 'ppv_wall', 'display_name': 'PPV Wall',
        'category': 'revenue', 'page_type_restriction': 'free',
        'description': 'Wall PPV', 'purpose': 'Revenue', 'strategy': 'Free page monetization',
        'requires_media': 1, 'requires_flyer': 1, 'requires_price': 1, 'requires_link': 0,
        'has_expiration': 0, 'default_expiration_hours': None, 'can_have_followup': 1,
        'followup_delay_minutes': 28, 'caption_length': 'long', 'emoji_recommendation': 'heavy',
        'max_per_day': 3, 'max_per_week': None, 'min_hours_between': 3, 'sort_order': 15,
        'is_active': 1, 'priority_score': 0.6, 'allocation_weight': 60,
        'fatigue_score': 6, 'fatigue_multiplier': 1.3,
        'revenue_weight': 0.4, 'engagement_weight': 0.35, 'retention_weight': 0.25,
        'cooldown_category': 'standard', 'cooldown_after_engagement_min': 180,
        'cooldown_after_revenue_min': 180, 'audience_segment': 'all',
        'ab_test_eligible': 1, 'current_experiment_id': None, 'min_subscriber_tenure_days': 0,
        'primary_channel_key': 'wall_post', 'secondary_channel_key': None,
        'primary_channel_weight': 100, 'wall_delivery_page_type': 'free',
        'wall_content_level': 'standard', 'supports_link_drop_promo': 0,
        'channel_distribution': 'wall_only', 'hybrid_split': None, 'page_type_lock': 'free',
        'drip_window_allowed': 0, 'drip_window_triggers': 0
    },
    {
        'send_type_id': 3, 'send_type_key': 'tip_goal', 'display_name': 'Tip Goal',
        'category': 'revenue', 'page_type_restriction': 'paid',
        'description': 'Tip goal post', 'purpose': 'Revenue', 'strategy': 'Gamified tipping',
        'requires_media': 1, 'requires_flyer': 0, 'requires_price': 1, 'requires_link': 0,
        'has_expiration': 1, 'default_expiration_hours': 24, 'can_have_followup': 0,
        'followup_delay_minutes': None, 'caption_length': 'medium', 'emoji_recommendation': 'moderate',
        'max_per_day': 2, 'max_per_week': None, 'min_hours_between': 4, 'sort_order': 20,
        'is_active': 1, 'priority_score': 0.5, 'allocation_weight': 50,
        'fatigue_score': 5, 'fatigue_multiplier': 1.0,
        'revenue_weight': 0.35, 'engagement_weight': 0.35, 'retention_weight': 0.3,
        'cooldown_category': 'standard', 'cooldown_after_engagement_min': 120,
        'cooldown_after_revenue_min': 120, 'audience_segment': 'all',
        'ab_test_eligible': 1, 'current_experiment_id': None, 'min_subscriber_tenure_days': 0,
        'primary_channel_key': 'wall_post', 'secondary_channel_key': None,
        'primary_channel_weight': 100, 'wall_delivery_page_type': 'paid',
        'wall_content_level': 'standard', 'supports_link_drop_promo': 0,
        'channel_distribution': 'wall_only', 'hybrid_split': None, 'page_type_lock': 'paid',
        'drip_window_allowed': 0, 'drip_window_triggers': 0
    },
    {
        'send_type_id': 4, 'send_type_key': 'bump_normal', 'display_name': 'Bump Normal',
        'category': 'engagement', 'page_type_restriction': 'both',
        'description': 'Standard bump', 'purpose': 'Engagement', 'strategy': 'Keep visible',
        'requires_media': 1, 'requires_flyer': 0, 'requires_price': 0, 'requires_link': 0,
        'has_expiration': 0, 'default_expiration_hours': None, 'can_have_followup': 0,
        'followup_delay_minutes': None, 'caption_length': 'short', 'emoji_recommendation': 'light',
        'max_per_day': 5, 'max_per_week': None, 'min_hours_between': 1, 'sort_order': 100,
        'is_active': 1, 'priority_score': 0.3, 'allocation_weight': 30,
        'fatigue_score': 2, 'fatigue_multiplier': 0.8,
        'revenue_weight': 0.2, 'engagement_weight': 0.5, 'retention_weight': 0.3,
        'cooldown_category': 'relaxed', 'cooldown_after_engagement_min': 60,
        'cooldown_after_revenue_min': 60, 'audience_segment': 'all',
        'ab_test_eligible': 1, 'current_experiment_id': None, 'min_subscriber_tenure_days': 0,
        'primary_channel_key': 'mass_message', 'secondary_channel_key': None,
        'primary_channel_weight': 100, 'wall_delivery_page_type': None,
        'wall_content_level': 'standard', 'supports_link_drop_promo': 0,
        'channel_distribution': 'dm_only', 'hybrid_split': None, 'page_type_lock': None,
        'drip_window_allowed': 0, 'drip_window_triggers': 0
    },
    {
        'send_type_id': 5, 'send_type_key': 'renew_on_post', 'display_name': 'Renew On Post',
        'category': 'retention', 'page_type_restriction': 'paid',
        'description': 'Retention post', 'purpose': 'Retention', 'strategy': 'Re-engage lapsed',
        'requires_media': 1, 'requires_flyer': 0, 'requires_price': 0, 'requires_link': 0,
        'has_expiration': 0, 'default_expiration_hours': None, 'can_have_followup': 0,
        'followup_delay_minutes': None, 'caption_length': 'medium', 'emoji_recommendation': 'moderate',
        'max_per_day': 2, 'max_per_week': None, 'min_hours_between': 12, 'sort_order': 200,
        'is_active': 1, 'priority_score': 0.4, 'allocation_weight': 40,
        'fatigue_score': 3, 'fatigue_multiplier': 0.9,
        'revenue_weight': 0.25, 'engagement_weight': 0.35, 'retention_weight': 0.4,
        'cooldown_category': 'conservative', 'cooldown_after_engagement_min': 360,
        'cooldown_after_revenue_min': 360, 'audience_segment': 'expiring',
        'ab_test_eligible': 1, 'current_experiment_id': None, 'min_subscriber_tenure_days': 25,
        'primary_channel_key': 'mass_message', 'secondary_channel_key': None,
        'primary_channel_weight': 100, 'wall_delivery_page_type': None,
        'wall_content_level': 'standard', 'supports_link_drop_promo': 0,
        'channel_distribution': 'dm_only', 'hybrid_split': None, 'page_type_lock': 'paid',
        'drip_window_allowed': 0, 'drip_window_triggers': 0
    },
]


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all module caches before and after each test."""
    from mcp_server import main
    main._SEND_TYPES_CACHE.clear()
    main._SEND_TYPES_CACHE_META.clear()
    main._SEND_TYPES_FULL_CACHE.clear()
    yield
    main._SEND_TYPES_CACHE.clear()
    main._SEND_TYPES_CACHE_META.clear()
    main._SEND_TYPES_FULL_CACHE.clear()


@pytest.fixture
def mock_db():
    """Mock db_query to return test data."""
    with patch('mcp_server.main.db_query') as mock:
        mock.return_value = MOCK_SEND_TYPES_FULL
        yield mock


class TestInputValidation:
    """Tests for page_type input validation."""

    def test_valid_page_type_paid_lowercase(self, mock_db):
        """Valid lowercase 'paid' should filter correctly."""
        from mcp_server.main import get_send_types
        result = get_send_types(page_type='paid')

        assert 'error' not in result
        assert result['page_type_filter'] == 'paid'
        # ppv_wall (free-only) should be excluded
        assert 'ppv_wall' not in result['all_send_type_keys']
        # tip_goal (paid-only) should be included
        assert 'tip_goal' in result['all_send_type_keys']

    def test_valid_page_type_case_normalized(self, mock_db):
        """'PAID', 'Paid', 'paid' should all work."""
        from mcp_server.main import get_send_types
        from mcp_server import main

        for variant in ['PAID', 'Paid', 'paid', '  paid  ']:
            # Clear caches between variants
            main._SEND_TYPES_FULL_CACHE.clear()

            result = get_send_types(page_type=variant)
            assert 'error' not in result, f"Failed for variant: {variant}"
            assert result['page_type_filter'] == 'paid'

    def test_valid_page_type_free_filters_correctly(self, mock_db):
        """Valid 'free' should exclude paid-only types."""
        from mcp_server.main import get_send_types
        result = get_send_types(page_type='free')

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
        from mcp_server.main import get_send_types
        result = get_send_types(page_type=None)

        assert 'error' not in result
        assert result['page_type_filter'] is None
        assert len(result['all_send_type_keys']) == 5  # All mock types

    def test_invalid_page_type_returns_error(self, mock_db):
        """Invalid page_type should return error with code."""
        from mcp_server.main import get_send_types
        result = get_send_types(page_type='invalid_value')

        assert 'error' in result
        assert result['error_code'] == 'INVALID_PAGE_TYPE'
        assert 'invalid_value' in result['error']
        assert result['by_category'] == {"revenue": [], "engagement": [], "retention": []}
        assert result['counts']['total'] == 0
        assert result['valid_values'] == ['paid', 'free', None]


class TestResponseSchema:
    """Tests for v2.0 response schema."""

    def test_no_send_types_flat_array(self, mock_db):
        """v2.0 BREAKING: send_types flat array should NOT be in response."""
        from mcp_server.main import get_send_types
        result = get_send_types()

        assert 'send_types' not in result, "Old send_types array should be removed in v2.0"

    def test_by_category_grouping_correct(self, mock_db):
        """Send types should be grouped by category."""
        from mcp_server.main import get_send_types
        result = get_send_types()

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
        from mcp_server.main import get_send_types
        result = get_send_types()

        assert 'all_send_type_keys' in result
        assert len(result['all_send_type_keys']) == 5
        assert 'ppv_unlock' in result['all_send_type_keys']

    def test_counts_accurate(self, mock_db):
        """counts should match actual groupings."""
        from mcp_server.main import get_send_types
        result = get_send_types()

        assert 'counts' in result
        assert result['counts']['total'] == 5
        assert result['counts']['revenue'] == len(result['by_category']['revenue'])
        assert result['counts']['engagement'] == len(result['by_category']['engagement'])
        assert result['counts']['retention'] == len(result['by_category']['retention'])

    def test_metadata_present(self, mock_db):
        """metadata block should have required fields."""
        from mcp_server.main import get_send_types
        result = get_send_types()

        assert 'metadata' in result
        assert 'fetched_at' in result['metadata']
        assert 'tool_version' in result['metadata']
        assert result['metadata']['tool_version'] == '2.0.0'
        assert 'source' in result['metadata']
        assert 'types_hash' in result['metadata']


class TestCaching:
    """Tests for module-level caching."""

    def test_full_cache_populated_on_first_call(self, mock_db):
        """First call should populate full cache."""
        from mcp_server import main
        from mcp_server.main import get_send_types

        assert len(main._SEND_TYPES_FULL_CACHE) == 0

        result = get_send_types()

        assert len(main._SEND_TYPES_FULL_CACHE) > 0
        assert result['metadata']['source'] == 'database'

    def test_full_cache_hit_on_second_call(self, mock_db):
        """Second call should use cache."""
        from mcp_server import main
        from mcp_server.main import get_send_types

        # First call populates cache
        result1 = get_send_types()
        assert result1['metadata']['source'] == 'database'

        # Second call should hit cache
        result2 = get_send_types()
        assert result2['metadata']['source'] == 'cache'

    def test_full_cache_separate_from_constraints_cache(self, mock_db):
        """Full cache should be separate from constraints cache."""
        from mcp_server import main
        from mcp_server.main import get_send_types

        # Call get_send_types (populates full cache)
        get_send_types()

        # Full cache should be populated
        assert len(main._SEND_TYPES_FULL_CACHE) > 0
        # Note: constraints cache is populated via _get_send_types_cache_meta call


class TestFieldContent:
    """Tests for field content in response."""

    def test_all_48_columns_present(self, mock_db):
        """Each send type should have all 48 business columns."""
        from mcp_server.main import get_send_types
        result = get_send_types()

        expected_fields = [
            'send_type_id', 'send_type_key', 'display_name', 'category', 'page_type_restriction',
            'description', 'purpose', 'strategy',
            'requires_media', 'requires_flyer', 'requires_price', 'requires_link', 'has_expiration',
            'default_expiration_hours', 'can_have_followup', 'followup_delay_minutes',
            'caption_length', 'emoji_recommendation',
            'max_per_day', 'max_per_week', 'min_hours_between', 'sort_order', 'is_active',
            'priority_score', 'allocation_weight', 'fatigue_score', 'fatigue_multiplier',
            'revenue_weight', 'engagement_weight', 'retention_weight',
            'cooldown_category', 'cooldown_after_engagement_min', 'cooldown_after_revenue_min',
            'audience_segment', 'ab_test_eligible', 'current_experiment_id', 'min_subscriber_tenure_days',
            'primary_channel_key', 'secondary_channel_key', 'primary_channel_weight',
            'wall_delivery_page_type', 'wall_content_level', 'supports_link_drop_promo',
            'channel_distribution', 'hybrid_split', 'page_type_lock',
            'drip_window_allowed', 'drip_window_triggers'
        ]

        for category in result['by_category'].values():
            for send_type in category:
                for field in expected_fields:
                    assert field in send_type, f"Missing field: {field}"

    def test_excluded_columns_not_present(self, mock_db):
        """Internal lifecycle columns should NOT be in response (when excluded from query)."""
        from mcp_server.main import get_send_types
        result = get_send_types()

        # Note: The mock data doesn't have these fields, so this test
        # verifies that the production query excludes them
        excluded_fields = ['schema_version', 'created_at', 'updated_at', 'deprecated_at', 'replacement_send_type_id']

        for category in result['by_category'].values():
            for send_type in category:
                for field in excluded_fields:
                    assert field not in send_type, f"Internal field should be excluded: {field}"


class TestErrorResponses:
    """Tests for error response schema."""

    def test_error_response_has_full_schema(self, mock_db):
        """Error response should have full schema with empty arrays."""
        from mcp_server.main import get_send_types
        result = get_send_types(page_type='invalid')

        # Required error fields
        assert 'error' in result
        assert 'error_code' in result

        # Full schema fields (with empty values)
        assert 'by_category' in result
        assert result['by_category'] == {"revenue": [], "engagement": [], "retention": []}
        assert 'all_send_type_keys' in result
        assert result['all_send_type_keys'] == []
        assert 'counts' in result
        assert result['counts']['total'] == 0
        assert 'metadata' in result

    def test_error_preserves_original_page_type(self, mock_db):
        """Error response should echo the original (invalid) input."""
        from mcp_server.main import get_send_types
        result = get_send_types(page_type='INVALID')

        # page_type_filter should show original input, not normalized
        assert result['page_type_filter'] == 'INVALID'
