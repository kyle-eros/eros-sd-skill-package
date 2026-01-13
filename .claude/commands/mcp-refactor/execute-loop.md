# Phase 3: Execution Loop Prompts

Use these prompts with `/ralph-loop` to execute each implementation phase.

## CRITICAL: File Locations

**All files are in the CURRENT WORKING DIRECTORY (`$PWD`).**
- MCP server: `./mcp_server/main.py`
- Spec file: `./mcp_refactoring_workspace/$TOOL_NAME/$TOOL_NAME.md`
- Execution log: `./mcp_refactoring_workspace/$TOOL_NAME/execution_log.md`
- Do NOT reference `~/Developer/EROS-SD-MAIN-PROJECT/` or other external projects

## Pre-requisites

1. Phase 1 review.md complete
2. Phase 2 [tool_name].md spec complete
3. Clean git working tree
4. Baseline commit recorded

## Pre-Flight Verification

Before starting any execution loop:

```bash
# Verify clean state
git status  # Must show clean tree

# Check Python command availability
PYTHON_CMD=$(command -v python3 || command -v python)
echo "Python: $PYTHON_CMD"

# Syntax check before tests
$PYTHON_CMD -m py_compile mcp_server/main.py && echo "Syntax OK"

# Record baseline
BASELINE_COMMIT=$(git rev-parse --short HEAD)
BASELINE_TESTS=$(pytest python/tests/ -q 2>&1 | tail -1)

echo "Baseline: $BASELINE_COMMIT"
echo "Tests: $BASELINE_TESTS"
```

## Master Orchestration Script

```bash
#!/bin/bash
# execute_phases.sh - Run all implementation phases

TOOL_NAME="$1"
SPEC_FILE="./mcp_refactoring_workspace/${TOOL_NAME}/${TOOL_NAME}.md"
BASELINE_COMMIT=$(git rev-parse --short HEAD)

# Extract phase count
PHASE_COUNT=$(grep -c "### Phase [0-9]" "$SPEC_FILE")

echo "=== EXECUTING $PHASE_COUNT PHASES FOR $TOOL_NAME ==="
echo "Baseline: $BASELINE_COMMIT"

for ((i=1; i<=PHASE_COUNT; i++)); do
    echo "=== PHASE $i/$PHASE_COUNT ==="

    # Run phase loop (template below)
    /ralph-loop "[PHASE_$i_PROMPT]" \
        --max-iterations 10 \
        --completion-promise "PHASE_${i}_DONE"

    # Check for blocking
    if [ $? -ne 0 ]; then
        echo "=== PHASE $i BLOCKED ==="
        exit 1
    fi
done

echo "=== ALL PHASES COMPLETE ==="
git log --oneline "$BASELINE_COMMIT"..HEAD
```

## Individual Phase Loop Template

```bash
/ralph-loop "Execute $TOOL_NAME Phase $N: $TITLE

## Spec Reference
File: ./mcp_refactoring_workspace/$TOOL_NAME/$TOOL_NAME.md
Section: 4. Implementation Phases -> Phase $N

## Pre-Read Verification (REQUIRED)
Before making ANY changes:
1. Read the spec file
2. Quote the EXACT Phase $N section
3. Read the target file(s)
4. Verify line numbers match spec (or find correct)

Quote format:
'''
File: ./mcp_refactoring_workspace/$TOOL_NAME/$TOOL_NAME.md
Section: Phase $N
Lines: [X-Y]

[PASTE EXACT CONTENT HERE]
'''

Verified: Content matches file: YES/NO
If NO: Find correct content, update references

## Execution Steps
1. Read each file to modify
2. Verify line numbers (Grep if stale)
3. Apply EXACT changes per before/after blocks
4. Run verification command from spec
5. If tests pass: git add . && git commit -m '[message from spec]'
6. Verify: git status (must be clean)

## Success Criteria (ALL must pass)
- [ ] All changes from spec applied exactly
- [ ] pytest python/tests/ -q passes
- [ ] Commit created with EXACT message from spec
- [ ] Working tree clean (git status shows nothing)

## Error Handling
- Line numbers stale: Grep for pattern, find correct, log discrepancy, proceed
- Tests fail (checking OLD behavior): Update test per spec, re-run, commit both
- Tests fail (REGRESSION): DO NOT COMMIT, rollback changes, report, STOP
- Spec unclear: STOP, output what's unclear, wait for clarification

## Signs to Follow
- E1: Verify file contents before modifying (Read first)
- E2: Distinguish old behavior test vs regression (if test checks old, update; if new behavior fails, stop)
- E3: One phase = one atomic commit
- E4: Log stale line numbers: 'Spec said line X, actual was line Y'
- E5: NEVER commit if tests fail with regression
- E6: Check phase dependencies before parallel execution

## Output
When phase complete and committed: <promise>PHASE_${N}_DONE</promise>
If blocked: <promise>PHASE_${N}_BLOCKED:[reason]</promise>" \
--max-iterations 10 \
--completion-promise "PHASE_${N}_DONE"
```

