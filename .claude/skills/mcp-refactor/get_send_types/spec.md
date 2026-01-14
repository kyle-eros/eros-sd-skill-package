# Specification: get_send_types v2.0.0

**Version**: 1.0.0
**Date**: 2026-01-13
**Author**: Claude Code (Phase 2 Ralph Loop)
**Status**: SPEC_COMPLETE

---

## 1. Executive Summary

Refactor `get_send_types` MCP tool from implicit v1.0 to v2.0.0 with:
- Hybrid caching strategy (lazy-loaded full cache)
- Consistent response schema matching `get_send_types_constraints`
- Curated 48-column output (excludes internal lifecycle fields)
- Structured error responses with `error_code`

**BREAKING CHANGE**: Removes redundant `send_types` flat array from response.

---

## 2. Design Decisions

### 2.1 Cache Strategy: Hybrid Lazy-Loading

```python
# Existing (unchanged)
_SEND_TYPES_CACHE: dict[str, dict] = {}       # 9 constraint fields
_SEND_TYPES_CACHE_META: dict[str, str] = {}   # cached_at, types_hash

# New (add)
_SEND_TYPES_FULL_CACHE: dict[str, dict] = {}  # 48 business columns, lazy-loaded
```

**Rationale**: `get_send_types_constraints` is PRIMARY (called frequently), `get_send_types` is SECONDARY (reference use). Lazy-loading avoids memory bloat until full data is actually needed.

### 2.2 Response Schema: Mirror Constraints Structure

```python
# v2.0.0 Response (matches constraints tool structure)
{
    "by_category": {
        "revenue": [{...48 fields...}, ...],
        "engagement": [{...48 fields...}, ...],
        "retention": [{...48 fields...}, ...]
    },
    "all_send_type_keys": ["ppv_unlock", "bump_normal", ...],
    "counts": {"revenue": 9, "engagement": 9, "retention": 4, "total": 22},
    "page_type_filter": "paid" | "free" | null,
    "metadata": {
        "fetched_at": "2026-01-13T...",
        "tool_version": "2.0.0",
        "source": "cache" | "database",
        "cached_at": "2026-01-13T..." | null,
        "types_hash": "abc123..."
    }
}
```

**BREAKING**: Removed `send_types` flat array. Consumers requiring flat list can derive: `[item for cat in result["by_category"].values() for item in cat]`

### 2.3 Column Selection: 48 Business-Relevant Fields

**Excluded (5 internal columns):**
- `schema_version` - Internal migration tracking
- `created_at` - Internal timestamp
- `updated_at` - Internal timestamp
- `deprecated_at` - Always NULL for is_active=1
- `replacement_send_type_id` - Always NULL for is_active=1

**Included (48 columns):**
```sql
send_type_id, send_type_key, display_name, category, page_type_restriction,
description, purpose, strategy,
requires_media, requires_flyer, requires_price, requires_link, has_expiration,
default_expiration_hours, can_have_followup, followup_delay_minutes,
caption_length, emoji_recommendation,
max_per_day, max_per_week, min_hours_between, sort_order, is_active,
priority_score, allocation_weight, fatigue_score, fatigue_multiplier,
revenue_weight, engagement_weight, retention_weight,
cooldown_category, cooldown_after_engagement_min, cooldown_after_revenue_min,
audience_segment, ab_test_eligible, current_experiment_id, min_subscriber_tenure_days,
primary_channel_key, secondary_channel_key, primary_channel_weight,
wall_delivery_page_type, wall_content_level, supports_link_drop_promo,
channel_distribution, hybrid_split, page_type_lock,
drip_window_allowed, drip_window_triggers
```

### 2.4 Error Response: Reuse Existing Helper

Error responses use `_build_send_types_error_response()` for consistency with constraints tool.

---

## 3. Implementation Phases

### Phase 1: Add Full Cache Infrastructure

**Files Modified:** `mcp_server/main.py`

