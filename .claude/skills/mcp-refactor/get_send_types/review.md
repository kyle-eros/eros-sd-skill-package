# Technical Review: get_send_types v1.0 → v2.0

**Version**: 1.0.0
**Date**: 2026-01-13
**Author**: Claude Code (Phase 1 Ralph Loop)
**Status**: REVIEW_COMPLETE

---

## Quick Reference

| Attribute | Value |
|-----------|-------|
| Tool Name | `mcp__eros-db__get_send_types` |
| Location | `mcp_server/main.py:3974-4019` |
| Current Version | 1.0 (implicit) |
| Target Version | 2.0.0 |
| Database Table | `send_types` (53 columns) |
| Pipeline Phase | Config/Reference |
| Primary Consumers | schedule-generator (reference), adapters.py |

---

## 1. Current Implementation Analysis

### 1.1 Source Code (Lines 3974-4019)

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

### 1.2 Key Observations

| Aspect | Current State | Issue |
|--------|---------------|-------|
| Query | `SELECT *` (53 columns) | Returns ALL columns including internal/deprecated |
| Input validation | None | Invalid page_type silently returns unfiltered results |
| Error response | `{"error": str, "send_types": []}` | Inconsistent with v2.0 pattern |
| Caching | None | Bypasses shared `_SEND_TYPES_CACHE` |
| Metadata | None | No version, fetched_at, hash |
| Response size | ~14,600 tokens | 10x larger than constraints tool |

---

## 2. Database Layer Analysis

### 2.1 Table Schema: `send_types` (53 columns)

Verified via `PRAGMA table_info(send_types)`:

| Column Group | Columns | Purpose |
|--------------|---------|---------|
| **Identity** (3) | send_type_id, send_type_key, display_name | Primary identifiers |
| **Classification** (2) | category, page_type_restriction | Grouping/filtering |
| **Constraints** (4) | max_per_day, max_per_week, min_hours_between, sort_order | Schedule limits |
| **Requirements** (5) | requires_media, requires_flyer, requires_price, requires_link, has_expiration | Content requirements |
| **Expiration** (2) | default_expiration_hours, can_have_followup | Time-based config |
| **Content Guidance** (2) | caption_length, emoji_recommendation | Caption hints |
| **Scoring** (5) | priority_score, allocation_weight, fatigue_score, fatigue_multiplier, revenue/engagement/retention_weight | Weighting |
| **Channel** (8) | primary_channel_key, secondary_channel_key, channel_distribution, hybrid_split, etc. | Delivery config |
| **Cooldown** (3) | cooldown_category, cooldown_after_engagement_min, cooldown_after_revenue_min | Rate limiting |
| **Drip** (2) | drip_window_allowed, drip_window_triggers | Drip scheduling |
| **A/B Testing** (2) | ab_test_eligible, current_experiment_id | Experimentation |
| **Lifecycle** (4) | schema_version, created_at, updated_at, deprecated_at | Metadata |
| **Descriptive** (3) | description, purpose, strategy | Human-readable |

### 2.2 Current Query Analysis

```sql
SELECT * FROM send_types WHERE is_active = 1
```

**Issues:**
1. Returns 53 columns when most consumers need 10-15
2. Includes internal columns (schema_version, created_at, deprecated_at)
3. Returns NULL values for optional columns (wastes tokens)
4. No hash for ValidationCertificate tracking

---

## 3. Pipeline Position & Consumer Analysis

### 3.1 Documented Consumers

| Consumer | File | Line | Usage Pattern |
|----------|------|------|---------------|
| schedule-generator | `.claude/skills/eros-schedule-generator/SKILL.md` | 11 | Listed as available tool (reference) |
| schedule-generator agent | `.claude/agents/schedule-generator.md` | 36 | "Use constraints instead of get_send_types" |
| adapters.py | `python/adapters.py` | 242-244 | Async wrapper passthrough |
| preflight.py | `python/preflight.py` | 87 | Protocol definition |

### 3.2 Actual Usage Pattern

