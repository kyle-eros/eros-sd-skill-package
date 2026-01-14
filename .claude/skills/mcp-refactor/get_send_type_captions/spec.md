# get_send_type_captions Refactoring Specification

**Version:** 2.0.0 | **Created:** 2026-01-13 | **Status:** Ready for Execution

---

## Executive Summary

Refactor `get_send_type_captions` from a simple caption retrieval tool to a production-grade MCP tool with:
- Four-layer validation (creator + send_type)
- Per-creator freshness filtering via caption_creator_performance JOIN
- Pool statistics for agent decision quality
- Consistent error handling via `_build_caption_error_response()`
- Dead code removal (category fallback that never worked)

**Estimated Phases:** 4 | **Breaking Changes:** No (additive only) | **New Tests:** 8

---

## Phase 1: Four-Layer Validation

### Objective
Add type/format/resolution/normalization validation before query execution.

### Before (Lines 3259-3261)
```python
logger.info(f"get_send_type_captions: creator_id={creator_id}, send_type={send_type}")
try:
    limit = min(max(1, limit), 50)
```

### After
```python
logger.info(f"get_send_type_captions: creator_id={creator_id}, send_type={send_type}")

# =========================================================================
# LAYER 1: Type validation
# =========================================================================
if not creator_id or not isinstance(creator_id, str):
    return _build_send_type_error_response(
        "INVALID_CREATOR_ID",
        "creator_id must be a non-empty string",
        send_type
    )

if not send_type or not isinstance(send_type, str):
    return _build_send_type_error_response(
        "INVALID_SEND_TYPE",
        "send_type must be a non-empty string",
        send_type
    )

# =========================================================================
# LAYER 2: Format validation
# =========================================================================
is_valid, validation_result = validate_creator_id(creator_id)
if not is_valid:
    return _build_send_type_error_response(
        "INVALID_CREATOR_ID_FORMAT",
        validation_result,
        send_type
    )

if len(send_type) > 50 or not send_type.replace('_', '').isalnum():
    return _build_send_type_error_response(
        "INVALID_SEND_TYPE_FORMAT",
        "send_type must be alphanumeric with underscores, max 50 chars",
        send_type
    )

# =========================================================================
# LAYER 3: Resolution
# =========================================================================
resolved = resolve_creator_id(creator_id)
if not resolved["found"]:
    return _build_send_type_error_response(
        "CREATOR_NOT_FOUND",
        f"Creator not found: {creator_id}",
        send_type
    )
resolved_creator_id = resolved["creator_id"]

# Validate send_type exists in send_types table
send_type_check = db_query(
    "SELECT 1 FROM send_types WHERE send_type_key = ? AND is_active = 1 LIMIT 1",
    (send_type,)
)
if not send_type_check:
    valid_types = db_query(
        "SELECT send_type_key FROM send_types WHERE is_active = 1 ORDER BY sort_order LIMIT 30"
    )
    valid_list = [r["send_type_key"] for r in valid_types]
    return _build_send_type_error_response(
        "SEND_TYPE_NOT_FOUND",
        f"send_type '{send_type}' not found. Valid types: {', '.join(valid_list[:10])}...",
        send_type
    )

# =========================================================================
# LAYER 4: Normalize
# =========================================================================
limit = max(1, min(50, limit))

try:
    # ... main query logic
```

### Helper Function to Add (before get_send_type_captions)
```python
def _build_send_type_error_response(
    error_code: str,
    error_message: str,
    send_type: str
) -> dict:
    """Build consistent error response for send_type caption retrieval."""
    return {
        "error": error_message,
        "error_code": error_code,
        "creator_id": None,
        "send_type": send_type,
        "captions": [],
        "pool_stats": None,
        "count": 0,
        "metadata": {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "error": True
        }
    }
```

### Success Criteria
- [ ] Layer 1-4 validation added
- [ ] `_build_send_type_error_response` helper created
- [ ] resolve_creator_id called and used
- [ ] send_type validated against send_types table
- [ ] All validation returns structured error with error_code

