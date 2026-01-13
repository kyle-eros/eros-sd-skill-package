# Technical Review: validate_caption_structure

**Tool**: `mcp__eros-db__validate_caption_structure`
**Version**: 1.0.0 (unversioned)
**Location**: `mcp_server/main.py:3503-3586`
**Review Date**: 2026-01-13
**Reviewer**: Claude (mcp-refactor skill)

---

## 1. Executive Summary

`validate_caption_structure` is a caption quality validation tool that checks for anti-patterization issues like spam patterns, excessive emojis, and length violations. However, it is significantly **underdeveloped** compared to other caption tools in the codebase (e.g., `get_batch_captions_by_content_types`, `get_send_type_captions`).

**Key Findings**:
- Tool does not query the database at all - pure Python logic
- Missing `send_type` validation against `send_types` table
- No metadata block (violates MCP best practices)
- No test coverage (0 tests)
- Hardcoded validation rules with no configurability
- Inconsistent with other caption tools' response schema patterns

**Severity**: MEDIUM - Tool works but has significant gaps

---

## 2. Current Implementation Analysis

### 2.1 Code Structure (Lines 3503-3586)

```python
@mcp.tool()
def validate_caption_structure(caption_text: str, send_type: str) -> dict:
    """Validates caption structure against anti-patterization rules."""
    logger.info(f"validate_caption_structure: send_type={send_type}, length={len(caption_text)}")

    issues = []
    score = 100

    # Length validation (lines 3521-3533)
    # Spam pattern detection (lines 3535-3549)
    # Emoji density check (lines 3551-3558)
    # Repetition check (lines 3560-3570)
    # All caps check (lines 3572-3575)

    return {
        "valid": score >= 70,
        "score": score,
        "issues": issues,
        "send_type": send_type,
        "caption_length": len(caption_text),
        "recommendation": "PASS" if score >= 85 else "REVIEW" if score >= 70 else "REJECT"
    }
```

### 2.2 Validation Rules Breakdown

| Rule | Condition | Penalty | Line Range |
|------|-----------|---------|------------|
| Too Short | `len < 10` | -30 | 3521-3522 |
| Very Short | `len < 20` | -10 | 3523-3524 |
| Too Long | `len > 500` | -10 | 3525-3526 |
| Lengthy | `len > 300` | -5 | 3527-3528 |
| Spam: "click here" | Contains | -15 | 3535-3543 |
| Spam: "limited time" | Contains | -10 | 3535-3543 |
| Spam: "act now" | Contains | -15 | 3535-3543 |
| Spam: "don't miss" | Contains | -10 | 3535-3543 |
| Spam: "hurry" | Contains | -5 | 3535-3543 |
| Spam: "exclusive offer" | Contains | -10 | 3535-3543 |
| Spam: "buy now" | Contains | -15 | 3535-3543 |
| Excessive Emojis | `count > 10` | -15 | 3551-3554 |
| High Emoji Count | `count > 5` | -5 | 3555-3558 |
| Repeated Words | Any word > 2 times | -10 | 3560-3570 |
| All Caps | Entire text, `len > 20` | -20 | 3572-3575 |

### 2.3 Score Thresholds

| Score Range | valid | recommendation |
|-------------|-------|----------------|
| 85-100 | true | PASS |
| 70-84 | true | REVIEW |
| 0-69 | false | REJECT |

---

## 3. Issues Identified

### 3.1 Critical Issues

#### 3.1.1 No Database Integration
**Severity**: HIGH
**Location**: Entire function

The tool accepts `send_type` as a parameter but never validates it exists in the `send_types` table. Other MCP tools in this codebase validate creator_id and content types against the database.

**Current Behavior**:
```python
# send_type is echoed back without validation
return {"send_type": send_type, ...}
```

**Risk**: Invalid send_types silently pass through, causing downstream failures.

#### 3.1.2 Missing Metadata Block
**Severity**: HIGH
**Location**: Return statement (line 3579-3586)

MCP best practices (from `docs/mcp_best_practices.md`) require:
- `metadata.fetched_at` - ISO timestamp
- `metadata.tool_version` - Version string
- `metadata.query_ms` - Execution time (even if 0 for non-DB operations)

**Current Response Schema**:
```json
{
  "valid": true,
  "score": 100,
  "issues": [],
  "send_type": "ppv_unlock",
  "caption_length": 49,
  "recommendation": "PASS"
}
```

**Missing Fields**: No `metadata` block at all.

#### 3.1.3 Zero Test Coverage
**Severity**: HIGH
**Location**: `python/tests/`

Grep for "validate_caption" in tests returns no matches. This is the only caption tool without tests:
- `test_mcp_captions.py` - 27 tests for `get_batch_captions_by_content_types`
- `test_send_type_captions.py` - Tests for `get_send_type_captions`
- No tests for `validate_caption_structure`

### 3.2 Moderate Issues

#### 3.2.1 Hardcoded Validation Rules
**Severity**: MEDIUM
**Location**: Lines 3535-3543 (spam patterns)

Spam patterns are hardcoded in the function body. Other tools use `volume_utils.py` for configuration constants.

**Current**:
```python
spam_patterns = [
    ("click here", 15),
    ("limited time", 10),
    ...
]
```

**Better**: Move to `volume_utils.py` as `CAPTION_SPAM_PATTERNS`.

#### 3.2.2 Emoji Detection Algorithm
**Severity**: MEDIUM
**Location**: Line 3552

```python
emoji_count = sum(1 for c in caption_text if ord(c) > 0x1F300)
```