**Before (lines ~3512-3556):**
```python
_SEND_TYPES_CACHE: dict[str, dict] = {}
_SEND_TYPES_CACHE_META: dict[str, str] = {}


def _get_send_types_cache() -> dict[str, dict]:
    """
    Load send types into module-level cache on first call.
    Extended in v2.0 to include constraint fields for both
    validate_caption_structure (needs category mapping) and
    get_send_types_constraints (needs all 9 fields).
    """
    global _SEND_TYPES_CACHE, _SEND_TYPES_CACHE_META
    if not _SEND_TYPES_CACHE:
        query = """
            SELECT send_type_key, category, page_type_restriction,
                   max_per_day, max_per_week, min_hours_between,
                   requires_media, requires_price, requires_flyer
            FROM send_types WHERE is_active = 1
            ORDER BY category, sort_order
        """
        rows = db_query(query, ())
        _SEND_TYPES_CACHE = {r["send_type_key"]: dict(r) for r in rows}

        # Compute hash for pipeline integrity verification
        keys_str = ','.join(sorted(_SEND_TYPES_CACHE.keys()))
        types_hash = hashlib.sha256(keys_str.encode()).hexdigest()[:12]

        _SEND_TYPES_CACHE_META = {
            "cached_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "types_hash": types_hash
        }
        logger.info(f"Loaded {len(_SEND_TYPES_CACHE)} send_types into cache (hash={types_hash})")
    return _SEND_TYPES_CACHE
```

**After:**
```python
_SEND_TYPES_CACHE: dict[str, dict] = {}
_SEND_TYPES_CACHE_META: dict[str, str] = {}
_SEND_TYPES_FULL_CACHE: dict[str, dict] = {}  # v2.0: 48-column cache for get_send_types

# Column list for full send_types (excludes internal lifecycle fields)
_SEND_TYPES_FULL_COLUMNS = """
    send_type_id, send_type_key, display_name, category, page_type_restriction,
    description, purpose, strategy,
    requires_media, requires_flyer, requires_price, requires_link, has_expiration,
    default_expiration_hours, can_have_followup, followup_delay_minutes,
    caption_length, emoji_recommendation,
    max_per_day, max_per_week, min_hours_between, sort_order, is_active,
    priority_score, allocation_weight, fatigue_score, fatigue_multiplier,
    revenue_weight, engagement_weight, retention_weight,
    cooldown_category, cooldown_after_engagement_min, cooldown_after_revenue_min,
    audience_segment, ab_test_eligible, current_experiment_id, min_subscriber_tenure_days,
    primary_channel_key, secondary_channel_key, primary_channel_weight,
    wall_delivery_page_type, wall_content_level, supports_link_drop_promo,
    channel_distribution, hybrid_split, page_type_lock,
    drip_window_allowed, drip_window_triggers
"""


def _get_send_types_cache() -> dict[str, dict]:
    """
    Load send types into module-level cache on first call.
    Extended in v2.0 to include constraint fields for both
    validate_caption_structure (needs category mapping) and
    get_send_types_constraints (needs all 9 fields).
    """
    global _SEND_TYPES_CACHE, _SEND_TYPES_CACHE_META
    if not _SEND_TYPES_CACHE:
        query = """
            SELECT send_type_key, category, page_type_restriction,
                   max_per_day, max_per_week, min_hours_between,
                   requires_media, requires_price, requires_flyer
            FROM send_types WHERE is_active = 1
            ORDER BY category, sort_order
        """
        rows = db_query(query, ())
        _SEND_TYPES_CACHE = {r["send_type_key"]: dict(r) for r in rows}

        # Compute hash for pipeline integrity verification
        keys_str = ','.join(sorted(_SEND_TYPES_CACHE.keys()))
        types_hash = hashlib.sha256(keys_str.encode()).hexdigest()[:12]

        _SEND_TYPES_CACHE_META = {
            "cached_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "types_hash": types_hash
        }
        logger.info(f"Loaded {len(_SEND_TYPES_CACHE)} send_types into cache (hash={types_hash})")
    return _SEND_TYPES_CACHE


def _get_send_types_full_cache() -> dict[str, dict]:
    """
    Lazy-load full 48-column cache on first get_send_types() call.

    Separate from _SEND_TYPES_CACHE to avoid bloating memory for
    get_send_types_constraints calls which only need 9 fields.

    Returns:
        dict keyed by send_type_key with 48 business-relevant columns.
    """
    global _SEND_TYPES_FULL_CACHE
    if not _SEND_TYPES_FULL_CACHE:
        query = f"""
            SELECT {_SEND_TYPES_FULL_COLUMNS}
            FROM send_types WHERE is_active = 1
            ORDER BY category, sort_order
        """
        rows = db_query(query, ())
        _SEND_TYPES_FULL_CACHE = {r["send_type_key"]: dict(r) for r in rows}
        logger.info(f"Loaded {len(_SEND_TYPES_FULL_CACHE)} full send_types into cache")
    return _SEND_TYPES_FULL_CACHE


def _is_send_types_full_cache_populated() -> bool:
    """Check if full cache was already populated (for source detection)."""
    return bool(_SEND_TYPES_FULL_CACHE)
```

