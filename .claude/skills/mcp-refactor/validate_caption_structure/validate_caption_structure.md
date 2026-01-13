# Refactoring Spec: validate_caption_structure v2.0.0

**Tool**: `mcp__eros-db__validate_caption_structure`
**Current Version**: 1.0.0 (unversioned)
**Target Version**: 2.0.0
**Spec Date**: 2026-01-13
**Status**: APPROVED

---

## 1. Summary of Changes

| Change | Before | After |
|--------|--------|-------|
| Database validation | None | Validates send_type against send_types table |
| Category awareness | Uniform rules | Per-category thresholds (revenue/engagement/retention) |
| Error handling | Always returns score | Returns error codes for invalid inputs |
| Metadata block | Missing | Full metadata (fetched_at, tool_version, query_ms) |
| Constants location | Inline | Extracted to volume_utils.py |
| Test coverage | 0 tests | 25+ tests |

---

## 2. Interview Decisions (Binding)

### 2.1 send_type Validation (Q1)
**Decision**: Validate send_type against database WITH session-level caching.

**Implementation**:
- First call loads all 22 send_types into module-level dict
- Subsequent calls use cached lookup (O(1))
- Query: `SELECT send_type_key, category, page_type_restriction FROM send_types WHERE is_active = 1`
- Invalid send_type returns error code `INVALID_SEND_TYPE`

### 2.2 Category-Aware Rules (Q2)
**Decision**: Apply different length thresholds by send_type category.

**Thresholds (to be added to volume_utils.py)**:
```python
CAPTION_LENGTH_THRESHOLDS = {
    "revenue": {"min": 40, "ideal_min": 80, "ideal_max": 300, "max": 450},
    "engagement": {"min": 15, "ideal_min": 30, "ideal_max": 150, "max": 250},
    "retention": {"min": 25, "ideal_min": 50, "ideal_max": 200, "max": 300},
    "default": {"min": 10, "ideal_min": 20, "ideal_max": 300, "max": 500}
}
```

**Spam Tolerance by Category**:
- Revenue: Allow "exclusive", "limited" (selling language expected)
- Engagement: Stricter - organic feel required
- Retention: Strictest - personal, not salesy

### 2.3 Error Codes (Q3)
**Decision**: Add error codes for structural failures, keep scores for quality issues.

**Error Conditions**:
| Error Code | Condition | Message |
|------------|-----------|---------|
| `EMPTY_CAPTION` | `caption_text is None or caption_text.strip() == ""` | "Caption text is required" |
| `INVALID_SEND_TYPE` | send_type not in send_types table | "Invalid send_type: {send_type}" |
| `CAPTION_EXCEEDS_LIMIT` | `len(caption_text) > 2000` | "Caption exceeds 2000 character limit" |

---

## 3. Response Schema v2.0

### 3.1 Success Response
```json
{
    "valid": true,
    "score": 87,
    "issues": ["Caption slightly below ideal length"],
    "send_type": "ppv_unlock",
    "category": "revenue",
    "caption_length": 65,
    "thresholds_applied": {
        "min": 40,
        "ideal_min": 80,
        "ideal_max": 300,
        "max": 450
    },
    "recommendation": "PASS",
    "metadata": {
        "fetched_at": "2026-01-13T15:30:00Z",
        "tool_version": "2.0.0",
        "query_ms": 0.5,
        "cache_hit": true
    }
}
```

### 3.2 Error Response
```json
{
    "error": "Invalid send_type: bad_type",
    "error_code": "INVALID_SEND_TYPE",
    "valid": false,
    "score": null,
    "send_type": "bad_type",
    "category": null,
    "caption_length": null,
    "valid_send_types": ["ppv_unlock", "ppv_wall", "bump_normal", "..."],
    "metadata": {
        "fetched_at": "2026-01-13T15:30:00Z",
        "tool_version": "2.0.0",
        "error": true
    }
}
```