Based on `schedule-generator.md` line 36:
> "**ALWAYS** use `mcp__eros-db__get_send_types_constraints` instead of `get_send_types`"

This suggests `get_send_types` is a **secondary/reference tool** used when:
- Full descriptions/strategies needed for caption generation
- Channel configuration details required
- Scoring weights needed for advanced optimization

### 3.3 Relationship with Sister Tool

| Aspect | get_send_types_constraints | get_send_types |
|--------|----------------------------|----------------|
| Version | 2.0.0 | 1.0 (implicit) |
| Fields | 9 essential | 53 (all) |
| Caching | Uses `_SEND_TYPES_CACHE` | Bypasses cache |
| Input validation | Case-normalize + error code | None |
| Error response | Structured with `error_code` | Simple string |
| Metadata | version, hash, source | None |
| Response size | ~1,500 tokens | ~14,600 tokens |
| Use case | Schedule generation (primary) | Reference (secondary) |

---

## 4. Issues Identified

### 4.1 CRITICAL Issues

*None identified* - Tool functions correctly but needs modernization.

### 4.2 HIGH Severity Issues

#### H1: Bypasses Shared Cache
**Current**: Direct `db_query()` call every invocation
**Impact**: Redundant DB calls when both tools used in same session
**Fix**: Use `_get_send_types_cache()` then extend with additional fields

#### H2: No Input Validation
**Current**: Invalid `page_type` silently returns unfiltered results
**Impact**: Consumer confusion, potential HARD GATE violations
**Fix**: Case-normalize, fail-fast with `INVALID_PAGE_TYPE` error code

#### H3: Inconsistent Error Response
**Current**: `{"error": str, "send_types": []}`
**Impact**: Consumers must handle different error schemas
**Fix**: Use structured error with `error_code`, `error_message`, all fields

### 4.3 MEDIUM Severity Issues

#### M1: No Metadata Block
**Current**: Response lacks version, fetched_at, hash
**Impact**: Cannot verify data freshness or pipeline integrity
**Fix**: Add standard metadata block matching constraints tool

#### M2: Duplicate `send_types` Array
**Current**: Returns both `send_types` (flat) and `by_category` (grouped)
**Impact**: Redundant data, inflated response size
**Fix**: Consider removing flat array (BREAKING - requires discussion)

#### M3: Missing Docstring Detail
**Current**: "Returns: List of send types with constraints"
**Impact**: No response schema documentation
**Fix**: Add full response schema in docstring

#### M4: No `counts` Field
**Current**: Only `total` count provided
**Impact**: Inconsistent with constraints tool response
**Fix**: Add `counts: {revenue, engagement, retention, total}`

### 4.4 LOW Severity Issues

#### L1: No Version Number in Docstring
**Current**: Implicit v1.0
**Impact**: Difficult to track changes
**Fix**: Add `Version: 2.0.0` to docstring

---

## 5. Refactoring Recommendations