### Commit Message
```
refactor(get_send_type_captions): add four-layer validation v2.0.0

- Add Layer 1: type validation (creator_id, send_type strings)
- Add Layer 2: format validation (creator format, send_type pattern)
- Add Layer 3: resolution (creator lookup, send_type existence check)
- Add Layer 4: normalization (limit clamping)
- Add _build_send_type_error_response helper for consistent errors
- Follows mcp_best_practices.md Section 2 four-layer defense pattern
```

---

## Phase 2: Remove Dead Code (Category Fallback)

### Objective
Delete category_map and fallback logic that never matched any data.

### Before (Lines 3263-3296)
```python
        # Map send types to caption categories (for fallback only)
        category_map = {
            'ppv_unlock': 'ppv',
            'ppv_wall': 'ppv',
            'ppv_followup': 'followup',
            'bump_normal': 'bump',
            'bump_descriptive': 'bump',
            'bump_text_only': 'bump',
            'bump_flyer': 'bump',
            'tip_goal': 'tip',
            'renew_on_post': 'renewal',
            'renew_on_message': 'renewal',
            'expired_winback': 'winback',
            'link_drop': 'promo',
            'dm_farm': 'engagement'
        }
        category = category_map.get(send_type, 'general')

        # Query caption_bank (actual table name)
        # Priority: 1) Exact send_type match, 2) Category fallback, 3) General captions
        captions = db_query("""
            SELECT caption_id, caption_text, caption_type as category,
                   performance_tier as quality_score, content_type_id,
                   global_last_used_date as last_used_at
            FROM caption_bank
            WHERE (caption_type = ? OR caption_type = ? OR caption_type = 'general')
            AND is_active = 1
            ORDER BY
                CASE WHEN caption_type = ? THEN 0
                     WHEN caption_type = ? THEN 1
                     ELSE 2 END,
                performance_tier ASC
            LIMIT ?
        """, (send_type, category, send_type, category, limit))
```

### After
```python
        # Query caption_bank - exact send_type match only
        # Note: Category fallback removed in v2.0.0 - data shows caption_type
        # stores send_type_keys directly, not generic categories
        captions = db_query("""
            SELECT caption_id, caption_text, caption_type as category,
                   performance_tier as quality_score, content_type_id,
                   global_last_used_date as last_used_at
            FROM caption_bank
            WHERE caption_type = ?
            AND is_active = 1
            ORDER BY performance_tier ASC, global_last_used_date ASC NULLS FIRST
            LIMIT ?
        """, (send_type, limit))

        # Log warning if no captions found for monitoring
        if not captions:
            logger.warning(f"No captions found for send_type={send_type}")
```

### Success Criteria
- [ ] category_map dictionary deleted
- [ ] category variable deleted
- [ ] SQL simplified to single WHERE caption_type = ?
- [ ] ORDER BY simplified (removed CASE expression)
- [ ] Warning logged for empty results
- [ ] No references to 'general' fallback

### Commit Message
```
refactor(get_send_type_captions): remove dead category fallback code

- Delete category_map (never matched data - caption_type stores send_type_keys)
- Simplify SQL to exact send_type match only
- Remove 'general' fallback (no captions with this type exist)
- Add warning log for monitoring empty results
- Dead code confirmed by data: 20 caption_types all match send_type_keys
```

---

## Phase 3: Add Per-Creator Freshness Filtering

### Objective
JOIN caption_creator_performance to prioritize captions not recently used by THIS creator.

### Before (from Phase 2)
```python
        captions = db_query("""
            SELECT caption_id, caption_text, caption_type as category,
                   performance_tier as quality_score, content_type_id,
                   global_last_used_date as last_used_at
            FROM caption_bank
            WHERE caption_type = ?
            AND is_active = 1
            ORDER BY performance_tier ASC, global_last_used_date ASC NULLS FIRST
            LIMIT ?
        """, (send_type, limit))
```

