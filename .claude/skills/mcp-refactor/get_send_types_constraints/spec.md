# get_send_types_constraints Refactoring Specification

**Version:** 2.0.0 | **Created:** 2026-01-13 | **Status:** Ready for Execution

---

## Executive Summary

Refactor `get_send_types_constraints` from a simple config lookup to a production-grade MCP tool with:
- Case-normalizing input validation with fail-fast on truly invalid values
- Optimized response: `by_category` only (no flat array duplication)
- Shared module-level cache with `validate_caption_structure`
- Targeted metadata for caching observability and pipeline integrity

**Estimated Phases:** 3 | **Breaking Changes:** Yes (response schema) | **New Tests:** 6

---

## Response Schema Change (BREAKING)

### Before (v1.x)
```json
{
  "send_types": [22 items],           // REMOVED - redundant
  "by_category": {...},
  "total": 22,
  "page_type_filter": "paid",
  "fields_returned": 9,               // REMOVED - not useful
  "_optimization_note": "..."         // REMOVED - not useful
}
```

### After (v2.0)
```json
{
  "by_category": {
    "revenue": [...],
    "engagement": [...],
    "retention": [...]
  },
  "all_send_type_keys": ["ppv_unlock", "bump_normal", ...],
  "counts": {
    "revenue": 9,
    "engagement": 9,
    "retention": 4,
    "total": 22
  },
  "page_type_filter": "paid" | "free" | null,
  "metadata": {
    "fetched_at": "2026-01-13T14:23:07Z",
    "tool_version": "2.0.0",
    "source": "cache" | "database",
    "cached_at": "2026-01-13T14:20:00Z",
    "types_hash": "a3f2b1..."
  }
}
```

---

## Phase 1: Shared Cache Infrastructure + Input Validation

### Objective
Add shared module-level cache for send_types (used by both `get_send_types_constraints` and `validate_caption_structure`) and case-normalizing input validation.

### 1A: Add Shared Cache Infrastructure

**Location:** Near top of main.py, after existing module-level variables

**Add:**
```python
# ============================================================
# SHARED CACHES (Module-level, session lifetime)
# ============================================================

# Shared send_types cache - used by get_send_types_constraints and validate_caption_structure
_SEND_TYPES_CACHE: dict[str, Any] = {}

def _get_cached_send_types_full() -> tuple[list[dict], str, str]:
    """
    Get all active send_types from cache or database.

    Returns:
        Tuple of (types_list, cached_at_iso, types_hash)
    """
    if 'all_types' not in _SEND_TYPES_CACHE:
        # Select ALL columns since validate_caption_structure needs category lookup
        types = db_query("""
            SELECT *
            FROM send_types
            WHERE is_active = 1
            ORDER BY category, sort_order
        """, tuple())

        # Compute hash of send_type_keys for pipeline integrity
        import hashlib
        keys_str = ','.join(sorted(t['send_type_key'] for t in types))
        types_hash = hashlib.sha256(keys_str.encode()).hexdigest()[:12]

        _SEND_TYPES_CACHE['all_types'] = types
        _SEND_TYPES_CACHE['cached_at'] = datetime.utcnow().isoformat() + "Z"
        _SEND_TYPES_CACHE['types_hash'] = types_hash

    return (
        _SEND_TYPES_CACHE['all_types'],
        _SEND_TYPES_CACHE['cached_at'],
        _SEND_TYPES_CACHE['types_hash']
    )


def _get_cached_send_types_constraints_only() -> tuple[list[dict], str, str]:
    """
    Get send_types with only constraint fields (9 columns).
    Filters from full cache to maintain single source of truth.

    Returns:
        Tuple of (constraint_types_list, cached_at_iso, types_hash)
    """
    full_types, cached_at, types_hash = _get_cached_send_types_full()

    # Project to constraint fields only
    constraint_fields = [
        'send_type_key', 'category', 'page_type_restriction',
        'max_per_day', 'max_per_week', 'min_hours_between',
        'requires_media', 'requires_price', 'requires_flyer'
    ]

    constraints = [
        {k: t[k] for k in constraint_fields}
        for t in full_types
    ]

    return constraints, cached_at, types_hash
```

### 1B: Add Error Response Helper

**Location:** Before `get_send_types_constraints` function

**Add:**
```python
def _build_send_types_error_response(
    error_code: str,
    error_message: str,
    page_type_filter: str = None
) -> dict:
    """Build consistent error response for send_types constraints."""
    return {
        "error": error_message,
        "error_code": error_code,
        "by_category": {"revenue": [], "engagement": [], "retention": []},
        "all_send_type_keys": [],
        "counts": {"revenue": 0, "engagement": 0, "retention": 0, "total": 0},
        "page_type_filter": page_type_filter,
        "metadata": {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "tool_version": "2.0.0",
            "source": "error",
            "error": True
        }
    }
```

### 1C: Update Function with Validation

**Replace:** Lines 3805-3830 (from logger.info through query execution)