### 5.1 Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     _SEND_TYPES_CACHE                        │
│  (extended to include ALL 53 fields on first population)    │
└─────────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
┌─────────────────────┐         ┌─────────────────────┐
│ get_send_types      │         │ get_send_types_     │
│ _constraints()      │         │ constraints()       │
│                     │         │                     │
│ Returns: 53 fields  │         │ Returns: 9 fields   │
│ Use: Full reference │         │ Use: Scheduling     │
└─────────────────────┘         └─────────────────────┘
```

### 5.2 Phased Implementation

| Phase | Scope | Breaking? | Effort |
|-------|-------|-----------|--------|
| 1 | Input validation + error response | No | Low |
| 2 | Integrate with shared cache | No | Medium |
| 3 | Add metadata block | No | Low |
| 4 | Add counts field | No | Low |
| 5 | Update docstring | No | Low |
| 6 | (Optional) Remove send_types array | **YES** | Discuss |

### 5.3 Backwards Compatibility Strategy

**SAFE to change:**
- Add input validation (fail-fast on invalid)
- Add metadata block (new field)
- Add counts field (new field)
- Update docstring (documentation only)

**DISCUSS before changing:**
- Remove `send_types` flat array (consumers may depend on it)
- Change `total` → `counts.total` (could break parsing)

---

## 6. Interview Questions for Phase 2

### 6.1 Scope Decisions

1. **Cache Integration Strategy**: Should `get_send_types` extend the shared cache to include ALL 53 columns, or maintain a separate query for full data?
   - Option A: Extend cache (single query serves both tools)
   - Option B: Separate query (cache stays lightweight)

2. **Flat Array Retention**: Should we keep the `send_types` flat array for backwards compatibility?
   - Option A: Keep both `send_types` and `by_category` (larger response, backwards compatible)
   - Option B: Remove `send_types`, keep only `by_category` (smaller, breaking)
   - Option C: Keep `send_types`, remove `by_category` (opposite of constraints tool pattern)

### 6.2 Response Schema Decisions

3. **Column Selection**: Should the tool return all 53 columns, or a curated subset of ~20 "useful" columns?
   - Option A: All 53 columns (current behavior, for max flexibility)
   - Option B: Curated subset (exclude internal: schema_version, created_at, deprecated_at, etc.)

4. **Consistency vs Differentiation**: Should the response schema mirror `get_send_types_constraints` exactly (just with more fields), or remain differentiated?
   - Option A: Mirror structure (easier to swap between tools)
   - Option B: Keep unique structure (clearer tool identity)

### 6.3 Edge Cases

5. **Error Response Schema**: When returning error, should we return empty `by_category` structure or just `error` + `send_types: []`?
   - Current: `{"error": str, "send_types": []}`
   - Proposed: Full schema with `error_code`, `by_category: {revenue: [], ...}`, `counts: {...}`

---

## 7. Success Criteria for Refactoring

### 7.1 Functional Requirements

- [ ] Input validation: Case-insensitive page_type with fail-fast on invalid
- [ ] Error responses: Structured with `error_code` matching constraints pattern
- [ ] Cache integration: Uses shared `_SEND_TYPES_CACHE` mechanism
- [ ] Metadata block: version, fetched_at, source, hash
- [ ] Counts field: Per-category counts matching constraints pattern

### 7.2 Non-Functional Requirements

- [ ] Backwards compatible (unless explicitly approved for breaking changes)
- [ ] All existing tests pass (if any)
- [ ] New tests for input validation, caching, error handling
- [ ] Response size documented in MCP_SETUP_GUIDE.md
- [ ] Docstring includes full response schema

### 7.3 Verification Commands

```bash
# Run tests (after Phase 3)
python3 -m pytest python/tests/test_send_types.py -v

# Verify cache sharing works
python3 -c "
from mcp_server.main import get_send_types_constraints, get_send_types
from mcp_server import main

# First call populates cache
result1 = get_send_types_constraints()
print(f'After constraints: cache size = {len(main._SEND_TYPES_CACHE)}')

# Second call should hit cache
result2 = get_send_types()
print(f'After full: source = {result2[\"metadata\"][\"source\"]}')
"
```

---

## 8. Appendix: Full Column List

```
send_type_id, send_type_key, category, display_name, description, purpose,
strategy, requires_media, requires_flyer, requires_price, requires_link,
has_expiration, default_expiration_hours, can_have_followup, followup_delay_minutes,
page_type_restriction, caption_length, emoji_recommendation, max_per_day,
max_per_week, min_hours_between, sort_order, is_active, created_at, priority_score,
allocation_weight, fatigue_score, fatigue_multiplier, revenue_weight,
engagement_weight, retention_weight, cooldown_category, audience_segment,
ab_test_eligible, current_experiment_id, min_subscriber_tenure_days, deprecated_at,
replacement_send_type_id, schema_version, updated_at, primary_channel_key,
secondary_channel_key, primary_channel_weight, wall_delivery_page_type,
wall_content_level, supports_link_drop_promo, channel_distribution, hybrid_split,
page_type_lock, drip_window_allowed, drip_window_triggers,
cooldown_after_engagement_min, cooldown_after_revenue_min
```

---

<promise>REVIEW_DONE</promise>
