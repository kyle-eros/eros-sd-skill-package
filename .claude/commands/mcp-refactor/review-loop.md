# Phase 1: Review Loop Prompt

Use this prompt with `/ralph-loop` to generate a technical review.

## CRITICAL: Search Location

**Search ONLY in the current working directory (`$PWD`).**
- MCP server: `./mcp_server/main.py`
- Do NOT search in `~/Developer/EROS-SD-MAIN-PROJECT/` or other external projects
- If tool not found in `./mcp_server/main.py`, STOP and ask user

## Template

```bash
/ralph-loop "Generate technical review for $TOOL_NAME.

## Task
Read and analyze ./mcp_server/main.py (in CURRENT WORKING DIRECTORY) to find $TOOL_NAME implementation.
Do NOT search in other projects like EROS-SD-MAIN-PROJECT.
Generate ./mcp_refactoring_workspace/$TOOL_NAME/review.md following the review template.

## Success Criteria (ALL must pass)
- [ ] Tool location verified (file:line confirmed via Read)
- [ ] All SQL columns cross-referenced against PRAGMA table_info()
- [ ] Return schema documented with field naming audit
- [ ] Error handling pattern identified and compared to best practices
- [ ] All issues have correct severity per definitions
- [ ] No [TBD] or placeholder text in output
- [ ] Pipeline position identified (Preflight/Generator/Validator/Utility)
- [ ] Consumer impact analysis complete (Grep across python/ and skills/)
- [ ] review.md written to ./mcp_refactoring_workspace/$TOOL_NAME/review.md

## Context Loading (Progressive Disclosure)
Level 1 (always): CLAUDE.md, LEARNINGS.md (lines 1-50)
Level 2 (by issue type):
  - Return schema questions → mcp_best_practices.md Section 6
  - Error handling patterns → mcp_best_practices.md Section 2
  - Pipeline integration → docs/DOMAIN_KNOWLEDGE.md
Level 3 (on demand): Prior review.md files, completed refactor specs

## Backpressure
After writing review.md, verify:
1. No [TBD] or [TODO] in content
2. All sections present: Quick Reference, Current Implementation, Database Layer, Pipeline Position, Issues, Refactoring Plan, Interview Questions
3. Line numbers filled in (not placeholders)
4. Schema columns verified against PRAGMA output

## Signs to Follow
- R1: Don't guess line numbers - Read file, search for decorator, record exact
- R2: PRAGMA table_info() for EACH column in SQL queries
- R3: Apply severity definitions strictly (CRITICAL=blocks/corruption, HIGH=perf, MEDIUM=missing features, LOW=quality)
- R4: Extract actual error return pattern, compare to mcp_best_practices.md Section 2
- R5: Run Grep for tool name across python/ and skills/, list ALL usages
- R6: Use 3-level progressive disclosure, don't load all context upfront
- R7: Parallel tool calls for independent searches

## Pattern Discovery

When analyzing a tool, ALWAYS check for similar tools that were recently refactored:
1. Grep for tools with similar names (get_batch_*, get_*_captions)
2. Read their implementations for patterns to match
3. Reference in review.md Section 5: "Pattern Alignment"

**Example:** get_send_type_captions should match get_batch_captions_by_content_types v2.0 patterns:
- Four-layer validation
- Per-creator freshness via caption_creator_performance JOIN
- pool_stats CTE
- Metadata block with tool_version

## Output
When ALL criteria pass, output: <promise>REVIEW_DONE</promise>

## If Blocked
- Schema mismatch: Document in issues as CRITICAL, continue
- Line numbers stale: Use Grep to find correct location, update
- Missing context: Load from progressive disclosure levels as needed" \
--max-iterations 25 \
--completion-promise "REVIEW_DONE"
```

## Review.md Template

The output should follow this structure:

```markdown
# [TOOL_NAME] - Technical Review

**Generated:** [DATE] | **Reviewer:** code-reviewer | **Status:** Interview Ready

---

## Quick Reference

| Attribute | Value |
|-----------|-------|
| File | mcp_server/main.py |
| Lines | [START]-[END] |
| Phase | [Preflight/Generator/Validator/Utility] |
| Data Sources | [tables/views] |
| Issues | [emoji] N | [emoji] N | [emoji] N | [emoji] N |

---

## 1. Current Implementation

### 1.1 Signature
[function signature with types]

### 1.2 Parameters
| Param | Type | Required | Default | Used? |
|-------|------|----------|---------|-------|

### 1.3 Return Schema
[documented structure]

### 1.4 Source Code
[complete function]

---

## 2. Database Layer

### 2.1 Schema
[verified columns from PRAGMA]

### 2.2 Queries
[exact SQL]

### 2.3 Column Verification
| SQL Column | Schema Column | Match |
|------------|---------------|-------|

---

## 3. Pipeline Position

### 3.1 Flow
[upstream -> THIS -> downstream]

### 3.2 Dependencies
[tables/tools]

### 3.3 Test Coverage
[existing tests or gaps]

---

## 4. Issues

### CRITICAL
[issues or "None"]

### HIGH
[issues]

### MEDIUM
[issues]

### LOW
[issues]

---

## 5. Refactoring Plan

### 5.1 Priority Order
1. [CRITICAL first]
2. [HIGH second]

### 5.2 Pattern Alignment
| Pattern | Source | Apply? |
|---------|--------|--------|

### 5.3 Complexity
| Aspect | Value |
|--------|-------|
| Files to modify | N |
| Breaking changes | Yes/No |
| Tests needed | N |

---

## 6. Interview Questions

### Decisions Required
1. [architectural choice]
2. [ambiguous behavior]

### Assumptions to Verify
1. [assumption]
2. [integration assumption]
```