### 3.3 Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `valid` | bool | Yes | Whether caption passes validation (score >= threshold) |
| `score` | int\|null | Yes | Quality score 0-100, null on error |
| `issues` | list[str] | Yes | List of specific issues found |
| `send_type` | str | Yes | Echoed input send_type |
| `category` | str\|null | Yes | Resolved category from send_types table |
| `caption_length` | int\|null | Yes | Character count of input |
| `thresholds_applied` | dict\|null | Yes | Category-specific thresholds used |
| `recommendation` | str | Yes | PASS/REVIEW/REJECT based on score |
| `metadata.fetched_at` | str | Yes | ISO timestamp |
| `metadata.tool_version` | str | Yes | "2.0.0" |
| `metadata.query_ms` | float | Yes | Execution time in ms |
| `metadata.cache_hit` | bool | Yes | Whether send_types cache was used |
| `error` | str | On error | Error message |
| `error_code` | str | On error | Machine-readable error code |
| `valid_send_types` | list[str] | On INVALID_SEND_TYPE | List of valid send_type_keys |

---

## 4. Constants to Add to volume_utils.py

### 4.1 Length Thresholds
```python
# Caption length thresholds by category
CAPTION_LENGTH_THRESHOLDS = {
    "revenue": {"min": 40, "ideal_min": 80, "ideal_max": 300, "max": 450},
    "engagement": {"min": 15, "ideal_min": 30, "ideal_max": 150, "max": 250},
    "retention": {"min": 25, "ideal_min": 50, "ideal_max": 200, "max": 300},
    "default": {"min": 10, "ideal_min": 20, "ideal_max": 300, "max": 500}
}
```

### 4.2 Spam Patterns by Category
```python
# Spam patterns with penalties, filtered by category tolerance
CAPTION_SPAM_PATTERNS = {
    "universal": [  # All categories
        ("click here", 15),
        ("act now", 15),
        ("buy now", 15),
        ("hurry", 5),
    ],
    "non_revenue": [  # Engagement + Retention only
        ("limited time", 10),
        ("exclusive offer", 10),
        ("don't miss", 10),
    ]
}

# Categories that tolerate sales language
SALES_LANGUAGE_TOLERANT = {"revenue"}
```

### 4.3 Score Thresholds
```python
# Score thresholds for recommendations
CAPTION_SCORE_THRESHOLDS = {
    "pass": 85,
    "review": 70,
    "reject": 0
}

# Maximum caption length (input guard)
CAPTION_MAX_INPUT_LENGTH = 2000
```

---

## 5. Execution Phases

### Phase 1: Constants Extraction
**Scope**: Extract constants to volume_utils.py
**Files Modified**: `mcp_server/volume_utils.py`, `mcp_server/main.py`
**Tests**: N/A (no behavior change)
**Commit**: `refactor(volume_utils): add caption validation constants for v2.0`

**Before** (main.py:3535-3543):
```python
spam_patterns = [
    ("click here", 15),
    ("limited time", 10),
    ...
]
```

**After** (main.py imports from volume_utils):
```python
from .volume_utils import (
    CAPTION_LENGTH_THRESHOLDS,
    CAPTION_SPAM_PATTERNS,
    CAPTION_SCORE_THRESHOLDS,
    CAPTION_MAX_INPUT_LENGTH,
    SALES_LANGUAGE_TOLERANT
)
```

**Verification**:
```bash
pytest python/tests/test_volume_utils.py -v
# Expect: existing tests pass, constants importable
```

---

### Phase 2: send_type Cache & Validation
**Scope**: Add send_type validation with cached lookup
**Files Modified**: `mcp_server/main.py`
**Tests**: Add tests before implementing

**Before**: send_type echoed without validation
**After**: send_type validated against cached send_types table