## Verification Gate Script

```python
#!/usr/bin/env python3
# verify_phase.py - Phase verification

import subprocess
import sys

def verify_phase(tool_name: str, phase_num: int) -> tuple[bool, list[str]]:
    errors = []

    # Gate 1: Tests pass
    result = subprocess.run(
        ["pytest", "python/tests/", "-q"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        errors.append(f"FAIL: Tests failed\n{result.stdout[-500:]}")

    # Gate 2: Working tree clean
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True
    )
    if status.stdout.strip():
        errors.append(f"FAIL: Uncommitted changes:\n{status.stdout}")

    # Gate 3: Recent commit exists
    log = subprocess.run(
        ["git", "log", "-1", "--oneline"],
        capture_output=True, text=True
    )
    if not log.stdout.strip():
        errors.append("FAIL: No recent commit found")

    return len(errors) == 0, errors

if __name__ == "__main__":
    tool_name = sys.argv[1]
    phase_num = int(sys.argv[2])
    passed, errors = verify_phase(tool_name, phase_num)

    if passed:
        print(f"PHASE {phase_num} VERIFIED")
        sys.exit(0)
    else:
        print(f"PHASE {phase_num} FAILED:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
```

## Error Recovery Commands

```bash
# Cancel stuck loop
/cancel-ralph

# Rollback single phase
git revert HEAD --no-edit
pytest python/tests/ -q  # Verify rollback

# Rollback multiple phases
git log --oneline $BASELINE_COMMIT..HEAD  # Find last good
git checkout [LAST_GOOD_COMMIT]

# Full abort
git reset --hard $BASELINE_COMMIT

# Resume from specific phase
/ralph-loop "Continue $TOOL_NAME from Phase $N..." \
    --max-iterations 10 \
    --completion-promise "PHASE_${N}_DONE"
```

## Execution Log Template

Create `./mcp_refactoring_workspace/$TOOL_NAME/execution_log.md`:

```markdown
# Execution Log: [TOOL_NAME]

**Started:** [TIMESTAMP] | **Baseline:** [COMMIT] | **Status:** In Progress

---

## Baseline

| Field | Value |
|-------|-------|
| Commit | [hash] |
| Branch | [branch] |
| Tests | [N] passed |

---

## Phases

### Phase 1: [Title]

| Field | Value |
|-------|-------|
| Started | [timestamp] |
| Commit | [hash] |
| Tests | [N] passed |
| Status | PASS/FAIL |
| Notes | [any issues] |

### Phase 2: [Title]
[same structure]

---

## Summary

| Metric | Value |
|--------|-------|
| Total Phases | [N] |
| Commits | [N] |
| Duration | [time] |
| Final Status | COMPLETE/BLOCKED |

---

## Commits

```
[hash1] [message1]
[hash2] [message2]
```

---

## Issues Encountered

| Phase | Issue | Resolution |
|-------|-------|------------|
| [N] | [description] | [how resolved] |
```
