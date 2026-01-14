# get_send_type_captions - Technical Review

**Generated:** 2026-01-13 | **Reviewer:** code-reviewer | **Status:** Interview Ready

---

## Quick Reference

| Attribute | Value |
|-----------|-------|
| File | mcp_server/main.py |
| Lines | 3245-3308 |
| Phase | Generator (schedule-generator uses for engagement/retention items) |
| Data Sources | caption_bank |
| Issues | CRITICAL: 1 | HIGH: 2 | MEDIUM: 3 | LOW: 2 |

---

## 1. Current Implementation

### 1.1 Signature
```python
@mcp.tool()
def get_send_type_captions(creator_id: str, send_type: str, limit: int = 10) -> dict:
```

### 1.2 Parameters
| Param | Type | Required | Default | Used? |
|-------|------|----------|---------|-------|
| creator_id | str | Yes | - | Logged but NOT used in query |
| send_type | str | Yes | - | Yes (caption_type filter) |
| limit | int | No | 10 | Yes (clamped 1-50) |

### 1.3 Return Schema
```python
# Success:
{
    "creator_id": str,
    "send_type": str,
    "category_matched": str,  # From hardcoded map
    "captions": list,         # Raw db_query results
    "count": int
}

# Error:
{
    "error": str,
    "captions": []
}
```

### 1.4 Source Code
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
    logger.info(f"get_send_type_captions: creator_id={creator_id}, send_type={send_type}")
    try:
        limit = min(max(1, limit), 50)

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

        return {
            "creator_id": creator_id,
            "send_type": send_type,
            "category_matched": category,
            "captions": captions,
            "count": len(captions)
        }

    except Exception as e:
        logger.error(f"get_send_type_captions error: {e}")
        return {"error": str(e), "captions": []}
```

---

## 2. Database Layer

### 2.1 Schema (caption_bank)
```sql
-- From PRAGMA table_info(caption_bank):
caption_id              INTEGER  PRIMARY KEY
caption_text            TEXT     NOT NULL
caption_hash            TEXT     NOT NULL
caption_type            TEXT     NOT NULL  -- Stores send_type_key values!
content_type_id         INTEGER  NOT NULL
schedulable_type        TEXT
is_paid_page_only       INTEGER  NOT NULL DEFAULT 0
is_active               INTEGER  NOT NULL DEFAULT 1
performance_tier        INTEGER  NOT NULL DEFAULT 3
suggested_price         REAL
price_range_min         REAL
price_range_max         REAL
classification_confidence REAL   NOT NULL DEFAULT 0.5
classification_method   TEXT     NOT NULL DEFAULT 'unknown'
global_times_used       INTEGER  NOT NULL DEFAULT 0
global_last_used_date   TEXT
total_earnings          REAL     DEFAULT 0.0
total_sends             INTEGER  DEFAULT 0
avg_view_rate           REAL     DEFAULT 0.0
avg_purchase_rate       REAL     DEFAULT 0.0
source                  TEXT     DEFAULT 'mass_messages_rebuild'
created_at              TEXT     NOT NULL DEFAULT datetime('now')
updated_at              TEXT     NOT NULL DEFAULT datetime('now')
```

### 2.2 Queries
```sql
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
```

### 2.3 Column Verification
| SQL Column | Schema Column | Match | Notes |
|------------|---------------|-------|-------|
| caption_id | caption_id | YES | |
| caption_text | caption_text | YES | |
| caption_type | caption_type | YES | Aliased as 'category' |
| performance_tier | performance_tier | YES | Aliased as 'quality_score' |
| content_type_id | content_type_id | YES | |
| global_last_used_date | global_last_used_date | YES | Aliased as 'last_used_at' |

---

## 3. Pipeline Position

### 3.1 Flow
```
Preflight (CreatorContext built)
    ↓
schedule-generator (uses this tool)
    ↓ Output: schedule items with caption_id
schedule-validator
    ↓
save_schedule
```

### 3.2 Dependencies
| Type | Items |
|------|-------|
| Tables | caption_bank |
| Upstream Tools | None (direct call from Generator) |
| Downstream | schedule-validator (receives caption_id) |

### 3.3 Test Coverage
**NONE** - No tests found in `python/tests/` directory for this tool.

---

## 4. Issues

### CRITICAL

#### C1: category_map Fallback Never Matches Data
**Location:** Lines 3263-3278
**Evidence:** Database analysis shows `caption_type` stores actual send_type_keys ('ppv_unlock', 'bump_normal'), NOT generic categories ('ppv', 'bump').
```sql
-- Actual caption_type values:
bump_normal|22960
ppv_unlock|11865
game_post|2456
-- etc.

