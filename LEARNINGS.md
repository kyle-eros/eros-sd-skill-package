# EROS Self-Improving Skills - Learning Accumulation

**Version**: 1.7.0 | **Last Updated**: 2026-01-13 | **Total Learnings**: 19

---

## Feedback Sources & Confidence Levels

| Level | Behavior | Sources |
|-------|----------|---------|
| **HIGH** | MUST follow | Hard gate violations, explicit user corrections |
| **MEDIUM** | SHOULD follow | Quality >= 85 patterns, user approvals, sample >= 10 |
| **LOW** | MAY inform | Sample < 10, emerging trends to monitor |

---

## Statistics

```yaml
by_confidence: { high: 1, medium: 239, low: 15 }
by_source: { validation: 238, user: 1, performance: 0, refactor: 16 }
by_scope: { all_creators: 16, tier_specific: 0, creator_specific: 0 }
last_7_days: { added: 251, promoted: 0, deprecated: 0 }
```

---

## HIGH Confidence Learnings

> MUST follow - Hard gate violations and explicit user corrections

<!-- Entry Template:
### [YYYY-MM-DD] Title
**Pattern**: What was done
**Issue**: Why it was wrong
**Correction**: What to do instead
**Source**: validation | user | **Violation Code**: CODE | **Sample Size**: N
**Applies To**: all | tier:TIER_NAME | creator:creator_id
-->

---
### [2026-01-12] Trigger Merge Strategy: Field-by-Field, Not Winner-Takes-All
**Pattern**: When DB triggers and runtime detections conflict on same (creator, content_type, trigger_type)
**Insight**: Different fields have different freshness requirements - adjustment_multiplier from runtime (fresher), confidence uses MAX (ratchets up), first_detected_at from DB (preserved)
**Source**: user | **Interview**: save_volume_triggers refactoring
**Applies To**: all
**Implementation**: `_merge_triggers()` function in preflight should use field-by-field rules, not simple source precedence

### [2026-01-12] Phase-by-Phase Sub-Agent Refactoring Pattern
**Pattern**: Complex refactors (5+ phases) executed via sequential sub-agent deployment with verification gates
**Insight**: Each phase has: explicit success criteria, test baseline check, commit specification, rollback protocol
**Source**: refactor | **Sample Size**: 1 (save_volume_triggers v3.0.0: 5 phases, 4 commits, 696 LOC, 14 new tests)
**Applies To**: all
**Workflow**: Preflight → Phase 1..N (each: sub-agent → verify → commit) → Final verification
**Promote When**: Pattern used successfully in 3+ multi-phase refactorings

### [2026-01-13] Category-Aware Validation Pattern for Multi-Purpose Tools
**Pattern**: Validation tools serving different send categories (revenue/engagement/retention) need category-specific rules
**Insight**: Revenue allows longer captions (450 chars) and tolerates sales language; engagement/retention stricter
**Source**: refactor | **Sample Size**: 1 (validate_caption_structure v2.0.0: 28 tests, all passing)
**Applies To**: all
**Implementation**: `CAPTION_LENGTH_THRESHOLDS` dict in volume_utils.py with per-category min/ideal/max ranges
**Promote When**: Pattern reused in 2+ other validation tools

### [2026-01-13] Shared Module-Level Cache Across MCP Tools
**Pattern**: Multiple MCP tools needing same static data should share a module-level cache
**Insight**: _SEND_TYPES_CACHE shared between validate_caption_structure and get_send_types_constraints - single DB call serves both
**Source**: refactor | **Sample Size**: 2 (both tools tested with 45 combined test cases passing)
**Applies To**: all
**Implementation**: Extend cache query to include all fields needed by any consumer; filter at return time
**Promote When**: Pattern used by 3+ tools

### [2026-01-13] Revenue Diversity Gate Requires 4+ Unique Send Types
**Pattern**: Schedule generated with only 3 revenue types (ppv_unlock, ppv_wall, bundle)
**Issue**: Gate 4 DIVERSITY check rejected schedule for insufficient revenue variety
**Correction**: Always include 4+ unique revenue send types when generating schedules. Use flash_bundle, first_to_tip, vip_program, game_post, or snapchat_bundle to diversify beyond core ppv_unlock/ppv_wall/bundle types.
**Source**: validation | **Violation Code**: INSUFFICIENT_DIVERSITY
**Applies To**: all
**Evidence**: grace_bennett 2026-01-13 schedule rejected then approved after adding flash_bundle + first_to_tip

