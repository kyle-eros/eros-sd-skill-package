# get_send_types_constraints - Technical Review

**Generated:** 2026-01-13 | **Reviewer:** code-reviewer | **Status:** Interview Ready

---

## Quick Reference

| Attribute | Value |
|-----------|-------|
| File | mcp_server/main.py |
| Lines | 3785-3854 |
| Phase | Generator (schedule-generator primary consumer) |
| Data Sources | send_types |
| Issues | HIGH: 1 | MEDIUM: 3 | LOW: 2 |

---

## 1. Current Implementation

### 1.1 Signature
```python
@mcp.tool()
def get_send_types_constraints(page_type: str = None) -> dict:
```

### 1.2 Parameters
| Param | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| page_type | str | No | None | None - accepts any value |

### 1.3 Return Schema
```python
# Success:
{
    "send_types": list,           # Raw db_query results (9 fields each)
    "by_category": {              # Grouped by category
        "revenue": [...],
        "engagement": [...],
        "retention": [...]
    },
    "total": int,                 # Count of send_types
    "page_type_filter": str|None, # Echoed input
    "fields_returned": 9,         # Static value
    "_optimization_note": str     # Static hint
}

# Error:
{
    "error": str,
    "send_types": []
}
```

### 1.4 Source Code (Lines 3785-3854)
```python
@mcp.tool()
def get_send_types_constraints(page_type: str = None) -> dict:
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
    logger.info(f"get_send_types_constraints: page_type={page_type}")
    try:
        # Select ONLY the 9 essential fields for schedule generation
        query = """
            SELECT
                send_type_key,
                category,
                page_type_restriction,
                max_per_day,
                max_per_week,
                min_hours_between,
                requires_media,
                requires_price,
                requires_flyer
            FROM send_types
            WHERE is_active = 1
        """

        if page_type == 'free':
            query += " AND page_type_restriction IN ('both', 'free')"
        elif page_type == 'paid':
            query += " AND page_type_restriction IN ('both', 'paid')"

        query += " ORDER BY category, sort_order"

        types = db_query(query, tuple())

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

    except Exception as e:
        logger.error(f"get_send_types_constraints error: {e}")
        return {"error": str(e), "send_types": []}
```

---

## 2. Database Layer

### 2.1 Schema (send_types table - 53 columns)
```sql
-- Essential 9 fields selected by this tool:
send_type_key           TEXT     PRIMARY KEY
category                TEXT     NOT NULL  -- 'revenue', 'engagement', 'retention'
page_type_restriction   TEXT     NOT NULL  -- 'paid', 'free', 'both'
max_per_day             INTEGER
max_per_week            INTEGER
min_hours_between       INTEGER
requires_media          INTEGER  DEFAULT 0
requires_price          INTEGER  DEFAULT 0
requires_flyer          INTEGER  DEFAULT 0

-- Additional fields NOT returned (44 columns):
send_type_id, display_name, description, purpose, strategy,
requires_link, has_expiration, default_expiration_hours,
can_have_followup, followup_delay_minutes, caption_length,
emoji_recommendation, sort_order, is_active, created_at,
priority_score, allocation_weight, fatigue_score, fatigue_multiplier,
revenue_weight, engagement_weight, retention_weight, cooldown_category,
audience_segment, ab_test_eligible, current_experiment_id,
min_subscriber_tenure_days, deprecated_at, replacement_send_type_id,
schema_version, updated_at, primary_channel_key, secondary_channel_key,
primary_channel_weight, wall_delivery_page_type, wall_content_level,
supports_link_drop_promo, channel_distribution, hybrid_split, ...
```

### 2.2 Query Analysis
```sql
SELECT
    send_type_key, category, page_type_restriction,
    max_per_day, max_per_week, min_hours_between,
    requires_media, requires_price, requires_flyer
FROM send_types
WHERE is_active = 1
  [AND page_type_restriction IN ('both', 'paid|free')]
ORDER BY category, sort_order
```

### 2.3 Column Verification
| SQL Column | Schema Column | Match | Notes |
|------------|---------------|-------|-------|
| send_type_key | send_type_key | YES | TEXT PRIMARY KEY |
| category | category | YES | TEXT NOT NULL |
| page_type_restriction | page_type_restriction | YES | TEXT NOT NULL |
| max_per_day | max_per_day | YES | INTEGER |
| max_per_week | max_per_week | YES | INTEGER (often NULL) |
| min_hours_between | min_hours_between | YES | INTEGER |
| requires_media | requires_media | YES | INTEGER DEFAULT 0 |
| requires_price | requires_price | YES | INTEGER DEFAULT 0 |
| requires_flyer | requires_flyer | YES | INTEGER DEFAULT 0 |