### After
```python
        # Calculate freshness threshold (90 days = effectively fresh)
        from datetime import date, timedelta
        freshness_threshold = (date.today() - timedelta(days=90)).isoformat()

        captions = db_query("""
            SELECT
                cb.caption_id,
                cb.caption_text,
                cb.caption_type as category,
                cb.performance_tier,
                cb.content_type_id,
                cb.global_last_used_date as global_last_used_at,
                ccp.last_used_date as creator_last_used_at,
                COALESCE(ccp.times_used, 0) as creator_use_count,
                CASE
                    WHEN ccp.last_used_date IS NULL THEN NULL
                    ELSE CAST(julianday('now') - julianday(ccp.last_used_date) AS INTEGER)
                END as days_since_creator_used,
                CASE
                    WHEN ccp.last_used_date IS NULL THEN 1
                    WHEN ccp.last_used_date < ? THEN 1
                    ELSE 0
                END as effectively_fresh
            FROM caption_bank cb
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id
                AND ccp.creator_id = ?
            WHERE cb.caption_type = ?
            AND cb.is_active = 1
            ORDER BY
                effectively_fresh DESC,          -- Fresh captions first
                ccp.last_used_date ASC NULLS FIRST,  -- Never used by creator first
                cb.performance_tier ASC,         -- Best quality
                cb.global_last_used_date ASC NULLS FIRST  -- Globally fresh
            LIMIT ?
        """, (freshness_threshold, resolved_creator_id, send_type, limit))

        # Log warning if no captions found for monitoring
        if not captions:
            logger.warning(f"No captions found for send_type={send_type}, creator={resolved_creator_id}")
```

### Success Criteria
- [ ] LEFT JOIN caption_creator_performance added
- [ ] resolved_creator_id used in JOIN condition
- [ ] creator_last_used_at, creator_use_count, days_since_creator_used fields added
- [ ] effectively_fresh calculated (90 days threshold)
- [ ] ORDER BY prioritizes: fresh → never-used → performance → global freshness
- [ ] freshness_threshold calculated correctly

### Commit Message
```
feat(get_send_type_captions): add per-creator freshness filtering

- JOIN caption_creator_performance for per-creator usage tracking
- Add fields: creator_last_used_at, creator_use_count, days_since_creator_used
- Add effectively_fresh flag (90+ days or never used = fresh)
- ORDER BY: fresh → never-used-by-creator → performance → global-freshness
- Matches get_batch_captions_by_content_types v2.0 freshness pattern
```

---

## Phase 4: Add Pool Statistics & Metadata

### Objective
Add pool_stats CTE and metadata block for agent decision quality and debugging.

### Before (from Phase 3)
```python
        captions = db_query("""
            SELECT
                cb.caption_id,
                ...
            LIMIT ?
        """, (freshness_threshold, resolved_creator_id, send_type, limit))

        if not captions:
            logger.warning(...)

        return {
            "creator_id": creator_id,
            "send_type": send_type,
            "category_matched": category,
            "captions": captions,
            "count": len(captions)
        }
```

