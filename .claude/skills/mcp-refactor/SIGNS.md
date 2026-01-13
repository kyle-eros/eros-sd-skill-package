# MCP Refactor Signs Library

## What are Signs?

Signs are explicit guardrails added to prompts to prevent common failure patterns. Named after the Ralph Wiggum philosophy: "When Ralph falls off the slide, add a sign saying 'SLIDE DOWN, DON'T JUMP.'"

**Key Principle:** Rather than prescribing everything upfront, observe where the loop fails and add signs to prevent those failures in future iterations.

---

## Phase 1 Signs: Review Generation

### R1: Don't Guess Line Numbers

**Failure Pattern:** Claude estimates line numbers instead of verifying.

**Sign Text:**
```
SIGN-R1: Line numbers MUST be verified.
WRONG: "The function is around line 500"
RIGHT: Read mcp_server/main.py, search for @mcp.tool decorator with tool name, record EXACT line numbers from Read output.
```

**Why It Matters:** Stale line numbers cascade through spec and execution phases.

---

### R2: Verify Every Column

**Failure Pattern:** Claude assumes SQL columns exist without checking schema.

**Sign Text:**
```
SIGN-R2: Every SQL column requires schema verification.
WRONG: "The query uses the standard columns"
RIGHT: For EACH column in SQL query, run:
  PRAGMA table_info([table_name]);
  Confirm column exists in output.
  Document in Column Verification table.
```

**Why It Matters:** Schema mismatches cause runtime errors.

---

### R3: Don't Inflate Severity

**Failure Pattern:** Claude marks everything as HIGH/CRITICAL for emphasis.

**Sign Text:**
```
SIGN-R3: Apply severity definitions STRICTLY.
CRITICAL: Blocks pipeline execution OR causes data corruption OR returns wrong data
HIGH: Performance degradation (>2x slower) OR missing validation that could cause bad data
MEDIUM: Missing features OR inconsistent patterns OR non-standard conventions
LOW: Code quality OR documentation gaps OR minor readability issues

If unsure, use LOWER severity. Over-severity causes priority confusion.
```

**Why It Matters:** Inflated severity wastes time on non-critical issues.

---

### R4: Check Error Handling

**Failure Pattern:** Claude assumes error handling is fine without inspection.

**Sign Text:**
```
SIGN-R4: Error handling requires explicit audit.
WRONG: "Error handling appears standard"
RIGHT:
1. Find all return statements with "error" in tool code
2. Extract exact error format:
   - Is it string only? {"error": "message"}
   - Or structured? {"error_code": "X", "error_message": "Y", "context": {}}
3. Compare to mcp_best_practices.md Section 2
4. Document compliance status
```

**Why It Matters:** Inconsistent error formats break downstream consumers.

---

### R5: Don't Skip Consumer Analysis

**Failure Pattern:** Claude assumes tool is standalone or used "somewhere."

**Sign Text:**
```
SIGN-R5: Consumer analysis MUST use explicit searches.
WRONG: "This tool is probably used by the pipeline"
RIGHT: Execute parallel searches:
  Grep: "mcp__eros-db__[tool_name]" in python/
  Grep: "mcp__eros-db__[tool_name]" in skills/
  Grep: "[tool_name]" in python/tests/

List ALL usages with file:line references.
```

**Why It Matters:** Breaking changes affect unknown consumers.

---

### R6: Progressive Context Loading

**Failure Pattern:** Claude loads all context files upfront, wasting tokens.

**Sign Text:**
```
SIGN-R6: Use 3-level progressive disclosure.
Level 1 (ALWAYS): CLAUDE.md, LEARNINGS.md lines 1-50
Level 2 (BY ISSUE): Load specific docs when issue type identified
Level 3 (ON DEMAND): Load prior reviews/specs only when pattern match needed

NEVER load Level 3 until Level 1 and Level 2 consumed.
```

**Why It Matters:** Token budget is finite (~4000/phase).

---

### R7: Parallel Tool Calls

**Failure Pattern:** Claude runs independent searches sequentially.

**Sign Text:**
```
SIGN-R7: Independent searches run in PARALLEL.
WRONG:
  Grep for decorator → wait → Grep for usages → wait → Grep for tests

RIGHT: Single message with multiple Grep calls:
  Grep: "@mcp.tool.*[tool_name]" in mcp_server/
  Grep: "mcp__eros-db__[tool_name]" in python/
  Grep: "[tool_name]" in python/tests/

Results combined in one response.
```

**Why It Matters:** Sequential searches waste iteration time.

---

## Phase 2 Signs: Spec Generation

### S1: Don't Re-Read review.md

**Failure Pattern:** Claude reads review.md multiple times per iteration.

**Sign Text:**
```
SIGN-S1: Build DISTILLED_CONTEXT once.
WRONG: Read review.md → extract data → read again for another section → extract

RIGHT:
1. Read review.md ONCE at iteration start
2. Build DISTILLED_CONTEXT object with all needed data
3. Reference DISTILLED_CONTEXT throughout iteration
4. NEVER call Read on review.md again

Saves ~2000 tokens per avoided re-read.
```