**Before:**
```python
    logger.info(f"get_send_types_constraints: page_type={page_type}")
    try:
        # Select ONLY the 9 essential fields for schedule generation
        query = """
            SELECT
                send_type_key,
                category,
                ...
        """

        if page_type == 'free':
            query += " AND page_type_restriction IN ('both', 'free')"
        elif page_type == 'paid':
            query += " AND page_type_restriction IN ('both', 'paid')"

        query += " ORDER BY category, sort_order"

        types = db_query(query, tuple())
```

**After:**
```python
    logger.info(f"get_send_types_constraints: page_type={page_type}")

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
        # FETCH FROM CACHE (or populate cache on first call)
        # =========================================================================
        cache_hit = 'all_types' in _SEND_TYPES_CACHE
        constraints, cached_at, types_hash = _get_cached_send_types_constraints_only()

        # =========================================================================
        # FILTER BY PAGE TYPE
        # =========================================================================
        if page_type == 'free':
            types = [t for t in constraints if t['page_type_restriction'] in ('both', 'free')]
        elif page_type == 'paid':
            types = [t for t in constraints if t['page_type_restriction'] in ('both', 'paid')]
        else:
            types = constraints
```

### Success Criteria (Phase 1)
- [ ] `_SEND_TYPES_CACHE` module-level dict added
- [ ] `_get_cached_send_types_full()` function added
- [ ] `_get_cached_send_types_constraints_only()` function added
- [ ] `_build_send_types_error_response()` helper added
- [ ] Case normalization: 'PAID' → 'paid', 'Free' → 'free'
- [ ] Invalid page_type returns error with error_code
- [ ] Cache hit tracked for metadata

### Commit Message
```
refactor(get_send_types_constraints): add shared cache and input validation v2.0.0

- Add _SEND_TYPES_CACHE shared with validate_caption_structure
- Add _get_cached_send_types_full() for session-lifetime caching
- Add _get_cached_send_types_constraints_only() for projection
- Add case-normalizing input validation (PAID → paid)
- Fail-fast with INVALID_PAGE_TYPE error_code for invalid values
- Add _build_send_types_error_response() helper for consistent errors
```

---

## Phase 2: Response Schema Optimization

### Objective
Replace duplicated send_types/by_category with optimized structure: by_category only + convenience fields.

### Replace Return Statement

**Replace:** Lines 3832-3850 (by_category grouping through return)

**Before:**
```python
        # Group by category for easy lookup
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
            "page_type_filter": page_type,
            "fields_returned": 9,
            "_optimization_note": "Lightweight view (9 fields vs 53). Use get_send_types for full details."
        }
```

**After:**
```python
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
                "fetched_at": datetime.utcnow().isoformat() + "Z",
                "tool_version": "2.0.0",
                "source": "cache" if cache_hit else "database",
                "cached_at": cached_at if cache_hit else None,
                "types_hash": types_hash
            }
        }
```

### Update Error Handler Return

**Replace:** Lines 3852-3854 (error return)

**Before:**
```python
    except Exception as e:
        logger.error(f"get_send_types_constraints error: {e}")
        return {"error": str(e), "send_types": []}
```

**After:**
```python
    except Exception as e:
        logger.error(f"get_send_types_constraints error: {e}")
        return _build_send_types_error_response(
            error_code="INTERNAL_ERROR",
            error_message=str(e),
            page_type_filter=page_type
        )
```

### Success Criteria (Phase 2)
- [ ] `send_types` array REMOVED from response
- [ ] `all_send_type_keys` array ADDED (just keys, not full objects)
- [ ] `counts` dict ADDED with per-category and total counts
- [ ] `metadata` block ADDED with fetched_at, tool_version, source, cached_at, types_hash
- [ ] `fields_returned` REMOVED
- [ ] `_optimization_note` REMOVED
- [ ] Error handler uses `_build_send_types_error_response()`

### Commit Message
```
feat(get_send_types_constraints): optimize response schema v2.0.0

BREAKING CHANGE: Response schema changed
- Remove send_types array (redundant with by_category)
- Add all_send_type_keys for quick validation (~200 chars vs ~3k)
- Add counts dict with per-category breakdown
- Add metadata block: fetched_at, tool_version, source, cached_at, types_hash
- Remove fields_returned and _optimization_note (not useful)
- Response ~43% smaller: ~3.5k chars vs ~6k chars
```

---

## Phase 3: Update Docstring and Add Tests

### Objective
Update function documentation and create comprehensive test suite.

### Update Docstring

**Replace:** Lines 3786-3804 (entire docstring)

**Before:**
```python
    """Returns minimal send type constraints for schedule generation.

    MCP Name: mcp__eros-db__get_send_types_constraints

    This is the PREFERRED tool for schedule generation. Returns only 9 essential
    fields instead of 53, reducing response from ~34k chars to ~6k chars (~80% reduction).

    Use full get_send_types() only when you need description, strategy, weights,
    channel configs, or other detailed fields.

    Args:
        page_type: Optional filter ('paid' or 'free')

    Returns:
        Minimal send type data with scheduling constraints only:
        - send_type_key, category, page_type_restriction
        - max_per_day, max_per_week, min_hours_between
        - requires_media, requires_price, requires_flyer
    """
```