**Verification:**
```bash
python3 -c "
import sys
sys.path.insert(0, '/Users/kylemerriman/Developer/eros-sd-skill-package')
from mcp_server.main import _SEND_TYPES_FULL_COLUMNS
# Verify column count
cols = [c.strip() for c in _SEND_TYPES_FULL_COLUMNS.strip().split(',') if c.strip()]
print(f'Column count: {len(cols)}')
assert len(cols) == 48, f'Expected 48 columns, got {len(cols)}'
print('Phase 1 column definition verified')
"
```

**Commit:** `feat(get_send_types): add 48-column full cache infrastructure`

---

### Phase 2: Refactor get_send_types to v2.0.0

**Files Modified:** `mcp_server/main.py`

**Before (lines 3974-4019):**
```python
def get_send_types(page_type: str = None) -> dict:
    """Returns the send type taxonomy with constraints.

    MCP Name: mcp__eros-db__get_send_types

    Args:
        page_type: Optional filter ('paid' or 'free')

    Returns:
        List of send types with constraints
    """
    logger.info(f"get_send_types: page_type={page_type}")
    try:
        query = "SELECT * FROM send_types WHERE is_active = 1"
        params = []

        if page_type == 'free':
            query += " AND page_type_restriction IN ('both', 'free')"
        elif page_type == 'paid':
            query += " AND page_type_restriction IN ('both', 'paid')"

        query += " ORDER BY category, sort_order"

        types = db_query(query, tuple(params))

        # Group by category
        by_category = {
            "revenue": [],
            "engagement": [],
            "retention": []
        }
        for t in types:
            cat = t.get('category', 'engagement').lower()
            if cat in by_category:
                by_category[cat].append(t)

        return {
            "send_types": types,
            "by_category": by_category,
            "total": len(types),
            "page_type_filter": page_type
        }

    except Exception as e:
        logger.error(f"get_send_types error: {e}")
        return {"error": str(e), "send_types": []}
```