**New Functions**:
```python
# Module-level cache
_SEND_TYPES_CACHE: dict[str, dict] = {}

def _get_send_types_cache() -> dict[str, dict]:
    """Load and cache all send_types. Called once per session."""
    global _SEND_TYPES_CACHE
    if not _SEND_TYPES_CACHE:
        query = """
            SELECT send_type_key, category, page_type_restriction
            FROM send_types WHERE is_active = 1
        """
        rows = db_query(query, ())
        _SEND_TYPES_CACHE = {r["send_type_key"]: r for r in rows}
    return _SEND_TYPES_CACHE

def _validate_send_type(send_type: str) -> tuple[bool, dict | None, str | None]:
    """Validate send_type and return (valid, send_type_row, error_code)."""
    cache = _get_send_types_cache()
    if send_type in cache:
        return (True, cache[send_type], None)
    return (False, None, "INVALID_SEND_TYPE")
```

**Verification**:
```bash
pytest python/tests/test_validate_caption_structure.py::TestSendTypeValidation -v
```

**Commit**: `feat(validate_caption_structure): add send_type cache and validation`

---

### Phase 3: Error Handling & Input Validation
**Scope**: Add error codes for structural failures
**Files Modified**: `mcp_server/main.py`
**Tests**: Add tests first

**Before**: Always returns score
**After**: Returns error for EMPTY_CAPTION, INVALID_SEND_TYPE, CAPTION_EXCEEDS_LIMIT

**Error Response Builder**:
```python
def _error_response(error: str, error_code: str, send_type: str, **kwargs) -> dict:
    """Build standardized error response."""
    return {
        "error": error,
        "error_code": error_code,
        "valid": False,
        "score": None,
        "send_type": send_type,
        "category": None,
        "caption_length": None,
        "issues": [],
        "recommendation": "REJECT",
        "thresholds_applied": None,
        "metadata": {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "tool_version": "2.0.0",
            "error": True
        },
        **kwargs
    }
```

**Verification**:
```bash
pytest python/tests/test_validate_caption_structure.py::TestErrorResponses -v
```

**Commit**: `feat(validate_caption_structure): add error codes for invalid inputs`

---

### Phase 4: Category-Aware Validation Rules
**Scope**: Apply different thresholds by category
**Files Modified**: `mcp_server/main.py`
**Tests**: Add tests first

**Before**: Uniform thresholds for all send_types
**After**: Category-specific thresholds from CAPTION_LENGTH_THRESHOLDS

**Implementation**:
```python
def _get_thresholds(category: str | None) -> dict:
    """Get length thresholds for category."""
    return CAPTION_LENGTH_THRESHOLDS.get(
        category or "default",
        CAPTION_LENGTH_THRESHOLDS["default"]
    )

def _score_length(length: int, thresholds: dict) -> tuple[int, list[str]]:
    """Score caption length against thresholds. Returns (penalty, issues)."""
    issues = []
    penalty = 0

    if length < thresholds["min"]:
        penalty = 30
        issues.append(f"Caption too short (min {thresholds['min']} chars for this category)")
    elif length < thresholds["ideal_min"]:
        penalty = 10
        issues.append(f"Caption below ideal length (recommend {thresholds['ideal_min']}+ chars)")
    elif length > thresholds["max"]:
        penalty = 15
        issues.append(f"Caption too long (max {thresholds['max']} chars)")
    elif length > thresholds["ideal_max"]:
        penalty = 5
        issues.append(f"Caption above ideal length (recommend under {thresholds['ideal_max']} chars)")

    return (penalty, issues)

def _get_spam_patterns(category: str | None) -> list[tuple[str, int]]:
    """Get spam patterns applicable to category."""
    patterns = list(CAPTION_SPAM_PATTERNS["universal"])
    if category not in SALES_LANGUAGE_TOLERANT:
        patterns.extend(CAPTION_SPAM_PATTERNS["non_revenue"])
    return patterns
```

**Verification**:
```bash
pytest python/tests/test_validate_caption_structure.py::TestCategoryRules -v
```

**Commit**: `feat(validate_caption_structure): add category-aware validation rules`

---

### Phase 5: Metadata & Response Schema
**Scope**: Add metadata block, finalize response schema
**Files Modified**: `mcp_server/main.py`
**Tests**: Full test suite run