**All columns verified present and correctly named.**

---

## 3. Pipeline Position

### 3.1 Flow
```
Preflight (CreatorContext built)
    ↓ Calls get_send_types_constraints for page_type filtering
schedule-generator (primary consumer)
    ↓ Uses constraints for send type selection
schedule-validator
    ↓ Validates against constraints
save_schedule
```

### 3.2 Dependencies
| Type | Items |
|------|-------|
| Tables | send_types |
| Upstream Tools | None (first call in generation) |
| Downstream | schedule-validator (checks max_per_day, min_hours_between) |

### 3.3 Consumers
1. **schedule-generator.md** (Line 36): "ALWAYS use `mcp__eros-db__get_send_types_constraints` instead of `get_send_types`"
2. **preflight.py** (Line 88): Protocol defines async wrapper for this tool

### 3.4 Test Coverage
**NONE** - No tests found in `python/tests/` directory for this tool.

---

## 4. Issues

### HIGH

#### H1: Invalid page_type Parameter Silently Ignored
**Location:** Lines 3823-3826
**Evidence:** Only 'free' and 'paid' are valid values, but any other string is silently accepted and returns ALL send_types.
```python
if page_type == 'free':
    query += " AND page_type_restriction IN ('both', 'free')"
elif page_type == 'paid':
    query += " AND page_type_restriction IN ('both', 'paid')"
# No else clause - invalid values return everything
```
**Impact:**
- Typos like 'PAID' or 'Free' or 'paid_page' return ALL types
- No error feedback to consumer
- schedule-generator could generate invalid schedules for page type
**Best Practice Violation:** `mcp_best_practices.md` Section 2 requires input validation.

### MEDIUM

#### M1: Inconsistent Error Response Schema
**Location:** Lines 3852-3854
**Evidence:** Error response `{"error": str, "send_types": []}` differs from success schema.
```python
return {"error": str(e), "send_types": []}
# Missing: by_category, total, page_type_filter, fields_returned
```
**Comparison:** Recent refactors (get_send_type_captions v2.0, validate_caption_structure v2.0) use consistent schema with `error_code`, `metadata.error`.

#### M2: No Metadata Block
**Location:** Return schema
**Evidence:** Missing `fetched_at`, `query_ms`, `tool_version` that other MCP tools provide.
**Comparison:** Pattern established in get_batch_captions_by_content_types v2.0, get_send_type_captions v2.0.

#### M3: Data Duplication in Response
**Location:** Return schema (send_types + by_category)
**Evidence:** Same send_type objects appear in BOTH `send_types` array AND `by_category` sub-arrays.
```json
{
  "send_types": [22 items],
  "by_category": {
    "revenue": [9 items],      // Same objects
    "engagement": [9 items],   // Same objects
    "retention": [4 items]     // Same objects
  }
}
```
**Impact:**
- Response ~6k chars could be ~3.5k chars without duplication
- Tool's stated purpose is "lightweight" but doubles data unnecessarily
- ~43% larger response than needed

### LOW

#### L1: Static `fields_returned` Value
**Location:** Line 3849
**Evidence:** Hardcoded `"fields_returned": 9` instead of calculated from actual fields.
```python
"fields_returned": 9,  # Hardcoded, not len(types[0].keys()) if types else 9
```
**Impact:** If columns are added/removed from query, this value becomes incorrect.

#### L2: Category Default Fallback
**Location:** Lines 3838-3841
**Evidence:** Unknown categories default to 'engagement' and are silently dropped.
```python
cat = t.get('category', 'engagement').lower()
if cat in by_category:
    by_category[cat].append(t)
# If category not in dict, item is silently excluded from by_category
```
**Impact:** Minimal risk since category values are constrained in DB, but inconsistent with fail-fast philosophy.

---

## 5. Refactoring Analysis

### 5.1 What's Working Well
1. **Query efficiency**: Selects only 9/53 columns (~80% reduction)
2. **Correct column names**: All schema references verified correct
3. **Appropriate filtering**: page_type_restriction logic is correct for valid inputs
4. **Stable over time**: Tool serves its purpose for schedule-generator

### 5.2 Comparison with Sister Tool (get_send_types)
| Aspect | get_send_types_constraints | get_send_types |
|--------|---------------------------|----------------|
| Columns | 9 | 53 (SELECT *) |
| Response size | ~6k chars | ~34k chars |
| Input validation | None | None |
| Error handling | Minimal | Minimal |
| Metadata | None | None |