### After
```python
        start_time = time.perf_counter()

        # Calculate freshness threshold (90 days = effectively fresh)
        from datetime import date, timedelta
        freshness_threshold = (date.today() - timedelta(days=90)).isoformat()

        # Get pool statistics first
        pool_stats_result = db_query("""
            SELECT
                COUNT(*) as total_available,
                SUM(CASE
                    WHEN ccp.last_used_date IS NULL THEN 1
                    WHEN ccp.last_used_date < ? THEN 1
                    ELSE 0
                END) as fresh_for_creator,
                AVG(cb.performance_tier) as avg_pool_performance_tier
            FROM caption_bank cb
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id
                AND ccp.creator_id = ?
            WHERE cb.caption_type = ?
            AND cb.is_active = 1
        """, (freshness_threshold, resolved_creator_id, send_type))

        pool = pool_stats_result[0] if pool_stats_result else {
            "total_available": 0, "fresh_for_creator": 0, "avg_pool_performance_tier": None
        }

        # Get captions with freshness fields
        captions = db_query("""
            SELECT
                cb.caption_id,
                cb.caption_text,
                cb.caption_type as category,
                cb.performance_tier,
                cb.content_type_id,
                cb.global_last_used_date as global_last_used_at,
                ccp.last_used_date as creator_last_used_at,
                COALESCE(ccp.times_used, 0) as creator_use_count,
                CASE
                    WHEN ccp.last_used_date IS NULL THEN NULL
                    ELSE CAST(julianday('now') - julianday(ccp.last_used_date) AS INTEGER)
                END as days_since_creator_used,
                CASE
                    WHEN ccp.last_used_date IS NULL THEN 1
                    WHEN ccp.last_used_date < ? THEN 1
                    ELSE 0
                END as effectively_fresh
            FROM caption_bank cb
            LEFT JOIN caption_creator_performance ccp
                ON cb.caption_id = ccp.caption_id
                AND ccp.creator_id = ?
            WHERE cb.caption_type = ?
            AND cb.is_active = 1
            ORDER BY
                effectively_fresh DESC,
                ccp.last_used_date ASC NULLS FIRST,
                cb.performance_tier ASC,
                cb.global_last_used_date ASC NULLS FIRST
            LIMIT ?
        """, (freshness_threshold, resolved_creator_id, send_type, limit))

        # Log warning if no captions found for monitoring
        if not captions:
            logger.warning(f"No captions found for send_type={send_type}, creator={resolved_creator_id}")

        query_ms = (time.perf_counter() - start_time) * 1000
        total_available = pool.get("total_available", 0) or 0
        fresh_for_creator = pool.get("fresh_for_creator", 0) or 0

        return {
            "creator_id": creator_id,
            "resolved_creator_id": resolved_creator_id,
            "send_type": send_type,
            "captions": captions,
            "count": len(captions),
            "pool_stats": {
                "total_available": total_available,
                "fresh_for_creator": fresh_for_creator,
                "returned_count": len(captions),
                "has_more": total_available > len(captions),
                "avg_pool_performance_tier": pool.get("avg_pool_performance_tier"),
                "freshness_ratio": round(fresh_for_creator / total_available, 3) if total_available > 0 else None
            },
            "metadata": {
                "fetched_at": datetime.utcnow().isoformat() + "Z",
                "query_ms": round(query_ms, 2),
                "tool_version": "2.0.0",
                "freshness_threshold_days": 90
            }
        }
```

### Update Error Handler Return Schema
Update `_build_send_type_error_response` to match success schema with pool_stats:
```python
def _build_send_type_error_response(
    error_code: str,
    error_message: str,
    send_type: str
) -> dict:
    """Build consistent error response for send_type caption retrieval."""
    return {
        "error": error_message,
        "error_code": error_code,
        "creator_id": None,
        "resolved_creator_id": None,
        "send_type": send_type,
        "captions": [],
        "count": 0,
        "pool_stats": {
            "total_available": 0,
            "fresh_for_creator": 0,
            "returned_count": 0,
            "has_more": False,
            "avg_pool_performance_tier": None,
            "freshness_ratio": None
        },
        "metadata": {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "error": True
        }
    }
```

### Success Criteria
- [ ] pool_stats CTE query added
- [ ] pool_stats block in response with all fields
- [ ] metadata block with fetched_at, query_ms, tool_version
- [ ] freshness_ratio calculated (fresh/total)
- [ ] has_more flag set correctly
- [ ] Error response schema matches success schema
- [ ] start_time added for query_ms calculation
- [ ] time import present

### Commit Message
```
feat(get_send_type_captions): add pool_stats and metadata v2.0.0

- Add pool_stats: total_available, fresh_for_creator, freshness_ratio
- Add metadata: fetched_at, query_ms, tool_version
- Add has_more flag for pagination awareness
- Update _build_send_type_error_response to match success schema
- Matches get_batch_captions_by_content_types v2.0 response pattern
```