<!-- Entry Template:
### [YYYY-MM-DD] Title
**Pattern**: What was observed | **Insight**: Why it works
**Source**: validation | user | performance | **Quality Score**: N | **Sample Size**: N
**Applies To**: all | tier:TIER_NAME | creator:creator_id
**Metric Impact**: +N% RPS | +N% conversion | etc.
-->

---

## LOW Confidence Learnings

> MAY inform - Observations with sample < 10, trends to monitor

### [2026-01-12] save_schedule v2.0.0 Schema Alignment
**Observation**: 6 column name mismatches between MCP tool and database schema caused silent failures
**Hypothesis**: Schema drift between documentation, code, and database is a recurring risk
**Source**: refactor | **Sample Size**: 1
**Applies To**: all
**Promote When**: Similar schema issues found in other MCP tools

### [2026-01-12] Detection Counter Pattern Over Soft-Delete for Trigger History
**Observation**: Soft-delete chains (is_active=0 + superseded_by) cause row proliferation and complex queries
**Hypothesis**: Detection counter (detection_count++) with first_detected_at preservation provides simpler history tracking
**Source**: refactor | **Sample Size**: 1
**Applies To**: all
**Promote When**: Pattern validated in production for 2+ weeks

### [2026-01-12] ON CONFLICT DO UPDATE Preserves IDs, INSERT OR REPLACE Destroys Them
**Observation**: INSERT OR REPLACE deletes then inserts, generating new AUTO_INCREMENT IDs. ON CONFLICT modifies in place.
**Hypothesis**: Preserving trigger_id across re-detections enables better audit trails and consumer tracking
**Source**: refactor | **Sample Size**: 1
**Applies To**: all
**Promote When**: Other MCP write tools confirm pattern value

### [2026-01-12] SQLite Partial Index Limitation with ON CONFLICT
**Observation**: Partial unique indexes (with WHERE clause) do NOT work with SQLite's ON CONFLICT clause
**Hypothesis**: Must convert partial indexes to full unique indexes when implementing UPSERT patterns
**Source**: refactor | **Sample Size**: 1 (save_volume_triggers v3.0.0 migration)
**Applies To**: all
**Promote When**: Confirmed in other UPSERT implementations

### [2026-01-12] Test Fixture Schema Sync Requirement
**Observation**: Test fixtures with inline CREATE TABLE must match production schema exactly including new columns
**Hypothesis**: Schema changes and test fixture updates should be atomic (same commit) to avoid test failures
**Source**: refactor | **Sample Size**: 1 (Phase 2 required fixture update for detection_count/first_detected_at)
**Applies To**: all
**Promote When**: Pattern validated across 3+ schema change PRs

### [2026-01-13] caption_type Stores send_type_key Values Directly
**Observation**: caption_bank.caption_type column stores exact send_type_keys (ppv_unlock, bump_normal, etc.), not generic categories
**Hypothesis**: Category-based fallback logic (ppv, bump, general) becomes dead code when data model stores granular values
**Source**: refactor | **Sample Size**: 1 (49,550 captions analyzed, 20 distinct caption_types all match send_type_keys)
**Applies To**: all
**Evidence**: SELECT DISTINCT caption_type FROM caption_bank returns only send_type_keys
**Promote When**: Pattern confirmed in other caption-related tool refactors

### [2026-01-13] Per-Creator Freshness JOIN Pattern for Caption Tools
**Observation**: JOIN caption_creator_performance enables per-creator usage tracking with 90-day freshness threshold
**Hypothesis**: ORDER BY effectively_fresh DESC, ccp.last_used_date ASC NULLS FIRST prioritizes never-used-by-creator captions
**Source**: refactor | **Sample Size**: 2 (get_batch_captions_by_content_types v2.0, get_send_type_captions v2.0)
**Applies To**: all
**Implementation**: LEFT JOIN caption_creator_performance ccp ON cb.caption_id = ccp.caption_id AND ccp.creator_id = ?
**Promote When**: 3+ caption tools use this pattern successfully

