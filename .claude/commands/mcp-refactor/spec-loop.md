# Phase 2: Spec Generation Loop Prompt

Use this prompt with `/ralph-loop` after completing the interview.

## CRITICAL: File Locations

**All files are in the CURRENT WORKING DIRECTORY (`$PWD`).**
- MCP server: `./mcp_server/main.py`
- Review input: `./mcp_refactoring_workspace/$TOOL_NAME/review.md`
- Spec output: `./mcp_refactoring_workspace/$TOOL_NAME/$TOOL_NAME.md`
- Do NOT reference `~/Developer/EROS-SD-MAIN-PROJECT/` or other external projects

## Pre-requisites

1. Phase 1 review.md complete
2. Interview conducted (Section 6 questions answered)
3. DISTILLED_CONTEXT prepared from interview responses

## DISTILLED_CONTEXT Template

Build this ONCE from review.md + interview:

```python
DISTILLED_CONTEXT = {
    "tool_identity": {
        "name": "$TOOL_NAME",
        "file": "mcp_server/main.py",
        "lines": "[START]-[END]",
        "phase": "[Preflight/Generator/Validator]"
    },
    "issues_to_fix": [
        {"id": "BUG-01", "severity": "CRITICAL", "fix": "[from interview]"},
        {"id": "BUG-02", "severity": "HIGH", "fix": "[from interview]"}
    ],
    "enhancements": [
        {"id": "ENH-01", "include": True, "description": "..."},
        {"id": "ENH-02", "include": False, "defer_reason": "..."}
    ],
    "decisions": {
        "question_1": {"choice": "...", "rationale": "..."},
        "question_2": {"choice": "...", "rationale": "..."}
    },
    "constraints": {
        "hard": ["All CRITICAL and HIGH issues"],
        "in_scope": ["User-approved MEDIUM items"],
        "out_of_scope": ["Deferred items"]
    }
}
```

## Interview Answer Integration

When user provides detailed answers (not just option selection), PRESERVE the full context:

```python
# Example: User selected "YES - Add freshness" with detailed rationale
DISTILLED_CONTEXT["decisions"]["freshness"] = {
    "choice": "YES",
    "rationale": "Consistency with get_batch_captions_by_content_types v2.0",
    "implementation_details": {
        "join_table": "caption_creator_performance",
        "ordering": "ccp.last_used_date ASC NULLS FIRST, performance_tier ASC",
        "fields_to_add": ["creator_last_used_at", "creator_use_count", "days_since_creator_used", "effectively_fresh"],
        "threshold_days": 90
    }
}
```

User answers contain IMPLEMENTATION DETAILS - don't just record the choice, record the HOW.

## Loop Template

```bash
/ralph-loop "Generate refactoring specification for $TOOL_NAME.

## Context
- Review: ./mcp_refactoring_workspace/$TOOL_NAME/review.md
- Interview decisions: $DISTILLED_CONTEXT

## Task
Generate ./mcp_refactoring_workspace/$TOOL_NAME/$TOOL_NAME.md specification.

## Success Criteria (ALL must pass)
- [ ] All CRITICAL issues have implementation phases
- [ ] All HIGH issues have implementation phases
- [ ] Each phase has before/after code blocks
- [ ] Each phase has verification command
- [ ] Each phase has exact commit message
- [ ] No [TBD] or 'as needed' or 'if appropriate' phrases
- [ ] Line numbers verified via Read (not copied from review.md blindly)
- [ ] Breaking changes have migration path documented
- [ ] Test plan includes all modified behavior
- [ ] Code blocks are syntactically valid Python

## Token Management
Estimate output tokens before writing.
If spec will exceed 2500 tokens:
- Use context: fork
- Write sections incrementally (1-3, then 4-5, then 6-9)
- Save after each major section

## Backpressure
After writing spec, verify:
1. All phases have: Before block, After block, Verification command, Commit message
2. No vague phrases: 'as needed', 'if appropriate', 'when necessary', '[TBD]'
3. All code blocks compile (valid Python syntax)
4. All file references exist

## Signs to Follow
- S1: Don't re-read review.md - use DISTILLED_CONTEXT only
- S2: Verify line numbers via Read before writing spec
- S3: Specific changes only - line N, exact change, no vague instructions
- S4: Every phase needs verification command (pytest, specific test file)
- S5: Exact commit messages in spec (conventional commit format)
- S6: Use context:fork if output >2500 tokens

## Output
When ALL criteria pass, output: <promise>SPEC_DONE</promise>

## If Blocked
- Line numbers don't match: Grep for pattern, find correct, proceed
- Unclear decision: Reference DISTILLED_CONTEXT.decisions
- Scope question: Reference DISTILLED_CONTEXT.constraints" \
--max-iterations 15 \
--completion-promise "SPEC_DONE"
```

## Spec Template

The output should follow this structure:

```markdown
# [TOOL_NAME] Refactoring Specification

**Version:** 1.0.0 | **Date:** [DATE] | **Status:** Ready for Execution

---

## Quick Reference

| Attribute | Value |
|-----------|-------|
| Tool | `mcp__eros-db__[tool_name]` |
| File | `mcp_server/main.py` lines [X-Y] |
| Issues Resolved | CRITICAL N, HIGH N, MEDIUM N |
| Breaking Changes | Yes/No |

---

## 1. Objectives

**This refactor will:**
- [ ] Fix [BUG-01]: [one-liner]
- [ ] Fix [BUG-02]: [one-liner]
- [ ] Add [ENH-01]: [one-liner]

**Success Criteria:**
- All tests pass
- No regressions in downstream consumers

---

## 2. Current Implementation

```python
# mcp_server/main.py lines [X-Y]
[code from review.md - verify line numbers current]
```

**Issues:**
1. Line [N]: [issue description]
2. Line [M]: [issue description]

---

## 3. Target Implementation

### 3.1 Design Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| [from interview] | [choice] | [why] |

### 3.2 New Interface
```python
def [tool_name](params) -> dict:
    """[docstring]"""
```

### 3.3 Return Schema Changes
```python
# Before
{"field": "type"}

# After
{"field": "type", "new_field": "type"}
```

---

## 4. Implementation Phases

### Phase 1: [Title]

**Objective:** [one sentence]

**Changes:**
| File | Line | Change |
|------|------|--------|
| mcp_server/main.py | [N] | [change description] |

**Before:**
```python
[exact code to replace]
```

**After:**
```python
[exact replacement code]
```

**Verification:**
```bash
pytest python/tests/test_[relevant].py -v
```

**Commit:**
```
fix([tool_name]): [description]
```

---

### Phase 2: [Title]
[same structure as Phase 1]

---

## 5. Database Changes

```sql
-- Migration (if any)
ALTER TABLE ...

-- Rollback
ALTER TABLE ... DROP ...
```

---

## 6. Testing

### 6.1 New Tests
| Test | File | Purpose |
|------|------|---------|

### 6.2 Implementation
```python
class Test[ToolName]:
    def test_[scenario](self):
        result = [tool_name](params)
        assert result["field"] == expected
```

---

## 7. Documentation Updates

| File | Update |
|------|--------|
| mcp_server/main.py | Docstring |

---

## 8. Pre-Merge Checklist

- [ ] All tests pass
- [ ] No type errors
- [ ] Downstream verified
- [ ] Docs updated

---

## 9. Rollback Plan

1. `git revert [commits]`
2. [Database rollback if needed]
```