-- category_map would map 'ppv_unlock' -> 'ppv' but NO captions have caption_type='ppv'
```
**Impact:** The fallback logic (`caption_type = ?` where `?` = category) will NEVER match any rows. Only exact send_type matches work.
**Current Behavior:** Tool appears to work because exact matches succeed, but fallback is dead code.

### HIGH

#### H1: creator_id Accepted but Ignored
**Location:** Line 3246, 3259, 3299
**Evidence:** Parameter logged and returned in response, but NOT used in SQL query.
**Impact:**
- No per-creator freshness filtering (unlike get_batch_captions_by_content_types v2.0)
- No creator validation (could pass invalid creator)
- Returns same captions for all creators
**Comparison:** `get_batch_captions_by_content_types` validates creator and joins with `caption_creator_performance` for freshness.

#### H2: Missing Input Validation (Four-Layer Defense)
**Location:** Lines 3259-3261
**Evidence:** Only limit clamping, no validation for:
- creator_id format/existence
- send_type validity (should check against send_types table)
**Best Practice Violation:** `mcp_best_practices.md` Section 2 requires four-layer defense.

### MEDIUM

#### M1: Inconsistent Error Response Schema
**Location:** Lines 3306-3308
**Evidence:** Error response `{"error": str, "captions": []}` differs from success schema.
**Comparison:** `get_batch_captions_by_content_types` uses `_build_caption_error_response()` with consistent fields including `error_code`, `metadata.error`, etc.

#### M2: No Pool Statistics
**Location:** Return schema
**Evidence:** No information about total available captions, fresh vs stale, or selection context.
**Comparison:** `get_batch_captions_by_content_types` v2.0 returns `pool_stats` per content type for transparency.

#### M3: Missing 12 Send Types from category_map
**Location:** Lines 3263-3278
**Evidence:** 23 send_types in database, only 13 in category_map.
```
Missing: bundle, vip_program, game_post, flash_bundle, snapchat_bundle,
         first_to_tip, like_farm, live_promo, ppv_message, renew_on_post,
         wall_link_drop, bump_text_only
```
**Impact:** These fall through to 'general' category which likely doesn't exist.

### LOW

#### L1: No Metadata Block
**Location:** Return schema
**Evidence:** Missing `fetched_at`, `query_ms`, `tool_version` that other MCP tools provide.

#### L2: Hardcoded 'general' Fallback Category
**Location:** Line 3279, 3288
**Evidence:** `caption_type = 'general'` fallback, but no captions with this type exist in database.
```sql
-- Query shows 20 distinct caption_types, none are 'general'
```

---

## 5. Refactoring Plan

### 5.1 Priority Order
1. **C1** - Fix category matching logic (or remove dead code)
2. **H1** - Implement per-creator freshness or remove unused parameter
3. **H2** - Add four-layer validation
4. **M1** - Align error response schema
5. **M2** - Add pool statistics
6. **M3** - Update category_map or use send_types table join

### 5.2 Pattern Alignment
| Pattern | Source | Apply? |
|---------|--------|--------|
| Four-layer defense | mcp_best_practices.md | YES - Add validation layers |
| _build_caption_error_response | get_batch_captions_by_content_types | YES - Consistent errors |
| pool_stats CTE | get_batch_captions_by_content_types | YES - Add transparency |
| Per-creator freshness | caption_creator_performance table | YES - If creator_id is meaningful |
| TypedDict return | mcp_best_practices.md | YES - Structured returns |

### 5.3 Complexity
| Aspect | Value |
|--------|-------|
| Files to modify | 1 (mcp_server/main.py) |
| Breaking changes | Maybe (return schema changes) |
| Tests needed | 6-8 (validation, send_type coverage, error cases) |
| Estimated phases | 3-4 |

---

## 6. Interview Questions

### Decisions Required

1. **Should creator_id drive per-creator freshness filtering?**
   - Option A: YES - Join with caption_creator_performance like get_batch_captions_by_content_types
   - Option B: NO - Remove parameter entirely (captions are global by send_type)
   - Option C: Keep parameter but only for logging/response (current behavior, but document)

2. **How should category fallback work?**
   - Option A: Remove fallback logic entirely (dead code - exact send_type match only)
   - Option B: Join with send_types table to get actual category, then fallback to same-category captions
   - Option C: Keep hardcoded map but fix to use actual caption_type values

3. **Should this tool return pool_stats like get_batch_captions_by_content_types?**
   - Option A: YES - Add pool_stats for transparency
   - Option B: NO - This is a simpler tool, keep lightweight

4. **What's the intended use case for this tool vs get_batch_captions_by_content_types?**
   - get_batch_captions_by_content_types: PPV selection by content type
   - get_send_type_captions: Non-PPV selection by send type (bumps, renewals, etc.)?
   - Should they be unified or remain separate?

### Assumptions to Verify

1. **Assumption:** `caption_type` in caption_bank always stores send_type_key values
   - Evidence: 20 distinct caption_types match send_type_keys exactly
   - Verify: Is this by design or migration artifact?

2. **Assumption:** The 'general' fallback category is unused
   - Evidence: No captions with caption_type='general' in database
   - Verify: Should 'general' captions exist? Was this planned?

3. **Assumption:** This tool is primarily used by schedule-generator for non-PPV items
   - Evidence: SKILL.md shows it's for "engagement/retention items"
   - Verify: Are there other consumers?

---

## Appendix: Data Analysis

### caption_type Distribution (Top 10)
```
bump_normal     | 22,960
ppv_unlock      | 11,865
game_post       | 2,456
bump_descriptive| 2,311
link_drop       | 1,911
bundle          | 1,662
dm_farm         | 1,508
first_to_tip    | 1,331
snapchat_bundle | 815
like_farm       | 785
```

### send_types.category Values
```
engagement
retention
revenue
```

### Missing send_type_keys in category_map
```
bundle, flash_bundle, snapchat_bundle - (revenue category)
vip_program - (retention category)
game_post, first_to_tip, like_farm - (engagement category)
live_promo - (engagement category)
ppv_message - (revenue category)
wall_link_drop - (revenue category)
```