**Why It Matters:** Re-reading wastes significant token budget.

---

### S2: Verify Line Numbers

**Failure Pattern:** Claude copies line numbers from review.md without checking.

**Sign Text:**
```
SIGN-S2: Line numbers from review.md may be STALE.
WRONG: Copy "lines 145-200" from review.md into spec

RIGHT:
1. Read actual file: mcp_server/main.py
2. Grep for function/pattern
3. Confirm current line numbers
4. If different, use CURRENT numbers
5. Note discrepancy: "Review said 145-200, actual is 152-207"
```

**Why It Matters:** Phase 3 execution uses these line numbers.

---

### S3: No Vague Instructions

**Failure Pattern:** Claude uses soft language that doesn't specify exact changes.

**Sign Text:**
```
SIGN-S3: Every change instruction MUST be executable.
WRONG: "Update error handling as appropriate"
WRONG: "Add validation if needed"
WRONG: "Refactor for clarity"

RIGHT: "Change line 147 from:
  return {'error': msg}
to:
  return {'error_code': 'INVALID_PARAM', 'error_message': msg}"

Test: Could a junior dev make this change with NO additional context?
```

**Why It Matters:** Vague specs cause Phase 3 loops to diverge.

---

### S4: Every Phase Needs Verification

**Failure Pattern:** Claude skips verification commands or uses generic "test the code."

**Sign Text:**
```
SIGN-S4: Each phase requires SPECIFIC verification.
WRONG: "Test the changes"
WRONG: "Run tests"

RIGHT: "Run: pytest python/tests/test_mcp_tools.py::test_[tool_name]_[scenario] -v"

Include:
- Exact test file
- Exact test class/function if applicable
- -v flag for verbose output
```

**Why It Matters:** Generic verification doesn't catch specific regressions.

---

### S5: Commit Messages in Spec

**Failure Pattern:** Claude leaves commit message vague or generic.

**Sign Text:**
```
SIGN-S5: Commit messages are EXACT, not templates.
WRONG: "Commit your changes with appropriate message"
WRONG: "Commit: fix things"

RIGHT: "Commit:
```
fix(get_creator_profile): add structured error responses

- Replace string error returns with ErrorResponse TypedDict
- Add error_code, error_message, context fields
- Maintain backwards compatibility via error alias
```
"

Conventional commit format: type(scope): description
```

**Why It Matters:** Phase 3 uses exact commit messages from spec.

---

### S6: Context Fork for Large Output

**Failure Pattern:** Claude writes large spec in main context, causing bloat.

**Sign Text:**
```
SIGN-S6: Large outputs use context:fork.
ESTIMATE tokens before writing:
- DISTILLED_CONTEXT: ~300 tokens
- Spec template: ~2000 tokens
- Code blocks: varies

IF estimated > 2500 tokens:
  USE context:fork
  WRITE incrementally:
    1. Sections 1-3 → save
    2. Sections 4-5 → save
    3. Sections 6-9 → save → rename to final

IF estimated <= 2500:
  WRITE in main context
```

**Why It Matters:** Main context bloat degrades subsequent responses.

---

## Phase 3 Signs: Execution

### E1: Verify Before Modifying

**Failure Pattern:** Claude modifies files based on spec without checking current state.

**Sign Text:**
```
SIGN-E1: ALWAYS Read before Edit.
WRONG: Edit file based on spec line numbers directly

RIGHT:
1. Read target file
2. Grep for specific code pattern from spec's "Before" block
3. Confirm line numbers match
4. If stale, find correct lines
5. THEN apply Edit

Log if line numbers differ: "Spec: line 147, Actual: line 152"
```

**Why It Matters:** Files may have changed since spec was written.

---

### E2: Distinguish Test Failure Types

**Failure Pattern:** Claude updates all failing tests automatically.

**Sign Text:**
```
SIGN-E2: Test failures have TWO causes.
IF test fails:
  Analyze the assertion:

  A) Testing OLD behavior (spec is changing this behavior)
     → Update test to check NEW expected behavior
     → Include test update in same commit

  B) Testing behavior that should STILL work (regression)
     → DO NOT update test
     → Rollback code changes: git checkout -- [files]
     → Report: "REGRESSION in test_[name]: [what broke]"
     → STOP loop, do not continue

KEY: Read the test. What is it checking? Is that supposed to change?
```

**Why It Matters:** Blindly updating tests masks real regressions.

---

### E3: Atomic Commits Only

**Failure Pattern:** Claude batches multiple phases into one commit.

**Sign Text:**
```
SIGN-E3: One phase = one commit.
WRONG: Complete all phases → single commit "refactored tool"

RIGHT:
  Phase 1 changes → commit 1 → verify tests
  Phase 2 changes → commit 2 → verify tests
  Phase 3 changes → commit 3 → verify tests

Each commit message from spec.
Tests must pass between each commit.
```

**Why It Matters:** Atomic commits enable granular rollback.

---

### E4: Report Stale Line Numbers

**Failure Pattern:** Claude silently adjusts line numbers without audit trail.