**After:**
```python
@mcp.tool()
def get_send_types(page_type: str = None) -> dict:
    """Returns full send type taxonomy with all business-relevant fields.

    MCP Name: mcp__eros-db__get_send_types
    Version: 2.0.0

    This is the FULL REFERENCE tool returning 48 business-relevant columns.
    Use get_send_types_constraints() for lightweight schedule generation (9 fields).

    BREAKING CHANGE v2.0: Removed redundant 'send_types' flat array.
    Use by_category for grouped access or all_send_type_keys for key list.

    Args:
        page_type: Optional filter ('paid', 'free', or None for all).
                   Case-insensitive: 'PAID', 'Paid', 'paid' all work.
                   Invalid values return error with INVALID_PAGE_TYPE code.

    Returns:
        Dict with send types grouped by category and full field set.

    Response Schema:
        {
            "by_category": {
                "revenue": [{...48 fields...}, ...],
                "engagement": [{...48 fields...}, ...],
                "retention": [{...48 fields...}, ...]
            },
            "all_send_type_keys": ["ppv_unlock", "bump_normal", ...],
            "counts": {"revenue": 9, "engagement": 9, "retention": 4, "total": 22},
            "page_type_filter": "paid" | "free" | null,
            "metadata": {
                "fetched_at": "ISO timestamp",
                "tool_version": "2.0.0",
                "source": "cache" | "database",
                "cached_at": "ISO timestamp" | null,
                "types_hash": "12-char hash for ValidationCertificate"
            }
        }

    Error Response:
        Same schema with error/error_code fields and empty by_category.
        Error codes: INVALID_PAGE_TYPE, INTERNAL_ERROR

    Excluded Columns (internal lifecycle):
        schema_version, created_at, updated_at, deprecated_at, replacement_send_type_id

    Example:
        get_send_types(page_type="paid")
        # Returns full details for paid pages (excludes free-only types)
    """
    logger.info(f"get_send_types: page_type={page_type}")

    try:
        # =========================================================================
        # INPUT VALIDATION: Case-normalize, then fail-fast on invalid
        # =========================================================================
        original_page_type = page_type
        if page_type is not None:
            page_type = str(page_type).lower().strip()
            if page_type not in ('paid', 'free'):
                return _build_send_types_error_response(
                    error_code="INVALID_PAGE_TYPE",
                    error_message=f"Invalid page_type: '{original_page_type}'. Valid values: 'paid', 'free', or null",
                    page_type_filter=original_page_type
                )

        # =========================================================================
        # FETCH FROM CACHE (lazy-load full cache on first call)
        # =========================================================================
        cache_hit = _is_send_types_full_cache_populated()
        cache = _get_send_types_full_cache()
        cache_meta = _get_send_types_cache_meta()  # Reuse constraint cache metadata for hash

        # Convert cache dict to ordered list
        all_types = list(cache.values())

        # =========================================================================
        # FILTER BY PAGE TYPE
        # =========================================================================
        if page_type == 'free':
            types = [t for t in all_types if t['page_type_restriction'] in ('both', 'free')]
        elif page_type == 'paid':
            types = [t for t in all_types if t['page_type_restriction'] in ('both', 'paid')]
        else:
            types = all_types

        # =========================================================================
        # GROUP BY CATEGORY
        # =========================================================================
        by_category = {
            "revenue": [],
            "engagement": [],
            "retention": []
        }
        for t in types:
            cat = t.get('category', 'engagement').lower()
            if cat in by_category:
                by_category[cat].append(t)

        # =========================================================================
        # BUILD RESPONSE
        # =========================================================================
        all_keys = [t['send_type_key'] for t in types]

        return {
            "by_category": by_category,
            "all_send_type_keys": all_keys,
            "counts": {
                "revenue": len(by_category["revenue"]),
                "engagement": len(by_category["engagement"]),
                "retention": len(by_category["retention"]),
                "total": len(types)
            },
            "page_type_filter": page_type,
            "metadata": {
                "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "tool_version": "2.0.0",
                "source": "cache" if cache_hit else "database",
                "cached_at": cache_meta.get("cached_at") if cache_hit else None,
                "types_hash": cache_meta.get("types_hash")
            }
        }

    except Exception as e:
        logger.error(f"get_send_types error: {e}")
        return _build_send_types_error_response(
            error_code="INTERNAL_ERROR",
            error_message=str(e),
            page_type_filter=page_type
        )
```