This is a naive implementation that:
1. Misses many emoji ranges (e.g., 0x2600-0x26FF for symbols)
2. Includes non-emoji Unicode characters > 0x1F300
3. Doesn't handle multi-codepoint emojis (e.g., 👨‍👩‍👧‍👦)

#### 3.2.3 send_type Not Used in Validation Logic
**Severity**: MEDIUM
**Location**: Lines 3503-3586

The `send_type` parameter is accepted but never influences validation. Different send types should have different length requirements:
- `bump_text_only`: Shorter captions expected
- `ppv_unlock`: Longer, more descriptive captions beneficial
- `dm_farm`: Very short captions normal

### 3.3 Minor Issues

#### 3.3.1 Inconsistent Error Response Pattern
**Severity**: LOW
**Location**: Entire function

The tool never returns errors - it always returns a valid response even for empty strings.

**Current** (empty string input):
```python
>>> validate_caption_structure("", "ppv_unlock")
{"valid": true, "score": 70, "issues": ["Caption too short (min 10 chars)"]}
```

Other tools return `{"error": "...", "error_code": "..."}` for invalid inputs.

#### 3.3.2 No Input Sanitization
**Severity**: LOW
**Location**: Line 3545

The caption is lowercased for pattern matching but original text is measured for length. This is inconsistent but not broken.

#### 3.3.3 Word Repetition Logic
**Severity**: LOW
**Location**: Lines 3561-3570

Only checks words > 3 characters and only counts if word appears > 2 times. Common words like "the" would be flagged if used 3+ times.

---

## 4. Consumer Analysis

### 4.1 Direct Consumers

| Consumer | Location | Usage |
|----------|----------|-------|
| `ProductionMCPClient.validate_caption_structure` | `python/adapters.py:233-235` | Async wrapper |
| `schedule-generator` skill | `.claude/skills/eros-schedule-generator/SKILL.md` | Caption quality checks |

### 4.2 Consumer Expectations

From `docs/DOMAIN_KNOWLEDGE.md:498`:
> `validate_caption_structure` | Validation | Anti-patterization check

Consumers expect:
1. Validation result (pass/fail)
2. Quality score
3. List of specific issues
4. Recommendation for action

Current implementation meets basic expectations but lacks:
- Confidence indicators
- Send-type-specific validation
- Audit trail metadata

---

## 5. Comparison with Sibling Tools

### 5.1 Response Schema Comparison

| Field | `get_batch_captions` | `get_send_type_captions` | `validate_caption_structure` |
|-------|---------------------|-------------------------|------------------------------|
| `metadata.fetched_at` | ✓ | ✓ | ✗ |
| `metadata.query_ms` | ✓ | ✓ | ✗ |
| `metadata.tool_version` | ✓ | ✓ | ✗ |
| `error_code` on failure | ✓ | ✓ | ✗ |
| Hash for validation | ✓ | ✓ | ✗ |

### 5.2 Input Validation Comparison

| Check | `get_batch_captions` | `get_send_type_captions` | `validate_caption_structure` |
|-------|---------------------|-------------------------|------------------------------|
| Empty input | ✓ | ✓ | ✗ (allows empty) |
| Invalid format | ✓ | ✓ | ✗ |
| DB existence check | ✓ (creator_id) | ✓ (creator_id, send_type) | ✗ |

---

## 6. Database Schema (Not Currently Used)

The tool SHOULD validate against these tables:

### 6.1 send_types Table
```sql
-- Verify send_type exists
SELECT 1 FROM send_types WHERE send_type_key = ? AND is_active = 1
```

### 6.2 caption_bank Table (Optional Enhancement)
```sql
-- Check if caption already exists (anti-duplication)
SELECT caption_id FROM caption_bank WHERE caption_text = ?
```

---

## 7. Recommended Refactoring Phases

### Phase 1: Schema Alignment (Foundation)
- Add metadata block to response
- Add error response pattern for invalid inputs
- Move constants to `volume_utils.py`
- Add tool version (2.0.0)

### Phase 2: Input Validation
- Validate `send_type` against `send_types` table
- Add empty string validation
- Add max length input guard

### Phase 3: Send-Type-Aware Validation
- Different length thresholds per send_type category
- Send-type-specific spam patterns
- Category-based scoring weights

### Phase 4: Enhanced Detection
- Improved emoji detection algorithm
- URL detection
- Phone number detection
- Platform name detection (OnlyFans, OF mentions)

### Phase 5: Test Coverage
- Unit tests for all validation rules
- Integration tests with real send_types
- Edge case coverage
- Target: 27+ tests (matching `test_mcp_captions.py`)

---

## 8. Risk Assessment

| Area | Risk Level | Mitigation |
|------|------------|------------|
| Breaking changes | LOW | Only adding fields, not removing |
| Consumer impact | LOW | Adapters wrapper unchanged |
| Test regression | N/A | No existing tests |
| Performance | LOW | No DB queries added (optional) |

---

## 9. Checklist for Spec Phase

- [ ] Define metadata block fields
- [ ] Define error codes (EMPTY_CAPTION, INVALID_SEND_TYPE)
- [ ] Define send_type validation behavior
- [ ] Define version numbering (2.0.0)
- [ ] Define test coverage requirements
- [ ] Define backward compatibility strategy
- [ ] Interview user for priority of enhancements

---

**REVIEW_DONE**

*Review completed: 2026-01-13*
*Lines analyzed: 83 (3503-3586)*
*Severity: MEDIUM*
*Recommended action: Proceed to spec phase*