Both tools share the same structural issues.

### 5.3 Priority Order
1. **H1** - Add input validation for page_type (fail-fast or normalize)
2. **M1** - Align error response schema with success schema
3. **M2** - Add metadata block for debugging/tracing
4. **M3** - Remove data duplication OR document why it's intentional
5. **L1** - Calculate fields_returned dynamically

### 5.4 Pattern Alignment
| Pattern | Source | Apply? |
|---------|--------|--------|
| Input validation | mcp_best_practices.md Section 2 | YES - Validate page_type |
| Consistent error schema | get_send_type_captions v2.0 | YES - Match structure |
| Metadata block | get_batch_captions_by_content_types v2.0 | YES - Add tracing |
| TypedDict return | mcp_best_practices.md | OPTIONAL - Low priority |

### 5.5 Complexity Assessment
| Aspect | Value |
|--------|-------|
| Files to modify | 1 (mcp_server/main.py) |
| Breaking changes | No (additive only) |
| Tests needed | 4-6 |
| Estimated phases | 2-3 |

---

## 6. Interview Questions

### Decisions Required

1. **Should invalid page_type values fail or be normalized?**
   - Option A: **FAIL** - Return error for invalid values (recommended - fail-fast)
   - Option B: NORMALIZE - Treat invalid as None (return all types)
   - Option C: Keep current behavior (silently return all)

2. **Should data duplication in response be removed?**
   - Option A: **REMOVE by_category** - Just return send_types array (lighter weight)
   - Option B: REMOVE send_types - Just return by_category dict
   - Option C: **Keep both** - Document that it's intentional for consumer convenience
   - Option D: Make by_category optional parameter

3. **Should this tool get a module-level cache?**
   - Option A: **YES** - Send types rarely change, cache for session lifetime
   - Option B: NO - Keep it simple, DB query is fast anyway
   - Evidence: LEARNINGS.md has "Module-Level Caching Pattern for MCP DB Lookups" as LOW confidence

4. **Should we add pool statistics like caption tools?**
   - Option A: YES - Add counts per category, active/inactive counts
   - Option B: **NO** - This is a config lookup, not a data retrieval tool

### Assumptions to Verify

1. **Assumption:** `by_category` grouping is used by consumers
   - Evidence: schedule-generator.md doesn't reference by_category explicitly
   - Verify: Is the grouping actually used, or do consumers just iterate send_types?

2. **Assumption:** page_type filter is always valid when called
   - Evidence: preflight.py passes creator.page_type which comes from DB
   - Verify: Could invalid values reach this tool from other entry points?

3. **Assumption:** No inactive send_types need to be retrieved
   - Evidence: WHERE is_active = 1 is hardcoded
   - Verify: Is there ever a need to see inactive types for debugging?

---

## 7. Data Analysis

### Send Types by Category
```
engagement: 9 types
  - link_drop, wall_link_drop, bump_normal, bump_descriptive,
    bump_text_only, bump_flyer, dm_farm, like_farm, live_promo

revenue: 9 types
  - ppv_unlock, ppv_wall, tip_goal, vip_program, game_post,
    bundle, flash_bundle, snapchat_bundle, first_to_tip

retention: 4 types
  - renew_on_post, renew_on_message, ppv_followup, expired_winback
```

### Page Type Restrictions
```
both: 18 types (available to all pages)
paid: 4 types (renew_on_post, renew_on_message, tip_goal, expired_winback)
free: 1 type (ppv_wall)
```

### Response Size Analysis
```
Full response (no filter): ~6,200 characters
With page_type='paid': ~5,800 characters (excludes ppv_wall)
With page_type='free': ~5,900 characters (excludes paid-only types)
Without by_category duplication: ~3,500 characters (estimated)
```

---

## 8. Recommended Refactoring Scope

Based on analysis, this tool requires **minor refactoring** (less complex than get_send_type_captions):

### Phase 1: Input Validation + Error Schema
- Add page_type validation ('paid', 'free', None, or error)
- Create `_build_send_types_error_response()` helper
- Add error_code to error responses

### Phase 2: Metadata + Optional Optimization
- Add metadata block (fetched_at, query_ms, tool_version)
- Optionally: Add include_by_category parameter (default True for backwards compat)
- Update docstring with version and full response schema

### Tests Required
1. test_valid_page_type_paid_filters_correctly
2. test_valid_page_type_free_filters_correctly
3. test_null_page_type_returns_all
4. test_invalid_page_type_returns_error
5. test_by_category_grouping_correct
6. test_metadata_present_in_response

---

**REVIEW_DONE**