**After:**
```python
    """Returns minimal send type constraints for schedule generation.

    MCP Name: mcp__eros-db__get_send_types_constraints
    Version: 2.0.0

    This is the PREFERRED tool for schedule generation. Returns only 9 essential
    constraint fields per send type, grouped by category for efficient allocation.

    Results are cached at module level for session lifetime. Use get_send_types()
    only when you need description, strategy, weights, or channel configs.

    Args:
        page_type: Optional filter ('paid', 'free', or None for all).
                   Case-insensitive: 'PAID', 'Paid', 'paid' all work.
                   Invalid values return error with INVALID_PAGE_TYPE code.

    Returns:
        Dict with send types grouped by category and convenience fields.

    Response Schema:
        {
            "by_category": {
                "revenue": [{send_type_key, category, page_type_restriction,
                            max_per_day, max_per_week, min_hours_between,
                            requires_media, requires_price, requires_flyer}, ...],
                "engagement": [...],
                "retention": [...]
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

    Example:
        get_send_types_constraints(page_type="paid")
        # Returns constraints for paid pages (excludes free-only types like ppv_wall)
    """
```

### Create Test File

**Create:** `/Users/kylemerriman/Developer/eros-sd-skill-package/python/tests/test_send_types_constraints.py`

```python
"""Tests for get_send_types_constraints MCP tool v2.0.0."""

import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Insert project root for imports
sys.path.insert(0, '/Users/kylemerriman/Developer/eros-sd-skill-package')


# Mock send_types data matching production schema
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
    yield
    main._SEND_TYPES_CACHE.clear()


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
        """Invalid page_type should return error with code."""
        from mcp_server.main import get_send_types_constraints
        result = get_send_types_constraints(page_type='invalid_value')

        assert 'error' in result
        assert result['error_code'] == 'INVALID_PAGE_TYPE'
        assert 'invalid_value' in result['error']
        assert result['by_category'] == {"revenue": [], "engagement": [], "retention": []}
        assert result['counts']['total'] == 0


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

        result = get_send_types_constraints()

        assert 'all_types' in main._SEND_TYPES_CACHE
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
```

### Success Criteria (Phase 3)
- [ ] Docstring updated with v2.0.0 version marker
- [ ] Full response schema documented in docstring
- [ ] Error codes documented
- [ ] Example provided
- [ ] Test file created at python/tests/test_send_types_constraints.py
- [ ] All 6 test classes pass
- [ ] Tests cover: validation, response schema, caching

### Commit Message
```
docs(get_send_types_constraints): update docstring and add tests v2.0.0

- Add version 2.0.0 marker to docstring
- Document full response schema including metadata
- Document error codes: INVALID_PAGE_TYPE, INTERNAL_ERROR
- Add usage example
- Create test_send_types_constraints.py with 10 test cases
- Test coverage: input validation, response schema, caching behavior
```

---

## Migration Notes for Consumers

### schedule-generator.md
The schedule-generator uses `by_category` grouping for allocation, so the schema change should be transparent. However:

1. **Response field removed:** `send_types` array no longer present
   - **Action:** If code iterates `send_types`, use `all_send_type_keys` or flatten `by_category`

2. **New convenience fields:**
   - `all_send_type_keys`: Quick list of keys for validation
   - `counts`: Per-category counts without iterating

3. **Metadata available:**
   - `types_hash`: Can include in ValidationCertificate for audit

### preflight.py
The MCPClient protocol stub needs no changes - it already expects dict return.

---

## Rollback Plan

If any phase fails:
```bash
# Revert single phase
git revert HEAD

# Revert all phases
git reset --hard $BASELINE_COMMIT
```

Baseline commit will be captured before Phase 1 execution.

---

## Verification Checklist (All Phases)

- [ ] All new tests pass: `pytest python/tests/test_send_types_constraints.py -v`
- [ ] Existing tests pass: `pytest python/tests/ -v`
- [ ] Manual verification with real data:
  ```
  mcp__eros-db__get_send_types_constraints(page_type="paid")
  mcp__eros-db__get_send_types_constraints(page_type="PAID")
  mcp__eros-db__get_send_types_constraints(page_type="invalid")
  ```
- [ ] Response size reduced (~3.5k vs ~6k chars)
- [ ] Cache behavior verified (second call faster, source="cache")
- [ ] types_hash consistent across filtered/unfiltered calls

---

## LEARNINGS.md Update

After successful completion, add:

```markdown
### [2026-01-13] Shared Module-Level Cache Pattern for Config Tables
**Pattern**: Config tables (send_types) cached at module level, shared between tools
**Insight**: Single cache population serves multiple tools; project from full cache for variants
**Source**: refactor | **Sample Size**: 2 (get_send_types_constraints v2.0, validate_caption_structure v2.0)
**Applies To**: all
**Implementation**: `_get_cached_send_types_full()` returns all columns, tool-specific functions project
**Promote When**: Pattern reused in 3+ tools (PROMOTE from LOW → MEDIUM)
```

---

**SPEC_DONE**