**Before**: Minimal response without metadata
**After**: Full response schema v2.0

**Success Response Builder**:
```python
def _success_response(
    score: int,
    issues: list[str],
    send_type: str,
    category: str,
    caption_length: int,
    thresholds: dict,
    cache_hit: bool,
    start_time: float
) -> dict:
    """Build standardized success response."""
    return {
        "valid": score >= CAPTION_SCORE_THRESHOLDS["review"],
        "score": score,
        "issues": issues,
        "send_type": send_type,
        "category": category,
        "caption_length": caption_length,
        "thresholds_applied": thresholds,
        "recommendation": (
            "PASS" if score >= CAPTION_SCORE_THRESHOLDS["pass"]
            else "REVIEW" if score >= CAPTION_SCORE_THRESHOLDS["review"]
            else "REJECT"
        ),
        "metadata": {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "tool_version": "2.0.0",
            "query_ms": (time.time() - start_time) * 1000,
            "cache_hit": cache_hit
        }
    }
```

**Verification**:
```bash
pytest python/tests/test_validate_caption_structure.py -v
# Expect: All 25+ tests pass
```

**Commit**: `feat(validate_caption_structure): v2.0.0 with metadata and full schema`

---

## 6. Test Coverage Plan

### 6.1 Test File
`python/tests/test_validate_caption_structure.py`

### 6.2 Test Categories

| Category | Count | Description |
|----------|-------|-------------|
| Input Validation | 5 | Empty, null, too long, invalid send_type, valid inputs |
| Error Responses | 4 | EMPTY_CAPTION, INVALID_SEND_TYPE, CAPTION_EXCEEDS_LIMIT, error schema |
| Send Type Validation | 4 | Cache load, cache hit, all 22 types valid, invalid type |
| Category Rules | 6 | Revenue thresholds, engagement thresholds, retention thresholds, default fallback, spam tolerance by category |
| Scoring | 4 | Length penalties, spam penalties, emoji penalties, repetition penalties |
| Metadata | 3 | All fields present, timing accurate, version correct |
| Integration | 2 | Full valid caption, full invalid caption |

**Total: 28 tests** (exceeds 25+ requirement)

### 6.3 Test Fixtures
```python
@pytest.fixture
def mock_send_types_cache():
    """Mock send_types cache with standard types."""
    return {
        "ppv_unlock": {"send_type_key": "ppv_unlock", "category": "revenue"},
        "bump_normal": {"send_type_key": "bump_normal", "category": "engagement"},
        "renew_on_post": {"send_type_key": "renew_on_post", "category": "retention"},
    }
```

---

## 7. Backward Compatibility

### 7.1 Preserved Behavior
- Score calculation logic unchanged for valid inputs
- `valid` field semantics unchanged (score >= 70)
- `recommendation` values unchanged (PASS/REVIEW/REJECT)
- `issues` array format unchanged

### 7.2 New Fields (Additive)
- `category` - New field, null-safe
- `thresholds_applied` - New field, null-safe
- `metadata.*` - New block, always present
- `error_code` - Only on errors

### 7.3 Breaking Changes
- Empty string now returns error instead of score
- Invalid send_type now returns error instead of echo

**Consumer Impact**: `python/adapters.py:233-235` unchanged - async wrapper passes through.

---

## 8. Rollback Plan

If issues discovered:
```bash
git revert HEAD~5..HEAD  # Revert all 5 phase commits
# OR
git reset --hard $BASELINE  # Full rollback to pre-refactor
```

---

## 9. Checklist

- [x] Interview completed (Q1-Q3 answered)
- [x] Response schema defined
- [x] Error codes defined
- [x] Constants specified
- [x] Phases defined with before/after
- [x] Test coverage planned (28 tests)
- [x] Backward compatibility analyzed
- [x] Rollback plan defined

---

**SPEC_DONE**

*Spec completed: 2026-01-13*
*Phases: 5*
*Estimated tests: 28*
*Estimated LOC changed: ~200*