### [2026-01-13] Pool Stats Enable Informed Caption Distribution
**Observation**: Returning pool_stats (total_available, fresh_for_creator, freshness_ratio) with caption queries aids agent decisions
**Hypothesis**: schedule-generator can reduce send_type frequency or flag degraded freshness when pool_stats.freshness_ratio < 0.5
**Source**: refactor | **Sample Size**: 2 (get_batch_captions_by_content_types v2.0, get_send_type_captions v2.0)
**Applies To**: all
**Promote When**: schedule-generator demonstrates usage of pool_stats in decision-making

### [2026-01-13] Test sys.path Must Use Project Root, Not Module Directory
**Observation**: pytest imports failed when sys.path pointed to mcp_server/ because main.py uses relative import `from .volume_utils import`
**Hypothesis**: Always insert project root into sys.path, then patch fully-qualified paths like `mcp_server.main.db_query`
**Source**: refactor | **Sample Size**: 1 (validate_caption_structure v2.0.0 tests required fix)
**Applies To**: all
**Fix Pattern**: `sys.path.insert(0, '/path/to/project')` + `patch('mcp_server.main.db_query')`
**Promote When**: Confirmed in 2+ additional test files

### [2026-01-13] Module-Level Caching Pattern for MCP DB Lookups
**Observation**: Repeated DB queries for static data (send_types taxonomy) add latency without benefit
**Hypothesis**: Module-level dict cache (`_SEND_TYPES_CACHE: dict[str, dict] = {}`) with session lifetime reduces calls
**Source**: refactor | **Sample Size**: 2 (validate_caption_structure v2.0.0 + get_send_types_constraints v2.0.0 share cache)
**Applies To**: all
**Implementation**: Check cache → call db_query if miss → populate cache → return from cache
**Note**: PROMOTED to MEDIUM - pattern reused in 2 MCP tools successfully with shared cache

### [2026-01-13] Hybrid Cache Strategy for Different Access Patterns
**Observation**: get_send_types (full) and get_send_types_constraints (lightweight) have different field requirements
**Hypothesis**: Lazy-loaded separate caches avoid memory bloat while enabling both use cases
**Source**: refactor | **Sample Size**: 1 (get_send_types v2.0.0)
**Applies To**: all
**Implementation**: `_SEND_TYPES_CACHE` (9 fields, eager) + `_SEND_TYPES_FULL_CACHE` (48 fields, lazy)
**Promote When**: Pattern used for 2+ tool pairs with different field requirements

### [2026-01-13] Explicit Column Lists Over SELECT * for MCP Tools
**Observation**: SELECT * returns 53 columns including internal lifecycle fields consumers shouldn't depend on
**Hypothesis**: Explicit column lists protect against schema changes leaking into API contracts
**Source**: refactor | **Sample Size**: 1 (get_send_types v2.0.0)
**Applies To**: all
**Implementation**: `_SEND_TYPES_FULL_COLUMNS` constant with 48 business columns, excludes schema_version, created_at, updated_at, deprecated_at, replacement_send_type_id
**Promote When**: 2+ additional MCP tools converted from SELECT * to explicit lists

### [2026-01-13] Breaking Changes Acceptable for Secondary Tools
**Observation**: Removing redundant data from get_send_types response was a breaking change that reduced tokens by ~45%
**Hypothesis**: Secondary/reference tools (explicitly documented as "use X instead") can accept breaking changes with minimal blast radius
**Source**: refactor | **Sample Size**: 1 (get_send_types v2.0.0 removed send_types array)
**Applies To**: all
**Evidence**: schedule-generator.md line 36: "ALWAYS use get_send_types_constraints instead of get_send_types"
**Promote When**: Pattern validated in 2+ secondary tool refactors

### [2026-01-13] Generator-to-Persistence Schema Field Mismatch
**Observation**: save_schedule MCP tool expects scheduled_date/scheduled_time/send_type_key but generator output uses date/send_time/send_type
**Hypothesis**: Generator output format should align with persistence schema to avoid transformation step or validation failures
**Source**: validation | **Sample Size**: 1 (grace_bennett 2026-01-13 schedule save attempt)
**Applies To**: all
**Evidence**: VALIDATION_ERROR: "missing required keys: scheduled_date, scheduled_time, send_type_key"
**Promote When**: Confirmed as consistent pattern across 3+ schedule saves