**Sign Text:**
```
SIGN-E4: Line number discrepancies are LOGGED.
WRONG: Spec says line 147 but it's actually 152 → just use 152

RIGHT: Use correct line, AND log:
"DISCREPANCY: Spec line 147 → Actual line 152
 Pattern: 'def get_creator_profile'
 Reason: [if known, e.g., 'new imports added']"

Add to execution_log.md under Issues Encountered.
```

**Why It Matters:** Audit trail helps diagnose spec drift.

---

### E5: Never Commit Failing Tests

**Failure Pattern:** Claude commits despite test failures "to preserve progress."

**Sign Text:**
```
SIGN-E5: Test failures BLOCK commit.
IF pytest returns non-zero:
  DO NOT run: git commit
  DO NOT output: <promise>PHASE_N_DONE</promise>

INSTEAD:
  1. Analyze failure (E2: old behavior vs regression)
  2. If old behavior: fix test, re-run
  3. If regression: rollback, report, STOP
  4. Only after ALL tests pass: commit

NEVER: "I'll commit now and fix tests in next phase"
```

**Why It Matters:** Broken commits pollute git history.

---

### E6: Respect Phase Dependencies

**Failure Pattern:** Claude runs dependent phases in parallel.

**Sign Text:**
```
SIGN-E6: Check dependency table before parallel execution.
For each phase pair (N, N+1):
  Q: Does Phase N+1 depend on Phase N output?

  IF YES (e.g., Phase 2 uses types defined in Phase 1):
    Execute SEQUENTIALLY
    Wait for Phase N verification gate
    Then start Phase N+1

  IF NO (e.g., Phase 2 and 3 modify different files):
    Can execute in PARALLEL
    (Use separate git worktrees if needed)
```

**Why It Matters:** Parallel dependent phases cause conflicts.

---

### E7: Verify Helper Function Schemas Before Writing Tests

**Failure Pattern:** Claude writes test fixtures without checking what helper functions expect.

**Sign Text:**
```
SIGN-E7: Test fixtures MUST match helper function signatures.
WRONG: Write test_send_type_captions.py with creators table having only (creator_id, display_name, is_active)

RIGHT:
1. Grep for helper functions used by tool: validate_creator_id, resolve_creator_id
2. Read each helper to find expected columns
3. Include ALL expected columns in test fixtures
4. Example: resolve_creator_id expects page_name column

Test fixtures are schemas - they must be complete.
```

**Why It Matters:** Incomplete fixtures cause false test failures that waste iterations.

---

### E8: Consolidate Tightly-Coupled Phases

**Failure Pattern:** Claude executes phases separately when they modify the same function and are interdependent.

**Sign Text:**
```
SIGN-E8: Tightly-coupled phases CAN be consolidated.
IF multiple phases:
- Modify the same function
- Cannot be tested independently
- Have circular dependencies (Phase 2 needs Phase 1's types, but Phase 1 needs Phase 2's return)

THEN:
- Combine into single implementation
- Single commit with comprehensive message
- Document consolidation in execution_log.md: "Phases 1-4 consolidated: interdependent changes to get_send_type_captions"

This is ALLOWED exception to E3 (atomic commits).
```

**Why It Matters:** Forcing artificial phase separation creates broken intermediate states.

---

## Adding New Signs

When the loop fails repeatedly on a new pattern:

1. **Identify the failure:** What went wrong? What was expected?
2. **Write the sign:** Clear WRONG/RIGHT examples
3. **Add to appropriate phase:** R (review), S (spec), E (execute)
4. **Include in loop prompt:** Reference sign by ID

### Template

```markdown
### [X][N]: [Title]

**Failure Pattern:** [What Claude does wrong]

**Sign Text:**
```
SIGN-[X][N]: [One-line rule]
WRONG: [Bad behavior]
RIGHT: [Good behavior]

[Additional guidance if needed]
```

**Why It Matters:** [Impact of failure]
```

---

## Quick Reference

| Sign | Phase | Rule |
|------|-------|------|
| R1 | Review | Verify line numbers via Read |
| R2 | Review | PRAGMA table_info() for all columns |
| R3 | Review | Apply severity definitions strictly |
| R4 | Review | Audit error handling explicitly |
| R5 | Review | Grep all consumers |
| R6 | Review | 3-level progressive disclosure |
| R7 | Review | Parallel independent searches |
| S1 | Spec | Build DISTILLED_CONTEXT once |
| S2 | Spec | Verify line numbers before spec |
| S3 | Spec | No vague instructions |
| S4 | Spec | Specific verification commands |
| S5 | Spec | Exact commit messages |
| S6 | Spec | context:fork if >2500 tokens |
| E1 | Execute | Read before Edit |
| E2 | Execute | Old behavior vs regression |
| E3 | Execute | One phase = one commit |
| E4 | Execute | Log line number discrepancies |
| E5 | Execute | Never commit failing tests |
| E6 | Execute | Respect phase dependencies |
| E7 | Execute | Verify helper function schemas before tests |
| E8 | Execute | Consolidate tightly-coupled phases |