---

## Phase 5: Update Docstring & Type Hints

### Objective
Update function signature and docstring to reflect v2.0 changes.

### Before
```python
@mcp.tool()
def get_send_type_captions(creator_id: str, send_type: str, limit: int = 10) -> dict:
    """Retrieves captions compatible with a specific send type.

    MCP Name: mcp__eros-db__get_send_type_captions

    Args:
        creator_id: Creator identifier
        send_type: Send type key (e.g., 'ppv_unlock', 'bump_normal')
        limit: Maximum captions to return (max 50)

    Returns:
        List of compatible captions
    """
```

### After
```python
@mcp.tool()
def get_send_type_captions(creator_id: str, send_type: str, limit: int = 10) -> dict:
    """Retrieves captions for a specific send type with per-creator freshness filtering.

    MCP Name: mcp__eros-db__get_send_type_captions
    Version: 2.0.0

    Args:
        creator_id: Creator identifier (required for per-creator freshness)
        send_type: Send type key from send_types table (e.g., 'ppv_unlock', 'bump_normal')
        limit: Maximum captions to return (clamped 1-50, default 10)

    Returns:
        Dict with captions (including freshness fields), pool_stats, and metadata.

    Response Schema:
        {
            "creator_id": str,           # Original input
            "resolved_creator_id": str,  # Resolved PK from creators table
            "send_type": str,
            "captions": [                # Ordered by freshness → performance
                {
                    "caption_id": int,
                    "caption_text": str,
                    "category": str,     # Same as send_type (caption_type column)
                    "performance_tier": int,
                    "content_type_id": int,
                    "global_last_used_at": str|null,
                    "creator_last_used_at": str|null,
                    "creator_use_count": int,
                    "days_since_creator_used": int|null,
                    "effectively_fresh": int  # 1=fresh, 0=stale
                }
            ],
            "count": int,
            "pool_stats": {
                "total_available": int,
                "fresh_for_creator": int,
                "returned_count": int,
                "has_more": bool,
                "avg_pool_performance_tier": float|null,
                "freshness_ratio": float|null
            },
            "metadata": {
                "fetched_at": str,       # ISO timestamp
                "query_ms": float,
                "tool_version": str,
                "freshness_threshold_days": int
            }
        }

    Error Response:
        Same schema with error/error_code fields and empty captions.

    Example:
        get_send_type_captions(
            creator_id="alexia",
            send_type="bump_normal",
            limit=5
        )
        # Returns 5 freshest bump_normal captions for Alexia
    """
```

### Success Criteria
- [ ] Version: 2.0.0 in docstring
- [ ] Args updated (creator_id purpose, limit clamping)
- [ ] Full response schema documented
- [ ] Error response documented
- [ ] Example provided

### Commit Message
```
docs(get_send_type_captions): update docstring for v2.0.0

- Add version marker
- Document full response schema including pool_stats and metadata
- Document freshness fields in caption objects
- Add usage example
```

---

## Test Requirements

Create `/Users/kylemerriman/Developer/eros-sd-skill-package/python/tests/test_send_type_captions.py`:

### Test Cases
1. **test_valid_send_type_returns_captions** - Happy path
2. **test_invalid_creator_id_returns_error** - Layer 1 validation
3. **test_invalid_send_type_returns_error** - Layer 1 validation
4. **test_creator_not_found_returns_error** - Layer 3 validation
5. **test_send_type_not_in_table_returns_error** - Layer 3 validation
6. **test_per_creator_freshness_ordering** - Fresh captions first
7. **test_pool_stats_accuracy** - Pool statistics match query
8. **test_empty_result_returns_valid_schema** - Empty array, not error

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

- [ ] All tests pass: `pytest python/tests/test_send_type_captions.py -v`
- [ ] Existing tests pass: `pytest python/tests/ -v`
- [ ] No lint errors: `ruff check mcp_server/main.py`
- [ ] Manual verification with real data
- [ ] Response schema matches documentation