<!-- Entry Template:
### [YYYY-MM-DD] Title
**Observation**: What was noticed | **Hypothesis**: Why it might matter
**Source**: validation | user | performance | **Sample Size**: N (<10)
**Applies To**: all | tier:TIER_NAME | creator:creator_id
**Promote When**: Sample >= 10 AND consistent results
-->

---

## Deprecated Learnings

> Superseded, invalidated, or expired learnings

### [2026-01-12] Test Artifacts Removed
**Original**: 47 "High Quality Pattern (90)" entries from test/mock validations
**Reason**: Invalidated - entries were from test runs with mock data, not production schedules

---
| 2026-01-12 | ADDED | ON CONFLICT vs INSERT OR REPLACE | LOW | refactor |
| 2026-01-12 | ADDED | Detection Counter Over Soft-Delete | LOW | refactor |
| 2026-01-12 | ADDED | Trigger Merge Strategy Field-by-Field | MEDIUM | user |
| 2026-01-12 | ADDED | Phase-by-Phase Sub-Agent Refactoring | MEDIUM | refactor |
| 2026-01-12 | ADDED | SQLite Partial Index ON CONFLICT Limitation | LOW | refactor |
| 2026-01-12 | ADDED | Test Fixture Schema Sync Requirement | LOW | refactor |
| 2026-01-12 | CLEANED | Removed 47 test-generated entries | - | refactor |
| 2026-01-12 | ADDED | save_schedule v2.0.0 Schema Alignment | LOW | refactor |
| 2026-01-13 | ADDED | caption_type Stores send_type_key Directly | LOW | refactor |
| 2026-01-13 | ADDED | Per-Creator Freshness JOIN Pattern | LOW | refactor |
| 2026-01-13 | ADDED | Pool Stats Enable Caption Distribution | LOW | refactor |
| 2026-01-13 | ADDED | Category-Aware Validation Pattern | MEDIUM | refactor |
| 2026-01-13 | ADDED | Test sys.path Project Root Requirement | LOW | refactor |
| 2026-01-13 | ADDED | Module-Level Caching Pattern | LOW | refactor |
| 2026-01-13 | PROMOTED | Module-Level Caching Pattern | LOW→MEDIUM | refactor |
| 2026-01-13 | ADDED | Shared Module-Level Cache Across MCP Tools | MEDIUM | refactor |
| 2026-01-13 | ADDED | get_send_types_constraints v2.0.0 learnings | MEDIUM | refactor |
| 2026-01-13 | ADDED | Hybrid Cache Strategy for Different Access Patterns | LOW | refactor |
| 2026-01-13 | ADDED | Explicit Column Lists Over SELECT * | LOW | refactor |
| 2026-01-13 | ADDED | Breaking Changes Acceptable for Secondary Tools | LOW | refactor |
| 2026-01-13 | ADDED | get_send_types v2.0.0 learnings | LOW | refactor |
| 2026-01-13 | ADDED | Revenue Diversity Gate Requires 4+ Types | HIGH | validation |
| 2026-01-13 | ADDED | Generator-to-Persistence Schema Field Mismatch | LOW | validation |
| 2026-01-06 | CREATED | Initial structure | - | system |

---

## Integration Hooks

### Validation Phase (Immediate)
```python
if certificate.status == "REJECTED":
    add_learning(confidence="HIGH", source="validation",
                 violation=certificate.violations, pattern=context)
if certificate.quality_score >= 85:
    add_learning(confidence="MEDIUM", source="validation",
                 quality=certificate.quality_score, pattern=decisions)
```

### Performance Feedback (7-14 days delayed)
```python
if rps > baseline * 1.15:
    add_learning(confidence="MEDIUM", source="performance",
                 impact=f"+{delta}% RPS", pattern=schedule_decisions)
```

### Promotion Rules
| LOW -> MEDIUM | Sample >= 10 AND 80% consistent |
| MEDIUM -> HIGH | User confirms OR 5+ validation successes |

---

## Agent Usage

- **schedule-generator**: Read HIGH/MEDIUM at start, apply corrections
- **schedule-validator**: Reference when scoring, generate learnings on reject
- **reflect command**: Extract session learnings, update stats, Git commit

---

*Ready to receive learnings*
