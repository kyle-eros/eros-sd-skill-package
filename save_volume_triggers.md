# save_volume_triggers MCP Tool v3.0.0 Refactoring Document

**Tool Name**: `save_volume_triggers`
**Version Upgrade**: 2.0.0 -> 3.0.0
**Date**: 2026-01-12
**Author**: Refactoring Specialist

---

## Quick Reference

| Attribute | Value |
|-----------|-------|
| File Path | `/Users/kylemerriman/Developer/eros-sd-skill-package/mcp_server/main.py` |
| Function | `save_volume_triggers(creator_id: str, triggers: list) -> dict` |
| Line Range | 2549-2691 (143 lines) |
| MCP Name | `mcp__eros-db__save_volume_triggers` |
| Validator | `volume_utils.validate_trigger()` (lines 489-567) |
| Pipeline Phase | Post-pipeline (called by preflight after trigger detection) |
| Target Line Count | ~200-220 lines (estimated +50% for new features) |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
3. [Target Architecture](#3-target-architecture)
4. [Implementation Phases](#4-implementation-phases)
5. [Database Changes](#5-database-changes)
6. [Testing Strategy](#6-testing-strategy)
7. [Documentation Updates](#7-documentation-updates)
8. [Verification Checklist](#8-verification-checklist)
9. [Rollback Plan](#9-rollback-plan)
10. [Future Work](#10-future-work)

---

## 1. Executive Summary

### What This Refactor Accomplishes

- **Detection History Tracking**: Add `detection_count` and `first_detected_at` columns to track trigger re-detection patterns over time
- **UPSERT Pattern Upgrade**: Replace `INSERT OR REPLACE` with `ON CONFLICT DO UPDATE` to preserve historical data and increment counters
- **Structured Return IDs**: Separate `created_ids` and `updated_ids` in response for complete audit trail
- **Enhanced Metadata**: Add `persisted_at`, `execution_ms`, and `triggers_hash` for observability
- **Overwrite Warnings**: Warn on direction flip (boost to reduce or vice versa) and large delta (>50%) changes

### Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Backward Compatibility | 100% | All existing callers work without modification |
| Test Coverage | >90% | `pytest --cov` on trigger-related tests |
| Transaction Safety | Zero partial writes | All-or-nothing batch semantics verified |
| Detection Tracking | Working | `detection_count` increments on re-detection |
| Response Schema | Complete | All new fields present and documented |
| Performance | <50ms | `execution_ms` metric in response |

---

## 2. Current State Analysis

### Current Implementation Overview (v2.0.0)

**Location**: `/Users/kylemerriman/Developer/eros-sd-skill-package/mcp_server/main.py` lines 2549-2691

**What Works Well**:
- Batch validation with all-or-nothing semantics (lines 2617-2641)
- Creator ID resolution supporting both `creator_id` and `page_name` (lines 2599-2615)
- Comprehensive trigger validation via `validate_trigger()` (lines 2622-2629)
- Warning collection without rejection for edge cases (lines 2626-2627)
- Proper `metrics_json` serialization (line 2670)

**What Is Missing**:

| Gap | Impact | Lines Affected |
|-----|--------|----------------|
| No detection count tracking | Cannot identify frequently-detected triggers | N/A (new feature) |
| No original detection timestamp | Cannot calculate trigger age accurately | N/A (new feature) |
| `INSERT OR REPLACE` destroys history | Re-detection loses all prior context | 2649-2671 |
| No explicit transaction control | Implicit transaction may not rollback on all failures | 2649-2674 |
| No created vs updated distinction | Cannot audit trigger lifecycle | 2676-2681 |
| No execution timing | Cannot monitor tool performance | N/A (new feature) |
| No overwrite warnings | Silent overwrites may indicate bugs | N/A (new feature) |
| No structured layer comments | Code organization unclear | 2549-2691 |

### Current SQL Pattern (Lines 2649-2671)

```sql
-- CURRENT: INSERT OR REPLACE destroys existing row entirely
INSERT OR REPLACE INTO volume_triggers (
    creator_id,
    content_type,
    trigger_type,
    adjustment_multiplier,
    confidence,
    reason,
    expires_at,
    detected_at,
    is_active,
    metrics_json
) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 1, ?)
```

**Problem**: When a trigger for the same `(creator_id, content_type, trigger_type)` tuple is re-detected:
1. The entire row is deleted and recreated
2. `trigger_id` changes (auto-increment generates new ID)
3. Original `detected_at` is lost
4. No record of how many times this trigger was detected

### Current Return Schema (Lines 2676-2681)

```json
{
    "success": true,
    "triggers_saved": 2,
    "creator_id": "maya_hill",
    "creator_id_resolved": "abc123-uuid",
    "warnings": ["trigger[0]: extreme multiplier 0.55 - verify intentional"]
}
```

**Missing Fields**:
- `created_ids`: Which triggers were newly inserted
- `updated_ids`: Which triggers were updated (re-detected)
- `persisted_at`: Timestamp of persistence operation
- `execution_ms`: Performance metric
- `triggers_hash`: Content hash for audit trail

### Current Index (Partial Unique)

From `/Users/kylemerriman/Developer/eros-sd-skill-package/python/tests/test_mcp_triggers_integration.py` lines 74-78:

```sql
-- CURRENT: Partial unique index (WHERE is_active = 1)
CREATE UNIQUE INDEX idx_volume_triggers_natural_key
ON volume_triggers(creator_id, content_type, trigger_type)
WHERE is_active = 1
```

**Problem**: This partial index does NOT work with `ON CONFLICT` clause because SQLite's ON CONFLICT only works with FULL unique constraints, not partial indexes.

---

## 3. Target Architecture

### New Return Schema (v3.0.0)

```json
{
    "success": true,
    "triggers_saved": 3,
    "created_ids": [142, 143],
    "updated_ids": [87],
    "creator_id": "maya_hill",
    "creator_id_resolved": "abc123-uuid",
    "warnings": [
        "trigger[0]: extreme multiplier 0.55 - verify intentional",
        "trigger[2]: direction flip detected (1.20 -> 0.85) for lingerie/HIGH_PERFORMER"
    ],
    "overwrite_warnings": [
        {
            "trigger_id": 87,
            "content_type": "lingerie",
            "trigger_type": "HIGH_PERFORMER",
            "old_multiplier": 1.20,
            "new_multiplier": 0.85,
            "direction_flip": true,
            "delta_percent": -29.2
        }
    ],
    "metadata": {
        "persisted_at": "2026-01-12T14:30:00.000Z",
        "execution_ms": 23.5,
        "triggers_hash": "sha256:a1b2c3d4e5f6"
    }
}
```

### New Trigger Schema Fields

```json
{
    "trigger_id": 87,
    "content_type": "lingerie",
    "trigger_type": "HIGH_PERFORMER",
    "adjustment_multiplier": 1.20,
    "confidence": "high",
    "reason": "Conversion 7.2%",
    "expires_at": "2026-01-19T14:30:00Z",
    "detected_at": "2026-01-12T14:30:00Z",
    "is_active": 1,
    "metrics_json": {"detected": {"conversion_rate": 7.2}},
    "detection_count": 3,
    "first_detected_at": "2026-01-05T10:15:00Z"
}
```

### Data Flow Diagram

```
+------------------------+
|   Caller (preflight)   |
|   triggers: list       |
+------------------------+
            |
            v
+------------------------+
| LAYER 1: INPUT         |
| - Validate creator_id  |
| - Empty list check     |
+------------------------+
            |
            v
+------------------------+
| LAYER 2: VALIDATION    |
| - validate_trigger()   |
| - Collect all errors   |
| - All-or-nothing batch |
+------------------------+
            |
            v
+------------------------+
| LAYER 3: PRE-QUERY     |
| - Query existing rows  |
| - Detect overwrites    |
| - Direction flip check |
| - Large delta check    |
+------------------------+
            |
            v
+------------------------+
| LAYER 4: PERSISTENCE   |
| - BEGIN IMMEDIATE      |
| - ON CONFLICT UPSERT   |
| - Track created/updated|
| - COMMIT or ROLLBACK   |
+------------------------+
            |
            v
+------------------------+
| LAYER 5: RESPONSE      |
| - Build metadata       |
| - Compute triggers_hash|
| - Return structured    |
+------------------------+
```

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Unique Constraint | FULL (not partial WHERE is_active=1) | ON CONFLICT only works with full unique constraints |
| History Tracking | Detection counter, NOT soft-delete | Avoids row proliferation, simpler queries |
| Transaction | Full rollback on any failure | Data integrity for batch operations |
| Return IDs | `{created_ids: [], updated_ids: []}` | Maximum audit trail for debugging |
| Timeout | SQLite busy_timeout only | Python timeout risks mid-transaction abort |
| Hash Input | Normalized triggers (post-validation) | Represents actual persisted state |
| Batch Validation | All-or-nothing (unchanged) | Preflight bugs should fail loudly |
| Overwrite Warnings | Direction flip + large delta only | Sparse, actionable warnings |

---

## 4. Implementation Phases

### Phase 1: Database Migration (Prerequisite)

**Objective**: Add new columns and fix unique constraint for ON CONFLICT support.

**Files Modified**:
- Database: `volume_triggers` table schema

**Steps**:

#### 1.1 Backup Database

```bash
# Run from project root
cp /Users/kylemerriman/Developer/eros-sd-skill-package/data/eros_sd_main.db \
   /Users/kylemerriman/Developer/eros-sd-skill-package/data/eros_sd_main.db.backup.$(date +%Y%m%d_%H%M%S)
```

#### 1.2 Add New Columns

```sql
-- Add detection_count column
ALTER TABLE volume_triggers ADD COLUMN detection_count INTEGER DEFAULT 1;

-- Add first_detected_at column
ALTER TABLE volume_triggers ADD COLUMN first_detected_at TEXT;

-- Backfill first_detected_at from existing detected_at
UPDATE volume_triggers
SET first_detected_at = detected_at
WHERE first_detected_at IS NULL;
```

#### 1.3 Fix Unique Constraint

```sql
-- Drop partial unique index (does not work with ON CONFLICT)
DROP INDEX IF EXISTS idx_volume_triggers_natural_key;

-- Create full unique index (works with ON CONFLICT)
CREATE UNIQUE INDEX idx_volume_triggers_natural_key
ON volume_triggers (creator_id, content_type, trigger_type);
```

#### 1.4 Verification SQL

```sql
-- Verify columns exist
PRAGMA table_info(volume_triggers);

-- Verify index is non-partial
SELECT * FROM sqlite_master
WHERE type = 'index'
AND name = 'idx_volume_triggers_natural_key';

-- Verify no WHERE clause in index definition
-- Expected: CREATE UNIQUE INDEX idx_volume_triggers_natural_key ON volume_triggers (creator_id, content_type, trigger_type)

-- Verify backfill worked
SELECT COUNT(*) FROM volume_triggers WHERE first_detected_at IS NULL;
-- Expected: 0
```

**Commit Message**:
```
chore(db): add detection_count and first_detected_at columns

- Add detection_count INTEGER DEFAULT 1 for re-detection tracking
- Add first_detected_at TEXT for original detection timestamp
- Backfill first_detected_at from existing detected_at values
- Replace partial unique index with full unique index for ON CONFLICT
- Prerequisite for save_volume_triggers v3.0.0

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

**Rollback SQL**:
```sql
-- Rollback Phase 1 (if needed)
-- Note: Cannot remove columns in SQLite, would need table recreation
-- For partial rollback, restore the partial index:
DROP INDEX IF EXISTS idx_volume_triggers_natural_key;
CREATE UNIQUE INDEX idx_volume_triggers_natural_key
ON volume_triggers (creator_id, content_type, trigger_type)
WHERE is_active = 1;
```

---

### Phase 2: Code Refactoring (Main Work)

**Objective**: Implement save_volume_triggers v3.0.0 with all enhancements.

**File Modified**: `/Users/kylemerriman/Developer/eros-sd-skill-package/mcp_server/main.py`

**Line Range**: 2549-2691 (replace entire function)

**Steps**:

#### 2.1 Add LAYER Comments Structure

Add 4-layer structure comments matching save_schedule pattern.

#### 2.2 Add Timing Instrumentation

```python
# At function start
from datetime import datetime
start_time = datetime.now()

# At function end (before return)
execution_ms = (datetime.now() - start_time).total_seconds() * 1000
```

#### 2.3 Query Existing Triggers Before INSERT

```python
# LAYER 3: PRE-QUERY - Check existing triggers for overwrite detection
existing_triggers = {}
if validated:
    placeholders = ",".join("?" * len(validated))
    content_types = [t["content_type"] for t in validated]
    trigger_types = [t["trigger_type"] for t in validated]

    rows = conn.execute(f"""
        SELECT trigger_id, content_type, trigger_type, adjustment_multiplier,
               detection_count, first_detected_at
        FROM volume_triggers
        WHERE creator_id = ?
          AND (content_type, trigger_type) IN (
              SELECT ?, ? FROM (SELECT 1) WHERE 1=0
              UNION ALL SELECT ?, ?
              -- ... dynamic generation for each trigger
          )
    """, params).fetchall()

    for row in rows:
        key = (row[1], row[2])  # (content_type, trigger_type)
        existing_triggers[key] = {
            "trigger_id": row[0],
            "adjustment_multiplier": row[3],
            "detection_count": row[4],
            "first_detected_at": row[5]
        }
```

#### 2.4 Replace INSERT OR REPLACE with ON CONFLICT

**Before** (lines 2649-2671):
```python
conn.execute("""
    INSERT OR REPLACE INTO volume_triggers (
        creator_id,
        content_type,
        trigger_type,
        adjustment_multiplier,
        confidence,
        reason,
        expires_at,
        detected_at,
        is_active,
        metrics_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 1, ?)
""", (
    creator_pk,
    t["content_type"],
    t["trigger_type"],
    t["adjustment_multiplier"],
    t["confidence"],
    t["reason"],
    t["expires_at"],
    json.dumps(t["metrics_json"]) if t["metrics_json"] else None
))
```

**After** (v3.0.0):
```python
cursor = conn.execute("""
    INSERT INTO volume_triggers (
        creator_id,
        content_type,
        trigger_type,
        adjustment_multiplier,
        confidence,
        reason,
        expires_at,
        detected_at,
        is_active,
        metrics_json,
        detection_count,
        first_detected_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 1, ?, 1, datetime('now'))
    ON CONFLICT (creator_id, content_type, trigger_type) DO UPDATE SET
        adjustment_multiplier = excluded.adjustment_multiplier,
        confidence = CASE
            WHEN excluded.confidence > volume_triggers.confidence THEN excluded.confidence
            ELSE volume_triggers.confidence
        END,
        reason = excluded.reason,
        expires_at = excluded.expires_at,
        detected_at = datetime('now'),
        is_active = 1,
        metrics_json = excluded.metrics_json,
        detection_count = volume_triggers.detection_count + 1
    RETURNING trigger_id,
              CASE WHEN detection_count = 1 THEN 'created' ELSE 'updated' END as operation
""", (
    creator_pk,
    t["content_type"],
    t["trigger_type"],
    t["adjustment_multiplier"],
    t["confidence"],
    t["reason"],
    t["expires_at"],
    json.dumps(t["metrics_json"]) if t["metrics_json"] else None
))

result_row = cursor.fetchone()
trigger_id = result_row[0]
operation = result_row[1]

if operation == 'created':
    created_ids.append(trigger_id)
else:
    updated_ids.append(trigger_id)
```

#### 2.5 Add Direction Flip and Large Delta Warnings

```python
# LAYER 3.5: OVERWRITE ANALYSIS
overwrite_warnings = []
for t in validated:
    key = (t["content_type"], t["trigger_type"])
    if key in existing_triggers:
        existing = existing_triggers[key]
        old_mult = existing["adjustment_multiplier"]
        new_mult = t["adjustment_multiplier"]

        # Direction flip detection
        direction_flip = (old_mult > 1.0 and new_mult < 1.0) or \
                        (old_mult < 1.0 and new_mult > 1.0)

        # Large delta detection (>50% change)
        if old_mult != 0:
            delta_percent = ((new_mult - old_mult) / old_mult) * 100
        else:
            delta_percent = 100.0 if new_mult != 0 else 0.0

        large_delta = abs(delta_percent) > 50

        if direction_flip or large_delta:
            overwrite_warnings.append({
                "trigger_id": existing["trigger_id"],
                "content_type": t["content_type"],
                "trigger_type": t["trigger_type"],
                "old_multiplier": old_mult,
                "new_multiplier": new_mult,
                "direction_flip": direction_flip,
                "delta_percent": round(delta_percent, 1)
            })

            # Also add to warnings list for backward compatibility
            if direction_flip:
                all_warnings.append(
                    f"direction flip detected ({old_mult} -> {new_mult}) "
                    f"for {t['content_type']}/{t['trigger_type']}"
                )
```

#### 2.6 Add Large Batch Warning

```python
# LAYER 1.5: BATCH SIZE CHECK
LARGE_BATCH_THRESHOLD = 20
if len(triggers) > LARGE_BATCH_THRESHOLD:
    all_warnings.append(
        f"Large batch: {len(triggers)} triggers (threshold: {LARGE_BATCH_THRESHOLD}). "
        f"Consider reviewing trigger detection logic."
    )
```

#### 2.7 Add Transaction Control

```python
# LAYER 4: PERSISTENCE with explicit transaction
try:
    conn.execute("BEGIN IMMEDIATE")

    created_ids = []
    updated_ids = []

    for t in validated:
        # ... ON CONFLICT INSERT logic ...

    conn.execute("COMMIT")

except Exception as e:
    conn.execute("ROLLBACK")
    logger.error(f"save_volume_triggers rollback: {e}")
    raise
```

#### 2.8 Add Hash Computation

```python
# LAYER 5: RESPONSE - Compute triggers hash
def compute_triggers_hash(validated_triggers: list) -> str:
    """Compute deterministic hash of normalized triggers."""
    import hashlib

    # Normalize for hashing: sort by (content_type, trigger_type)
    sorted_triggers = sorted(
        validated_triggers,
        key=lambda t: (t["content_type"], t["trigger_type"])
    )

    # Include only fields that affect behavior
    hash_inputs = [
        {
            "content_type": t["content_type"],
            "trigger_type": t["trigger_type"],
            "adjustment_multiplier": t["adjustment_multiplier"],
            "confidence": t["confidence"],
            "expires_at": t["expires_at"]
        }
        for t in sorted_triggers
    ]

    hash_str = json.dumps(hash_inputs, sort_keys=True)
    return hashlib.sha256(hash_str.encode()).hexdigest()[:16]

triggers_hash = compute_triggers_hash(validated)
```

#### 2.9 Construct New Return Schema

```python
# LAYER 5: RESPONSE
execution_ms = (datetime.now() - start_time).total_seconds() * 1000

return {
    "success": True,
    "triggers_saved": len(created_ids) + len(updated_ids),
    "created_ids": created_ids,
    "updated_ids": updated_ids,
    "creator_id": creator_id,
    "creator_id_resolved": creator_pk,
    "warnings": all_warnings if all_warnings else None,
    "overwrite_warnings": overwrite_warnings if overwrite_warnings else None,
    "metadata": {
        "persisted_at": datetime.now().isoformat() + "Z",
        "execution_ms": round(execution_ms, 2),
        "triggers_hash": f"sha256:{triggers_hash}"
    }
}
```

**Commit Message**:
```
refactor(save_volume_triggers): implement v3.0.0 with detection tracking

BREAKING CHANGE: Return schema now includes created_ids and updated_ids

- Replace INSERT OR REPLACE with ON CONFLICT DO UPDATE
- Add detection_count increment on re-detection
- Preserve first_detected_at on updates
- Add structured overwrite_warnings for direction flip and large delta
- Add metadata block with persisted_at, execution_ms, triggers_hash
- Add explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK transaction control
- Add 4-layer structure comments (INPUT, VALIDATION, PERSISTENCE, RESPONSE)
- Add large batch warning (>20 triggers)

Backward compatible: warnings field preserved, new fields are additive

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

---

### Phase 3: get_active_volume_triggers Update (Minor)

**Objective**: Add new columns to SELECT and return in response.

**File Modified**: `/Users/kylemerriman/Developer/eros-sd-skill-package/mcp_server/main.py`

**Line Range**: 1822-1871 (SELECT query and object construction)

**Steps**:

#### 3.1 Update SELECT Query

**Before** (lines 1822-1842):
```sql
SELECT
    vt.trigger_id,
    vt.content_type,
    vt.trigger_type,
    vt.adjustment_multiplier,
    vt.confidence,
    vt.reason,
    vt.expires_at,
    vt.detected_at,
    vt.metrics_json,
    vt.applied_count,
    vt.last_applied_at,
    CAST(julianday(vt.expires_at) - julianday('now') AS INTEGER) as days_until_expiry,
    CAST(julianday('now') - julianday(vt.detected_at) AS INTEGER) as days_since_detected
FROM volume_triggers vt
...
```

**After** (v3.0.0):
```sql
SELECT
    vt.trigger_id,
    vt.content_type,
    vt.trigger_type,
    vt.adjustment_multiplier,
    vt.confidence,
    vt.reason,
    vt.expires_at,
    vt.detected_at,
    vt.metrics_json,
    vt.applied_count,
    vt.last_applied_at,
    vt.detection_count,
    vt.first_detected_at,
    CAST(julianday(vt.expires_at) - julianday('now') AS INTEGER) as days_until_expiry,
    CAST(julianday('now') - julianday(vt.detected_at) AS INTEGER) as days_since_detected,
    CAST(julianday('now') - julianday(vt.first_detected_at) AS INTEGER) as days_since_first_detected
FROM volume_triggers vt
...
```

#### 3.2 Update Trigger Object Construction

**Before** (lines 1856-1871):
```python
triggers.append({
    "trigger_id": row[0],
    "content_type": row[1],
    "trigger_type": row[2],
    "adjustment_multiplier": row[3],
    "confidence": row[4],
    "reason": row[5],
    "expires_at": row[6],
    "detected_at": row[7],
    "metrics_json": metrics_json,
    "source": "database",
    "applied_count": row[9] or 0,
    "last_applied_at": row[10],
    "days_until_expiry": row[11],
    "days_since_detected": row[12]
})
```

**After** (v3.0.0):
```python
triggers.append({
    "trigger_id": row[0],
    "content_type": row[1],
    "trigger_type": row[2],
    "adjustment_multiplier": row[3],
    "confidence": row[4],
    "reason": row[5],
    "expires_at": row[6],
    "detected_at": row[7],
    "metrics_json": metrics_json,
    "source": "database",
    "applied_count": row[9] or 0,
    "last_applied_at": row[10],
    "detection_count": row[11] or 1,
    "first_detected_at": row[12],
    "days_until_expiry": row[13],
    "days_since_detected": row[14],
    "days_since_first_detected": row[15]
})
```

**Commit Message**:
```
feat(get_active_volume_triggers): return detection_count and first_detected_at

- Add detection_count to SELECT (tracks re-detection frequency)
- Add first_detected_at to SELECT (original detection timestamp)
- Add days_since_first_detected calculated field
- Update trigger object construction for new column indices

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

---

### Phase 4: Tests (Verification)

**Objective**: Add comprehensive tests for v3.0.0 features.

**File Modified**: `/Users/kylemerriman/Developer/eros-sd-skill-package/python/tests/test_mcp_triggers_integration.py`

**Tests to Add**:

#### 4.1 Transaction Rollback Tests

```python
class TestTransactionRollback:
    """Tests for transaction safety."""

    def test_rollback_on_db_error(self, test_db, monkeypatch):
        """Verify full rollback on database error mid-batch."""
        pass

    def test_no_partial_writes_on_validation_error(self, test_db, monkeypatch):
        """Verify zero triggers saved if any validation fails."""
        pass
```

#### 4.2 ON CONFLICT Tests

```python
class TestOnConflictBehavior:
    """Tests for UPSERT behavior."""

    def test_on_conflict_updates_existing_trigger(self, test_db, monkeypatch):
        """Re-detection updates existing row instead of creating new."""
        pass

    def test_on_conflict_increments_detection_count(self, test_db, monkeypatch):
        """detection_count increments from 1 to 2 on re-detection."""
        pass

    def test_on_conflict_preserves_first_detected_at(self, test_db, monkeypatch):
        """first_detected_at unchanged on re-detection."""
        pass

    def test_on_conflict_reactivates_inactive_trigger(self, test_db, monkeypatch):
        """Trigger with is_active=0 is reactivated and updated."""
        pass

    def test_on_conflict_updates_detected_at(self, test_db, monkeypatch):
        """detected_at is updated to current time on re-detection."""
        pass
```

#### 4.3 Return Schema Tests

```python
class TestReturnSchema:
    """Tests for v3.0.0 response schema."""

    def test_created_ids_on_new_triggers(self, test_db, monkeypatch):
        """New triggers appear in created_ids list."""
        pass

    def test_updated_ids_on_re_detection(self, test_db, monkeypatch):
        """Re-detected triggers appear in updated_ids list."""
        pass

    def test_created_and_updated_ids_mixed_batch(self, test_db, monkeypatch):
        """Batch with new and existing triggers correctly separates IDs."""
        pass

    def test_metadata_block_complete(self, test_db, monkeypatch):
        """metadata contains persisted_at, execution_ms, triggers_hash."""
        pass

    def test_triggers_hash_is_deterministic(self, test_db, monkeypatch):
        """Same triggers produce same hash."""
        pass
```

#### 4.4 Overwrite Warning Tests

```python
class TestOverwriteWarnings:
    """Tests for direction flip and large delta warnings."""

    def test_direction_flip_warning_boost_to_reduce(self, test_db, monkeypatch):
        """Warning when multiplier goes from >1.0 to <1.0."""
        pass

    def test_direction_flip_warning_reduce_to_boost(self, test_db, monkeypatch):
        """Warning when multiplier goes from <1.0 to >1.0."""
        pass

    def test_large_delta_warning_over_50_percent(self, test_db, monkeypatch):
        """Warning when multiplier changes by more than 50%."""
        pass

    def test_no_warning_for_small_delta(self, test_db, monkeypatch):
        """No warning when multiplier changes by less than 50%."""
        pass

    def test_overwrite_warnings_structure(self, test_db, monkeypatch):
        """overwrite_warnings contains correct fields."""
        pass
```

#### 4.5 Batch Warning Tests

```python
class TestBatchWarnings:
    """Tests for large batch warning."""

    def test_large_batch_warning_over_20(self, test_db, monkeypatch):
        """Warning when batch contains more than 20 triggers."""
        pass

    def test_no_warning_for_normal_batch(self, test_db, monkeypatch):
        """No warning when batch contains 20 or fewer triggers."""
        pass
```

#### 4.6 get_active_volume_triggers Tests

```python
class TestGetActiveVolumeTriggers:
    """Tests for get_active_volume_triggers new fields."""

    def test_detection_count_in_response(self, test_db, monkeypatch):
        """detection_count field present in trigger objects."""
        pass

    def test_first_detected_at_in_response(self, test_db, monkeypatch):
        """first_detected_at field present in trigger objects."""
        pass

    def test_days_since_first_detected(self, test_db, monkeypatch):
        """days_since_first_detected calculated correctly."""
        pass
```

**Commit Message**:
```
test(save_volume_triggers): add v3.0.0 integration tests

- Add TestTransactionRollback: rollback on DB error, no partial writes
- Add TestOnConflictBehavior: UPSERT, detection_count, first_detected_at
- Add TestReturnSchema: created_ids, updated_ids, metadata block
- Add TestOverwriteWarnings: direction flip, large delta detection
- Add TestBatchWarnings: large batch (>20) warning
- Add TestGetActiveVolumeTriggers: new fields in response

Total: 20+ new test functions covering all v3.0.0 features

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

---

### Phase 5: Documentation (Finalization)

**Objective**: Update all documentation to reflect v3.0.0 changes.

**Files Modified**:
- `/Users/kylemerriman/Developer/eros-sd-skill-package/skills/eros-schedule-generator/REFERENCE/triggers.md`
- `/Users/kylemerriman/Developer/eros-sd-skill-package/CHANGELOG.md`

**Steps**:

#### 5.1 Update triggers.md

**Changes to Make**:

1. Update version header:
```markdown
**Version**: 7.0.0
**MCP Tool Version**: 3.0.0
**Updated**: 2026-01-12
```

2. Update Trigger Schema section to include new fields:
```json
{
    "trigger_id": 87,
    "content_type": "lingerie",
    "trigger_type": "HIGH_PERFORMER",
    "adjustment_multiplier": 1.20,
    "confidence": "high",
    "reason": "Conversion 7.2%",
    "expires_at": "2026-01-19T14:30:00Z",
    "detected_at": "2026-01-12T14:30:00Z",
    "first_detected_at": "2026-01-05T10:15:00Z",
    "metrics_json": {"detected": {"conversion_rate": 7.2}},
    "source": "database",
    "applied_count": 0,
    "last_applied_at": null,
    "detection_count": 3,
    "days_until_expiry": 7,
    "days_since_detected": 0,
    "days_since_first_detected": 7
}
```

3. Add save_volume_triggers Response section:
```markdown
### `save_volume_triggers` Response (v3.0)

```json
{
    "success": true,
    "triggers_saved": 3,
    "created_ids": [142, 143],
    "updated_ids": [87],
    "creator_id": "maya_hill",
    "creator_id_resolved": "abc123-uuid",
    "warnings": [],
    "overwrite_warnings": [
        {
            "trigger_id": 87,
            "content_type": "lingerie",
            "trigger_type": "HIGH_PERFORMER",
            "old_multiplier": 1.20,
            "new_multiplier": 0.85,
            "direction_flip": true,
            "delta_percent": -29.2
        }
    ],
    "metadata": {
        "persisted_at": "2026-01-12T14:30:00.000Z",
        "execution_ms": 23.5,
        "triggers_hash": "sha256:a1b2c3d4e5f6"
    }
}
```
```

4. Add New Fields (v3.0) table:
```markdown
### New Fields (v3.0)

| Field | Type | Description |
|-------|------|-------------|
| `detection_count` | int | Number of times trigger re-detected (starts at 1) |
| `first_detected_at` | string | Original detection timestamp (never changes) |
| `days_since_first_detected` | int | Days since first detection |
| `created_ids` | array | IDs of newly created triggers |
| `updated_ids` | array | IDs of updated (re-detected) triggers |
| `overwrite_warnings` | array | Direction flip and large delta warnings |
| `metadata.execution_ms` | float | Tool execution time in milliseconds |
| `metadata.triggers_hash` | string | Deterministic hash of persisted triggers |
```

5. Update MCP Tools table:
```markdown
| Tool | Purpose | Version |
|------|---------|---------|
| `get_active_volume_triggers` | Retrieve active triggers with compound calculation | 3.0.0 |
| `save_volume_triggers` | Persist new trigger detections with validation | 3.0.0 |
```

#### 5.2 Update CHANGELOG.md

Add entry at top of file (after `## [Unreleased]`):

```markdown
## [3.0.0] - 2026-01-12

### Changed
- **BREAKING (internal)**: `save_volume_triggers` return schema now includes `created_ids` and `updated_ids`
- Replace `INSERT OR REPLACE` with `ON CONFLICT DO UPDATE` for trigger persistence
- Unique index on volume_triggers changed from partial to full (required for ON CONFLICT)

### Added
- `detection_count` column: Tracks how many times a trigger has been re-detected
- `first_detected_at` column: Preserves original detection timestamp
- `overwrite_warnings` in save response: Direction flip and large delta detection
- `metadata` block in save response: `persisted_at`, `execution_ms`, `triggers_hash`
- Large batch warning when >20 triggers in single call
- `days_since_first_detected` calculated field in get_active_volume_triggers
- Explicit transaction control with BEGIN IMMEDIATE / COMMIT / ROLLBACK
- 4-layer structure comments in save_volume_triggers

### Fixed
- Trigger re-detection no longer destroys history (detection_count preserved)
- Original detection timestamp preserved on re-detection

### Database Migration
- `ALTER TABLE volume_triggers ADD COLUMN detection_count INTEGER DEFAULT 1`
- `ALTER TABLE volume_triggers ADD COLUMN first_detected_at TEXT`
- Backfill: `UPDATE volume_triggers SET first_detected_at = detected_at WHERE first_detected_at IS NULL`
- Index change: `DROP INDEX idx_volume_triggers_natural_key` (partial) -> `CREATE UNIQUE INDEX` (full)
```

**Commit Message**:
```
docs: update save_volume_triggers to v3.0.0

- Update triggers.md to version 7.0.0 with new schema fields
- Add save_volume_triggers response schema documentation
- Document detection_count, first_detected_at, overwrite_warnings
- Update MCP tools version table
- Add CHANGELOG entry for v3.0.0 with full change list
- Document database migration steps

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

---

## 5. Database Changes

### Full Migration SQL

```sql
-- ============================================================
-- save_volume_triggers v3.0.0 Migration Script
-- Run against: eros_sd_main.db
-- Date: 2026-01-12
-- ============================================================

-- STEP 1: Backup verification (run manually first)
-- cp eros_sd_main.db eros_sd_main.db.backup.YYYYMMDD_HHMMSS

-- STEP 2: Add detection_count column
-- Tracks how many times this trigger has been detected
-- Starts at 1 for new triggers, increments on re-detection
ALTER TABLE volume_triggers ADD COLUMN detection_count INTEGER DEFAULT 1;

-- STEP 3: Add first_detected_at column
-- Preserves the original detection timestamp
-- Never updated on re-detection (unlike detected_at)
ALTER TABLE volume_triggers ADD COLUMN first_detected_at TEXT;

-- STEP 4: Backfill first_detected_at from detected_at
-- For existing triggers, original detection = detected_at
UPDATE volume_triggers
SET first_detected_at = detected_at
WHERE first_detected_at IS NULL;

-- STEP 5: Drop partial unique index
-- Partial indexes (WHERE clause) do not work with ON CONFLICT
DROP INDEX IF EXISTS idx_volume_triggers_natural_key;

-- STEP 6: Create full unique index
-- Required for ON CONFLICT (creator_id, content_type, trigger_type) DO UPDATE
CREATE UNIQUE INDEX idx_volume_triggers_natural_key
ON volume_triggers (creator_id, content_type, trigger_type);

-- STEP 7: Verification queries
-- 7a: Verify columns exist
SELECT name, type, dflt_value
FROM pragma_table_info('volume_triggers')
WHERE name IN ('detection_count', 'first_detected_at');
-- Expected: 2 rows

-- 7b: Verify no NULL first_detected_at
SELECT COUNT(*) as null_count
FROM volume_triggers
WHERE first_detected_at IS NULL;
-- Expected: 0

-- 7c: Verify index is non-partial
SELECT sql
FROM sqlite_master
WHERE type = 'index'
AND name = 'idx_volume_triggers_natural_key';
-- Expected: No WHERE clause in output

-- 7d: Verify detection_count defaults
SELECT COUNT(*) as default_count
FROM volume_triggers
WHERE detection_count = 1 OR detection_count IS NULL;
-- Expected: Equal to total row count
```

### Rollback SQL

```sql
-- ============================================================
-- save_volume_triggers v3.0.0 ROLLBACK Script
-- Use if v3.0.0 deployment fails
-- ============================================================

-- Note: SQLite cannot DROP COLUMN, so columns remain
-- Code will simply ignore detection_count and first_detected_at

-- STEP 1: Restore partial unique index
DROP INDEX IF EXISTS idx_volume_triggers_natural_key;

CREATE UNIQUE INDEX idx_volume_triggers_natural_key
ON volume_triggers (creator_id, content_type, trigger_type)
WHERE is_active = 1;

-- STEP 2: Verify rollback
SELECT sql
FROM sqlite_master
WHERE type = 'index'
AND name = 'idx_volume_triggers_natural_key';
-- Expected: Should contain "WHERE is_active = 1"

-- STEP 3: Restore code from git
-- git checkout HEAD~1 -- mcp_server/main.py
```

---

## 6. Testing Strategy

### Test Matrix by Risk Level

#### CRITICAL (Must Pass Before Merge)

| Test Name | What It Verifies | File |
|-----------|-----------------|------|
| `test_rollback_on_db_error` | Transaction rollback on DB failure | test_mcp_triggers_integration.py |
| `test_on_conflict_updates_existing_trigger` | ON CONFLICT updates, not creates | test_mcp_triggers_integration.py |
| `test_on_conflict_increments_detection_count` | detection_count goes from 1 to 2 | test_mcp_triggers_integration.py |
| `test_on_conflict_reactivates_inactive_trigger` | is_active=0 -> is_active=1 on re-detect | test_mcp_triggers_integration.py |

#### HIGH (Must Pass Before Merge)

| Test Name | What It Verifies | File |
|-----------|-----------------|------|
| `test_created_ids_on_new_triggers` | New triggers in created_ids | test_mcp_triggers_integration.py |
| `test_updated_ids_on_re_detection` | Re-detected triggers in updated_ids | test_mcp_triggers_integration.py |
| `test_triggers_hash_is_deterministic` | Same input = same hash | test_mcp_triggers_integration.py |
| `test_no_partial_writes_on_validation_error` | All-or-nothing batch semantics | test_mcp_triggers_integration.py |

#### MEDIUM (Should Pass)

| Test Name | What It Verifies | File |
|-----------|-----------------|------|
| `test_direction_flip_warning_boost_to_reduce` | Warning when >1.0 -> <1.0 | test_mcp_triggers_integration.py |
| `test_large_delta_warning_over_50_percent` | Warning when delta > 50% | test_mcp_triggers_integration.py |
| `test_metadata_block_complete` | All metadata fields present | test_mcp_triggers_integration.py |
| `test_large_batch_warning_over_20` | Warning when >20 triggers | test_mcp_triggers_integration.py |

### Edge Cases to Cover

| Edge Case | Expected Behavior |
|-----------|-------------------|
| Empty triggers list | Return success with triggers_saved=0 |
| Unknown creator_id | Return error with CREATOR_NOT_FOUND |
| Mixed valid/invalid batch | Reject entire batch, triggers_saved=0 |
| Re-detect with same values | Update detected_at, increment detection_count |
| Re-detect with direction flip | Update and add overwrite_warning |
| 21 triggers in batch | Add large batch warning but proceed |
| Inactive trigger re-detected | Reactivate (is_active=1), increment count |

### Running Tests

```bash
# Run all trigger tests
cd /Users/kylemerriman/Developer/eros-sd-skill-package
pytest python/tests/test_mcp_triggers_integration.py -v

# Run with coverage
pytest python/tests/test_mcp_triggers_integration.py --cov=mcp_server --cov-report=term-missing

# Run specific test class
pytest python/tests/test_mcp_triggers_integration.py::TestOnConflictBehavior -v

# Run CRITICAL tests only (tagged)
pytest python/tests/test_mcp_triggers_integration.py -m critical -v
```

---

## 7. Documentation Updates

### Files to Update

| File | Section | Change |
|------|---------|--------|
| triggers.md | Header | Version 6.0.0 -> 7.0.0, MCP Tool Version 2.0.0 -> 3.0.0 |
| triggers.md | Trigger Schema (v2.0) | Rename to v3.0, add detection_count, first_detected_at |
| triggers.md | MCP Response Schema | Add save_volume_triggers response schema |
| triggers.md | New Fields | Add v3.0 fields table |
| triggers.md | MCP Tools | Update version numbers |
| CHANGELOG.md | Top | Add [3.0.0] section with all changes |
| CHANGELOG.md | Unreleased | Move any v3.0 items to [3.0.0] |

### triggers.md Diff Summary

```diff
- **Version**: 6.0.0
- **MCP Tool Version**: 2.0.0
- **Updated**: 2026-01-10
+ **Version**: 7.0.0
+ **MCP Tool Version**: 3.0.0
+ **Updated**: 2026-01-12

- ## Trigger Schema (v2.0)
+ ## Trigger Schema (v3.0)

  {
      "trigger_id": 42,
      ...
+     "detection_count": 3,
+     "first_detected_at": "2026-01-05T10:15:00Z",
+     "days_since_first_detected": 7
  }

+ ## save_volume_triggers Response (v3.0)
+
+ {
+     "success": true,
+     "created_ids": [...],
+     "updated_ids": [...],
+     "overwrite_warnings": [...],
+     "metadata": {...}
+ }

- | `get_active_volume_triggers` | ... | 2.0.0 |
- | `save_volume_triggers` | ... | 2.0.0 |
+ | `get_active_volume_triggers` | ... | 3.0.0 |
+ | `save_volume_triggers` | ... | 3.0.0 |
```

---

## 8. Verification Checklist

### Pre-Merge Checklist

#### Database Migration
- [ ] Backup created and verified
- [ ] `detection_count` column added
- [ ] `first_detected_at` column added
- [ ] Backfill completed (0 NULL values)
- [ ] Old partial index dropped
- [ ] New full index created
- [ ] Verification queries all pass

#### Code Changes
- [ ] LAYER comments added to save_volume_triggers
- [ ] ON CONFLICT replaces INSERT OR REPLACE
- [ ] created_ids and updated_ids tracked separately
- [ ] Timing instrumentation added
- [ ] Hash computation implemented
- [ ] Direction flip warning implemented
- [ ] Large delta warning implemented
- [ ] Large batch warning implemented
- [ ] Transaction control explicit (BEGIN/COMMIT/ROLLBACK)
- [ ] get_active_volume_triggers SELECT updated
- [ ] get_active_volume_triggers object construction updated

#### Tests
- [ ] All CRITICAL tests pass
- [ ] All HIGH tests pass
- [ ] All MEDIUM tests pass
- [ ] Coverage >90% on trigger code
- [ ] No regressions in existing tests

#### Documentation
- [ ] triggers.md updated to v7.0.0
- [ ] CHANGELOG.md updated with v3.0.0 section
- [ ] All new fields documented
- [ ] Response schema examples accurate

#### Final Verification
- [ ] Manual test: save new trigger -> created_ids populated
- [ ] Manual test: re-save same trigger -> updated_ids populated
- [ ] Manual test: detection_count increments
- [ ] Manual test: first_detected_at preserved
- [ ] Manual test: direction flip warning fires
- [ ] Manual test: get_active_volume_triggers returns new fields

---

## 9. Rollback Plan

### Phase Rollback Procedures

#### Rollback Phase 1 (Database)

```bash
# Option A: Restore from backup (cleanest)
cp /Users/kylemerriman/Developer/eros-sd-skill-package/data/eros_sd_main.db.backup.TIMESTAMP \
   /Users/kylemerriman/Developer/eros-sd-skill-package/data/eros_sd_main.db

# Option B: Restore partial index only (if columns are acceptable)
sqlite3 /Users/kylemerriman/Developer/eros-sd-skill-package/data/eros_sd_main.db <<EOF
DROP INDEX IF EXISTS idx_volume_triggers_natural_key;
CREATE UNIQUE INDEX idx_volume_triggers_natural_key
ON volume_triggers (creator_id, content_type, trigger_type)
WHERE is_active = 1;
EOF
```

#### Rollback Phase 2 (Code)

```bash
# Restore save_volume_triggers to v2.0.0
cd /Users/kylemerriman/Developer/eros-sd-skill-package
git checkout HEAD~1 -- mcp_server/main.py

# Or restore specific commit
git show <v2.0.0-commit-hash>:mcp_server/main.py > mcp_server/main.py
```

#### Rollback Phase 3 (get_active_volume_triggers)

```bash
# Already rolled back with Phase 2 (same file)
# If separated, restore specific function:
git checkout HEAD~1 -- mcp_server/main.py
```

#### Rollback Phase 4 (Tests)

```bash
# Tests are additive, no rollback needed
# If cleanup desired:
git checkout HEAD~1 -- python/tests/test_mcp_triggers_integration.py
```

#### Rollback Phase 5 (Documentation)

```bash
# Restore documentation
git checkout HEAD~1 -- skills/eros-schedule-generator/REFERENCE/triggers.md
git checkout HEAD~1 -- CHANGELOG.md
```

### Full Rollback (All Phases)

```bash
# 1. Restore database from backup
cp /Users/kylemerriman/Developer/eros-sd-skill-package/data/eros_sd_main.db.backup.TIMESTAMP \
   /Users/kylemerriman/Developer/eros-sd-skill-package/data/eros_sd_main.db

# 2. Revert all code changes (5 commits)
cd /Users/kylemerriman/Developer/eros-sd-skill-package
git revert --no-commit HEAD~4..HEAD
git commit -m "revert: rollback save_volume_triggers v3.0.0"

# 3. Verify rollback
pytest python/tests/test_mcp_triggers_integration.py -v
```

---

## 10. Future Work

### Out of Scope for v3.0.0

| Item | Description | Why Deferred |
|------|-------------|--------------|
| `applied_trigger_ids` in save_schedule | Track which triggers influenced each schedule | Separate concern, requires save_schedule changes |
| Trigger expiration sweep | Background job to deactivate expired triggers | Operational concern, not tool behavior |
| Trigger analytics dashboard | Visualize detection patterns | UI/reporting scope |
| Trigger confidence auto-adjustment | Increase confidence on repeated detection | Needs product decision |

### Potential v3.1.0 Enhancements

1. **Bulk re-detection optimization**: Query all existing triggers in single query instead of per-trigger
2. **Detection pattern analytics**: Add `detection_pattern` field (e.g., "consistent", "sporadic", "declining")
3. **Trigger merge logic**: When same content_type has conflicting triggers, auto-resolve
4. **Expiration warning**: Warn when >50% of batch triggers expire within 24 hours

### Related Documentation

- `/Users/kylemerriman/Developer/eros-sd-skill-package/docs/DOMAIN_KNOWLEDGE.md` - Business rules
- `/Users/kylemerriman/Developer/eros-sd-skill-package/mcp_server/volume_utils.py` - Validation logic
- `/Users/kylemerriman/Developer/eros-sd-skill-package/python/preflight.py` - Upstream caller
- `/Users/kylemerriman/Developer/eros-sd-skill-package/python/adapters.py` - Integration adapter

---

## Appendix A: Complete New Function Signature

```python
def save_volume_triggers(creator_id: str, triggers: list) -> dict:
    """Persists detected volume triggers with validation and detection tracking.

    MCP Name: mcp__eros-db__save_volume_triggers
    Version: 3.0.0

    CRITICAL: Uses ON CONFLICT DO UPDATE pattern to:
    - Preserve first_detected_at (original detection timestamp)
    - Increment detection_count on re-detection
    - Track created_ids vs updated_ids for audit trail

    Args:
        creator_id: Creator identifier (creator_id or page_name)
        triggers: List of trigger objects to persist

    Trigger Object Schema:
        REQUIRED: trigger_type, content_type, adjustment_multiplier
        OPTIONAL: confidence (default 'moderate'), reason, expires_at (default +7d), metrics_json

    Returns:
        dict with:
        - success: bool
        - triggers_saved: int (total created + updated)
        - created_ids: list[int] - IDs of newly created triggers
        - updated_ids: list[int] - IDs of re-detected triggers
        - creator_id: echoed input
        - creator_id_resolved: actual DB key used
        - warnings: list[str] if suspicious values detected
        - overwrite_warnings: list[dict] if direction flip or large delta detected
        - metadata: dict with persisted_at, execution_ms, triggers_hash
        - error: str if failed
        - validation_errors: list[str] if validation failed

    Validation:
        - Rejects entire batch if ANY trigger has invalid required fields
        - Defaults optional fields gracefully
        - Warns but accepts extreme multiplier values
        - Warns on direction flip (boost->reduce or vice versa)
        - Warns on large delta (>50% change)
        - Warns on large batch (>20 triggers)

    Transaction Safety:
        - Uses BEGIN IMMEDIATE for exclusive write lock
        - Full ROLLBACK on any failure
        - No partial writes possible

    See Also:
        - volume_utils.validate_trigger: Validation function
        - get_active_volume_triggers: Retrieve persisted triggers
    """
```

---

## Appendix B: Response Schema Reference

### Success Response (v3.0.0)

```json
{
    "success": true,
    "triggers_saved": 3,
    "created_ids": [142, 143],
    "updated_ids": [87],
    "creator_id": "maya_hill",
    "creator_id_resolved": "abc123-def456-uuid",
    "warnings": [
        "trigger[0]: extreme multiplier 0.55 - verify intentional",
        "direction flip detected (1.20 -> 0.85) for lingerie/HIGH_PERFORMER"
    ],
    "overwrite_warnings": [
        {
            "trigger_id": 87,
            "content_type": "lingerie",
            "trigger_type": "HIGH_PERFORMER",
            "old_multiplier": 1.20,
            "new_multiplier": 0.85,
            "direction_flip": true,
            "delta_percent": -29.2
        }
    ],
    "metadata": {
        "persisted_at": "2026-01-12T14:30:00.000Z",
        "execution_ms": 23.5,
        "triggers_hash": "sha256:a1b2c3d4e5f67890"
    }
}
```

### Error Response - Validation Failed

```json
{
    "success": false,
    "error": "Validation failed",
    "error_code": "VALIDATION_ERROR",
    "validation_errors": [
        "trigger[1]: invalid trigger_type 'INVALID', must be one of ['HIGH_PERFORMER', 'TRENDING_UP', 'EMERGING_WINNER', 'SATURATING', 'AUDIENCE_FATIGUE']"
    ],
    "triggers_rejected": 1,
    "triggers_valid": 1,
    "creator_id": "maya_hill"
}
```

### Error Response - Creator Not Found

```json
{
    "success": false,
    "error": "Creator not found: unknown_creator",
    "error_code": "CREATOR_NOT_FOUND",
    "creator_id": "unknown_creator"
}
```

### Error Response - Database Error

```json
{
    "success": false,
    "error": "Database error: SQLITE_BUSY",
    "error_code": "DATABASE_ERROR",
    "creator_id": "maya_hill"
}
```

---

*End of Refactoring Document*

*Document Version: 1.0.0*
*Created: 2026-01-12*
*Author: Refactoring Specialist*