**Verification:**
```bash
python3 -c "
import sys
sys.path.insert(0, '/Users/kylemerriman/Developer/eros-sd-skill-package')
from mcp_server import main
# Clear caches
main._SEND_TYPES_CACHE.clear()
main._SEND_TYPES_CACHE_META.clear()
main._SEND_TYPES_FULL_CACHE.clear()

from mcp_server.main import get_send_types
result = get_send_types()

# Verify response structure
assert 'by_category' in result, 'Missing by_category'
assert 'all_send_type_keys' in result, 'Missing all_send_type_keys'
assert 'counts' in result, 'Missing counts'
assert 'metadata' in result, 'Missing metadata'
assert 'send_types' not in result, 'Old send_types array should be removed'

# Verify metadata
assert result['metadata']['tool_version'] == '2.0.0', 'Version mismatch'
print(f'Response verified: {len(result[\"all_send_type_keys\"])} types')
"
```

**Commit:** `refactor(get_send_types): v2.0.0 with cache, validation, structured response`

---

### Phase 3: Add Tests

**Files Created:** `python/tests/test_send_types.py`

```python
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

        # Constraints cache should still be empty
        assert len(main._SEND_TYPES_CACHE) == 0
        # Full cache should be populated
        assert len(main._SEND_TYPES_FULL_CACHE) > 0


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
        """Internal lifecycle columns should NOT be in response."""
        from mcp_server.main import get_send_types
        result = get_send_types()

        excluded_fields = ['schema_version', 'created_at', 'updated_at', 'deprecated_at', 'replacement_send_type_id']

        for category in result['by_category'].values():
            for send_type in category:
                for field in excluded_fields:
                    assert field not in send_type, f"Internal field should be excluded: {field}"
```

**Verification:**
```bash
python3 -m pytest python/tests/test_send_types.py -v
```

**Commit:** `test(get_send_types): add comprehensive v2.0.0 tests`

---

### Phase 4: Update Documentation

**Files Modified:** `docs/MCP_SETUP_GUIDE.md`

Update the get_send_types entry in the tool documentation to reflect v2.0.0 changes:

**Before:**
```markdown
| `get_send_types` | ~14,600 | 53 | Full details (rare) |
```

**After:**
```markdown
| `get_send_types` | ~8,000 | 48 | Full details (rare, v2.0.0) |
```

**Note:** Token count reduced due to removal of redundant `send_types` array.

**Commit:** `docs(mcp): update get_send_types v2.0.0 token estimate`

---

## 4. Verification Commands

### Pre-Refactor Baseline
```bash
# Capture baseline commit
BASELINE=$(git rev-parse --short HEAD)
echo "Baseline: $BASELINE"

# Run existing tests to ensure clean state
python3 -m pytest python/tests/ -q
```

### Post-Phase Verification
```bash
# After each phase, verify tests pass
python3 -m pytest python/tests/test_send_types.py -v

# Verify cache interaction
python3 -c "
import sys
sys.path.insert(0, '/Users/kylemerriman/Developer/eros-sd-skill-package')
from mcp_server import main
main._SEND_TYPES_CACHE.clear()
main._SEND_TYPES_CACHE_META.clear()
main._SEND_TYPES_FULL_CACHE.clear()

from mcp_server.main import get_send_types_constraints, get_send_types

# Constraints should use lightweight cache
r1 = get_send_types_constraints()
print(f'Constraints cache: {len(main._SEND_TYPES_CACHE)} items')
print(f'Full cache: {len(main._SEND_TYPES_FULL_CACHE)} items')

# Full should use separate cache
r2 = get_send_types()
print(f'After full - Constraints cache: {len(main._SEND_TYPES_CACHE)} items')
print(f'After full - Full cache: {len(main._SEND_TYPES_FULL_CACHE)} items')
"
```

### Rollback Command
```bash
# If needed, rollback to baseline
git reset --hard $BASELINE
```

---

## 5. Success Criteria

- [ ] Phase 1: Cache infrastructure added, column constant defined (48 columns)
- [ ] Phase 2: get_send_types refactored with v2.0.0 response schema
- [ ] Phase 3: All tests pass (input validation, caching, response schema)
- [ ] Phase 4: Documentation updated
- [ ] Breaking change documented in docstring
- [ ] Constraints cache unchanged (still 9 fields)
- [ ] Full cache lazy-loaded only when get_send_types called

---

<promise>SPEC_DONE</promise>
