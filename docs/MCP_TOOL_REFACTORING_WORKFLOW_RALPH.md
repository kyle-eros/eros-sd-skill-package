# MCP Tool Refactoring Workflow + Ralph Wiggum Method

**Version:** 4.0.0 | **Updated:** 2026-01-12 | **Claude Code:** v2.1.6 Opus 4.5

---

## Executive Summary

This workflow combines the **structured 3-phase MCP refactoring methodology** with the **Ralph Wiggum autonomous loop technique** to create a self-correcting, convergent refactoring system. Each phase runs as a Ralph loop with explicit completion promises, backpressure mechanisms, and automatic iteration until quality gates pass.

**Core Philosophy:** Instead of expecting perfect first attempts, define success criteria upfront and let the agent iterate toward them. Failures become data. Each iteration refines the approach based on what broke.

---

## Architecture Overview

```
                    RALPH-POWERED MCP REFACTORING PIPELINE

┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   PHASE 1 LOOP              PHASE 2 LOOP              PHASE 3 LOOPS        │
│   ─────────────             ─────────────             ─────────────        │
│   Review Gen                Spec Gen                  Execute Phases       │
│   (autonomous)              (semi-auto)               (autonomous)         │
│                                                                             │
│   ┌──────────┐             ┌──────────┐              ┌──────────┐          │
│   │  START   │             │  START   │              │  START   │          │
│   └────┬─────┘             └────┬─────┘              └────┬─────┘          │
│        │                        │                         │                 │
│        ▼                        ▼                         ▼                 │
│   ┌──────────┐             ┌──────────┐              ┌──────────┐          │
│   │ Execute  │             │ Interview│              │ Execute  │          │
│   │ Review   │             │ (human)  │              │ Phase N  │          │
│   └────┬─────┘             └────┬─────┘              └────┬─────┘          │
│        │                        │                         │                 │
│        ▼                        ▼                         ▼                 │
│   ┌──────────┐             ┌──────────┐              ┌──────────┐          │
│   │Backpres- │             │ Generate │              │Backpres- │          │
│   │sure Gate │             │ Spec     │              │sure Gate │          │
│   └────┬─────┘             └────┬─────┘              └────┬─────┘          │
│        │                        │                         │                 │
│   ┌────┴────┐              ┌────┴────┐               ┌────┴────┐           │
│   │         │              │         │               │         │           │
│   ▼         ▼              ▼         ▼               ▼         ▼           │
│  FAIL     PASS            FAIL     PASS            FAIL     PASS          │
│   │         │              │         │               │         │           │
│   │         │              │         │               │         │           │
│   └──┐      │              └──┐      │               └──┐      │           │
│      │      │                 │      │                  │      │           │
│      ▼      ▼                 ▼      ▼                  ▼      ▼           │
│   [LOOP]  [DONE]           [LOOP] [DONE]            [LOOP]  [NEXT]        │
│                                                                             │
│   Iterations: 15-25        Iterations: 10-15        Iterations: 5-10/phase │
│   Promise: REVIEW_DONE     Promise: SPEC_DONE       Promise: PHASE_N_DONE  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Claude Code v2.1.6 Features Integration

| Feature | Ralph Integration | Workflow Section |
|---------|-------------------|------------------|
| `context: fork` | Isolate loop iterations from main context | All phases |
| Stop hooks | Intercept exit, check completion promise | Loop control |
| `permissionMode: plan` | Read-only subagents during review | Phase 1 |
| Auto-compaction | Each loop iteration maintains independent context | All phases |
| Parallel tool calls | Multiple searches within single iteration | 1.1, 1.3 |
| Subagent resumability | Resume loops from HALT with full context | Error recovery |
| 3-level progressive disclosure | Load context on demand per iteration | Context management |

---

## Skill Package Structure

```
.claude/
├── commands/
│   └── mcp-refactor/
│       ├── mcp-refactor.md           # Main entry point
│       ├── review-loop.md            # Phase 1 loop prompt
│       ├── spec-loop.md              # Phase 2 loop prompt
│       └── execute-loop.md           # Phase 3 loop prompt
├── skills/
│   └── mcp-refactor/
│       ├── SKILL.md                  # Skill definition
│       ├── BACKPRESSURE.md           # Test/validation gates
│       └── SIGNS.md                  # Guardrails library
└── agents/
    └── mcp-refactor/
        ├── review-agent.md           # Phase 1 agent config
        ├── spec-agent.md             # Phase 2 agent config
        └── execute-agent.md          # Phase 3 agent config
```

---

## Skill Metadata (YAML Header)

```yaml
---
name: mcp-refactor
description: "Ralph-powered MCP tool refactoring with autonomous loops"
model: opus
context: fork
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Task]
hooks:
  stop:
    command: "check-completion-promise"
    exit_code: 2  # Continue loop if promise not found
---
```

---

## Phase 1: Technical Review Generation (Ralph Loop)

### Mission

Generate a comprehensive, accuracy-verified review of the target MCP tool using an autonomous loop that iterates until all quality gates pass.

### Loop Configuration

```bash
/ralph-loop "Generate technical review for [TOOL_NAME].

## Task
Read and analyze mcp_server/main.py to find [TOOL_NAME] implementation.
Generate mcp_refactoring/[tool_name]/review.md following the template.

## Success Criteria (ALL must pass)
- [ ] Tool location verified (file:line confirmed via Read)
- [ ] All SQL columns cross-referenced against PRAGMA table_info()
- [ ] Return schema documented with field naming audit
- [ ] Error handling pattern identified
- [ ] All issues have correct severity (match definitions)
- [ ] No [TBD] or placeholder text in output
- [ ] Pipeline position identified
- [ ] Consumer impact analysis complete
- [ ] review.md written to mcp_refactoring/[tool_name]/review.md

## Backpressure
Run validation: verify_review.py [tool_name]
- Schema columns must exist
- Line numbers must be current
- All sections must be complete

## Output
When ALL criteria pass, output: <promise>REVIEW_DONE</promise>

## If blocked
- Schema mismatch: Document in issues, continue
- Line numbers stale: Use Grep to find correct, update
- Missing context: Load from progressive disclosure levels" \
--max-iterations 25 \
--completion-promise "REVIEW_DONE"
```

### Backpressure Gates (Phase 1)

```python
# verify_review.py - Automated validation
def verify_review(tool_name: str) -> tuple[bool, list[str]]:
    """
    Returns (passed, errors) tuple.
    Loop continues if passed=False.
    """
    errors = []
    review_path = f"mcp_refactoring/{tool_name}/review.md"

    # Gate 1: File exists
    if not Path(review_path).exists():
        errors.append("FAIL: review.md not created")
        return False, errors

    content = Path(review_path).read_text()

    # Gate 2: No placeholders
    if "[TBD]" in content or "[TODO]" in content:
        errors.append("FAIL: Placeholder text found")

    # Gate 3: Required sections
    required_sections = [
        "## Quick Reference",
        "## 1. Current Implementation",
        "## 2. Database Layer",
        "## 3. Pipeline Position",
        "## 4. Issues",
        "## 5. Refactoring Plan",
        "## 6. Interview Questions"
    ]
    for section in required_sections:
        if section not in content:
            errors.append(f"FAIL: Missing section: {section}")

    # Gate 4: Line numbers verified
    if "Lines | [" in content or "lines [" in content.lower():
        errors.append("FAIL: Line numbers not filled in")

    # Gate 5: Schema verification
    if "❌" in content and "CRITICAL" not in content:
        errors.append("WARN: Schema mismatches not flagged as CRITICAL")

    return len(errors) == 0, errors
```

### Signs Library (Phase 1)

```markdown
## SIGNS: Review Generation

### SIGN-R1: Don't Guess Line Numbers
WRONG: "The function is around line 500"
RIGHT: Read mcp_server/main.py, search for exact decorator, record exact lines

### SIGN-R2: Verify Every Column
WRONG: "The query uses the standard columns"
RIGHT: For EACH column in SQL, run PRAGMA table_info(), confirm exists

### SIGN-R3: Don't Inflate Severity
WRONG: Mark everything HIGH because it seems important
RIGHT: Apply severity definitions strictly:
  - CRITICAL: Blocks pipeline, data corruption
  - HIGH: Performance degradation, missing validation
  - MEDIUM: Missing features, inconsistent patterns
  - LOW: Code quality, documentation

### SIGN-R4: Check Error Handling
WRONG: Assume error handling is fine if no obvious issues
RIGHT: Extract actual error return pattern, compare to mcp_best_practices.md Section 2

### SIGN-R5: Don't Skip Consumer Analysis
WRONG: "Other code probably uses this tool"
RIGHT: Run Grep for tool name across python/ and skills/, list all usages
```

### Loop Iteration Flow (Phase 1)

```
ITERATION N:
├── Load context (Level 1 always, Level 2 by issue type)
├── Execute review generation steps
├── Write review.md
├── Run verify_review.py
├── Check result:
│   ├── ALL PASS → Output <promise>REVIEW_DONE</promise>
│   └── ANY FAIL →
│       ├── Log which gates failed
│       ├── Review own output
│       ├── Fix issues
│       └── Loop continues (iteration N+1)
```

---

## Phase 2: Interview & Spec Generation (Semi-Autonomous)

### Mission

Conduct targeted interview, then run autonomous spec generation loop until complete.

### Two-Part Structure

**Part 2A: Interview (Human-in-Loop)**
- Uses AskUserQuestion tool
- Cannot be fully automated (requires user decisions)
- Maximum 3 question batches

**Part 2B: Spec Generation (Ralph Loop)**
- Fully autonomous once interview complete
- Generates [tool_name].md specification

### Part 2A: Interview Protocol

```yaml
# Interview questions batched by category
# Use AskUserQuestion with max 3 batches

Batch 1 - Architectural Decisions:
  - Questions from review.md Section 6 "Decisions Required"
  - Fix approach choices for HIGH/CRITICAL issues

Batch 2 - Scope Decisions:
  - Include/defer for MEDIUM issues
  - Breaking change migration approach

Batch 3 - Business Context:
  - Edge case handling preferences
  - Downstream impact acceptance
```

### Part 2B: Spec Loop Configuration

```bash
/ralph-loop "Generate refactoring specification for [TOOL_NAME].

## Context
- Review: mcp_refactoring/[tool_name]/review.md
- Interview decisions: [DISTILLED_DECISIONS]

## Task
Generate mcp_refactoring/[tool_name]/[tool_name].md specification.

## Success Criteria (ALL must pass)
- [ ] All CRITICAL issues have implementation phases
- [ ] All HIGH issues have implementation phases
- [ ] Each phase has before/after code blocks
- [ ] Each phase has verification command
- [ ] Each phase has exact commit message
- [ ] No [TBD] or 'as needed' phrases
- [ ] Line numbers verified via Read
- [ ] Breaking changes have migration path
- [ ] Test plan includes all modified behavior

## Token Management
If spec exceeds 2500 tokens:
- Use context: fork
- Write sections incrementally
- Save after each major section

## Backpressure
Run: verify_spec.py [tool_name]
- All phases must have complete structure
- All code blocks must be syntactically valid
- All file references must exist

## Output
When ALL criteria pass, output: <promise>SPEC_DONE</promise>" \
--max-iterations 15 \
--completion-promise "SPEC_DONE"
```

### DISTILLED_CONTEXT Template

```python
# Build ONCE from review.md + interview, reference throughout
DISTILLED_CONTEXT = {
    "tool_identity": {
        "name": "[tool_name]",
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

### Backpressure Gates (Phase 2)

```python
# verify_spec.py - Automated validation
def verify_spec(tool_name: str) -> tuple[bool, list[str]]:
    errors = []
    spec_path = f"mcp_refactoring/{tool_name}/{tool_name}.md"

    if not Path(spec_path).exists():
        errors.append("FAIL: Spec file not created")
        return False, errors

    content = Path(spec_path).read_text()

    # Gate 1: All phases have structure
    import re
    phases = re.findall(r'### Phase \d+:', content)
    for phase_match in phases:
        phase_section = extract_section(content, phase_match)
        if "**Before:**" not in phase_section:
            errors.append(f"FAIL: {phase_match} missing Before block")
        if "**After:**" not in phase_section:
            errors.append(f"FAIL: {phase_match} missing After block")
        if "**Verification:**" not in phase_section:
            errors.append(f"FAIL: {phase_match} missing Verification")
        if "**Commit:**" not in phase_section:
            errors.append(f"FAIL: {phase_match} missing Commit message")

    # Gate 2: No vague language
    vague_phrases = ["as needed", "if appropriate", "when necessary", "TBD"]
    for phrase in vague_phrases:
        if phrase.lower() in content.lower():
            errors.append(f"FAIL: Vague phrase found: '{phrase}'")

    # Gate 3: Code blocks are valid Python
    code_blocks = re.findall(r'```python\n(.*?)```', content, re.DOTALL)
    for i, block in enumerate(code_blocks):
        try:
            compile(block, f'<block_{i}>', 'exec')
        except SyntaxError as e:
            errors.append(f"FAIL: Invalid Python in code block {i}: {e}")

    return len(errors) == 0, errors
```

### Signs Library (Phase 2)

```markdown
## SIGNS: Spec Generation

### SIGN-S1: Don't Re-Read review.md
WRONG: Read review.md multiple times during spec generation
RIGHT: Build DISTILLED_CONTEXT once, reference throughout

### SIGN-S2: Verify Line Numbers Before Writing
WRONG: Copy line numbers from review.md without checking
RIGHT: Read actual file, confirm lines match, update if stale

### SIGN-S3: No Vague Instructions
WRONG: "Update error handling as appropriate"
RIGHT: "Change line 147 from `return {'error': msg}` to `return {'error_code': 'INVALID_PARAM', 'error_message': msg}`"

### SIGN-S4: Every Phase Needs Verification
WRONG: "Test the changes"
RIGHT: "Run: pytest python/tests/test_mcp_tools.py::test_[tool_name] -v"

### SIGN-S5: Commit Messages from Spec
WRONG: "Commit your changes"
RIGHT: "Commit: `fix([tool_name]): add structured error responses`"
```

---

## Phase 3: Refactoring Execution (Ralph Loop per Phase)

### Mission

Execute each implementation phase as an independent Ralph loop with atomic commits and verification gates.

### Master Orchestration

```bash
# Phase 3 orchestrator - runs sequential loops for each spec phase
#!/bin/bash

TOOL_NAME="$1"
SPEC_FILE="mcp_refactoring/${TOOL_NAME}/${TOOL_NAME}.md"
BASELINE_COMMIT=$(git rev-parse --short HEAD)

# Extract phase count from spec
PHASE_COUNT=$(grep -c "### Phase [0-9]" "$SPEC_FILE")

echo "=== PHASE 3: EXECUTING $PHASE_COUNT PHASES ==="
echo "Baseline: $BASELINE_COMMIT"

for ((i=1; i<=PHASE_COUNT; i++)); do
    echo "=== STARTING PHASE $i/$PHASE_COUNT ==="

    /ralph-loop "Execute Phase $i of $TOOL_NAME refactoring.

## Spec Reference
File: $SPEC_FILE
Section: 4. Implementation Phases -> Phase $i

## Task
1. Read spec section for Phase $i
2. Read files to modify (verify line numbers current)
3. Make EXACT changes per before/after blocks
4. Run verification command from spec
5. If tests pass: commit with EXACT message from spec
6. Report result

## Success Criteria
- [ ] Code changes match spec exactly
- [ ] All tests pass
- [ ] Commit created with correct message
- [ ] Working tree clean

## Rules
- Line numbers stale -> Grep for pattern, find correct, proceed
- Tests fail (checking old behavior) -> Update test, re-run
- Tests fail (regression) -> DO NOT COMMIT, report and stop
- Spec unclear -> STOP, report ambiguity

## Backpressure
pytest python/tests/ -q
git status (must be clean after commit)

## Output
When phase complete and committed: <promise>PHASE_${i}_DONE</promise>
If blocked: <promise>PHASE_${i}_BLOCKED</promise>" \
    --max-iterations 10 \
    --completion-promise "PHASE_${i}_DONE"

    # Check if blocked
    if grep -q "BLOCKED" /tmp/ralph_output; then
        echo "=== PHASE $i BLOCKED - STOPPING ==="
        exit 1
    fi

    echo "=== PHASE $i COMPLETE ==="
done

echo "=== ALL PHASES COMPLETE ==="
echo "Commits since baseline:"
git log --oneline "$BASELINE_COMMIT"..HEAD
```

### Individual Phase Loop Template

```bash
/ralph-loop "Execute [TOOL_NAME] Phase [N]: [TITLE]

## Spec
Read: mcp_refactoring/[tool_name]/[tool_name].md Section 4 Phase [N]

## Pre-Read Verification
Quote the exact spec section before executing:
'''
[PASTE SPEC SECTION HERE]
'''
Verified: Read([tool_name].md) matches quoted text

## Changes
| File | Line | Change |
|------|------|--------|
| [from spec] | [verify current] | [from spec] |

## Execution
1. Read each file to modify
2. Verify line numbers (Grep if stale)
3. Apply changes per before/after blocks
4. Run: [verification command from spec]
5. If pass: git add . && git commit -m '[message from spec]'
6. git status (confirm clean)

## Success Criteria
- [ ] All changes from spec applied
- [ ] pytest passes
- [ ] Commit created
- [ ] Tree clean

## Output
<promise>PHASE_[N]_DONE</promise> when complete
<promise>PHASE_[N]_BLOCKED:[reason]</promise> if blocked" \
--max-iterations 10 \
--completion-promise "PHASE_[N]_DONE"
```

### Backpressure Gates (Phase 3)

```python
# verify_phase.py - Per-phase validation
def verify_phase(tool_name: str, phase_num: int) -> tuple[bool, list[str]]:
    errors = []

    # Gate 1: Tests pass
    result = subprocess.run(
        ["pytest", "python/tests/", "-q"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        errors.append(f"FAIL: Tests failed\n{result.stdout}\n{result.stderr}")

    # Gate 2: Working tree clean
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True
    )
    if status.stdout.strip():
        errors.append(f"FAIL: Uncommitted changes:\n{status.stdout}")

    # Gate 3: Commit exists for this phase
    log = subprocess.run(
        ["git", "log", "-1", "--oneline"],
        capture_output=True, text=True
    )
    if tool_name.lower() not in log.stdout.lower():
        errors.append(f"WARN: Latest commit may not be for {tool_name}")

    return len(errors) == 0, errors
```

### Signs Library (Phase 3)

```markdown
## SIGNS: Execution

### SIGN-E1: Verify Before Modifying
WRONG: Trust line numbers from spec blindly
RIGHT: Read file, Grep for pattern, confirm current location

### SIGN-E2: Don't Fix Tests for Wrong Reasons
WRONG: Tests fail -> immediately update tests
RIGHT: Tests fail -> determine if checking OLD behavior (update) or NEW behavior (regression -> rollback)

### SIGN-E3: Atomic Commits Only
WRONG: Make all changes, commit at end
RIGHT: One phase = one commit, verification between each

### SIGN-E4: Report Stale Line Numbers
WRONG: Silently adjust and continue
RIGHT: Log "Spec line [X] was actually [Y]" for audit trail

### SIGN-E5: Never Commit Failing Tests
WRONG: Commit now, fix tests later
RIGHT: If tests fail with regression, rollback immediately, report, stop
```

---

## Error Recovery & Rollback

### Loop-Level Recovery

```bash
# If a loop gets stuck, cancel and diagnose
/cancel-ralph

# Review what happened
git log --oneline -5
git diff HEAD~1

# Resume from checkpoint
/ralph-loop "Continue [TOOL_NAME] Phase [N].
Previous attempt blocked because: [REASON]
Fix: [ADJUSTMENT]
..." --max-iterations 10
```

### Phase-Level Rollback

```bash
# Rollback single phase
git revert HEAD --no-edit
pytest python/tests/ -q  # Verify rollback worked

# Rollback multiple phases
git log --oneline $BASELINE_COMMIT..HEAD  # Find last good
git reset --hard [LAST_GOOD_COMMIT]
```

### Full Abort

```bash
# Complete rollback to baseline
git reset --hard $BASELINE_COMMIT
echo "Aborted at $(date)" >> mcp_refactoring/[tool_name]/execution_log.md
```

---

## Cost Management

### Token Budget per Phase

| Phase | Iterations | Tokens/Iter | Max Cost |
|-------|------------|-------------|----------|
| Phase 1 (Review) | 15-25 | ~4000 | $15-25 |
| Phase 2 (Spec) | 10-15 | ~4500 | $12-18 |
| Phase 3 (per phase) | 5-10 | ~800 | $2-5/phase |
| **Total (3 impl phases)** | | | **$35-55** |

### Cost Controls

```bash
# Set conservative iteration limits for first run
/ralph-loop "..." --max-iterations 15  # Not 50

# Monitor usage
claude --usage  # Check token consumption

# Use appropriate models
# Opus: Coordination, complex reasoning
# Sonnet: Searches, file reads, implementation
# Haiku: Status checks, simple validation
```

---

## Complete Workflow Invocation

### Quick Start

```bash
# 1. Set up directory
mkdir -p mcp_refactoring/[tool_name]

# 2. Run Phase 1 (Review Generation)
/ralph-loop "Generate technical review for [TOOL_NAME]..." \
  --max-iterations 25 --completion-promise "REVIEW_DONE"

# 3. Conduct Interview (manual)
# Review mcp_refactoring/[tool_name]/review.md
# Answer questions from Section 6

# 4. Run Phase 2 (Spec Generation)
/ralph-loop "Generate spec for [TOOL_NAME] with decisions..." \
  --max-iterations 15 --completion-promise "SPEC_DONE"

# 5. Run Phase 3 (Execution)
./execute_phases.sh [tool_name]

# 6. Verify & Learn
git log --oneline $BASELINE..HEAD
/reflect  # Capture learnings
```

### Single Command (Advanced)

```bash
# Full pipeline with defaults
/mcp-refactor [TOOL_NAME]

# This invokes:
# 1. Phase 1 loop with standard review template
# 2. Pauses for interview
# 3. Phase 2 loop with interview decisions
# 4. Phase 3 loops for each implementation phase
```

---

## Appendix A: Complete Signs Library

### Phase 1 - Review Generation

| Sign ID | Don't | Do Instead |
|---------|-------|------------|
| R1 | Guess line numbers | Read file, search for decorator, record exact |
| R2 | Assume columns exist | PRAGMA table_info() for each column |
| R3 | Inflate severity | Apply definitions strictly |
| R4 | Skip error handling check | Extract actual pattern, compare to best practices |
| R5 | Skip consumer analysis | Grep across all potential consumers |
| R6 | Load all context upfront | Use 3-level progressive disclosure |
| R7 | Run searches sequentially | Parallel tool calls for independent searches |

### Phase 2 - Spec Generation

| Sign ID | Don't | Do Instead |
|---------|-------|------------|
| S1 | Re-read review.md | Build DISTILLED_CONTEXT once |
| S2 | Copy stale line numbers | Verify via Read before writing |
| S3 | Use vague instructions | Specific line, specific change |
| S4 | Skip verification commands | Every phase needs pytest/validation |
| S5 | Generic commit messages | Exact message in spec |
| S6 | Oversize output | Use context: fork if >2500 tokens |

### Phase 3 - Execution

| Sign ID | Don't | Do Instead |
|---------|-------|------------|
| E1 | Trust spec line numbers | Verify before modifying |
| E2 | Update tests automatically | Determine if old behavior or regression |
| E3 | Batch commits | One phase = one commit |
| E4 | Silent line number fixes | Log discrepancy for audit |
| E5 | Commit failing tests | Rollback, report, stop |
| E6 | Parallel dependent phases | Check dependency table, sequential if needed |

---

## Appendix B: Backpressure Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKPRESSURE MECHANISMS                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PHASE 1                PHASE 2                PHASE 3              │
│  ────────               ────────               ────────             │
│                                                                     │
│  verify_review.py       verify_spec.py         verify_phase.py      │
│  ├─ File exists         ├─ File exists         ├─ pytest passes     │
│  ├─ No placeholders     ├─ All phases have     ├─ Tree clean        │
│  ├─ All sections        │   before/after       ├─ Commit exists     │
│  ├─ Line numbers        ├─ No vague language   │                    │
│  └─ Schema verified     └─ Valid Python        │                    │
│                                                                     │
│  FAIL → Loop            FAIL → Loop            FAIL → Loop          │
│  PASS → REVIEW_DONE     PASS → SPEC_DONE       PASS → PHASE_N_DONE  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Appendix C: Completion Promise Reference

| Phase | Promise | Meaning |
|-------|---------|---------|
| 1 | `<promise>REVIEW_DONE</promise>` | review.md complete, all gates pass |
| 2 | `<promise>SPEC_DONE</promise>` | [tool].md complete, all gates pass |
| 3.1 | `<promise>PHASE_1_DONE</promise>` | Implementation phase 1 committed |
| 3.N | `<promise>PHASE_N_DONE</promise>` | Implementation phase N committed |
| 3.X | `<promise>PHASE_X_BLOCKED:[reason]</promise>` | Phase blocked, needs human |
| Final | `<promise>REFACTOR_COMPLETE</promise>` | All phases done |

---

## Appendix D: Quick Reference Card

```
RALPH-POWERED MCP REFACTORING
═════════════════════════════

PHASE 1: REVIEW LOOP
────────────────────
/ralph-loop "Generate review..." --max-iterations 25 --completion-promise "REVIEW_DONE"
Gates: verify_review.py
Signs: R1-R7

PHASE 2: SPEC LOOP (after interview)
────────────────────────────────────
/ralph-loop "Generate spec..." --max-iterations 15 --completion-promise "SPEC_DONE"
Gates: verify_spec.py
Signs: S1-S6

PHASE 3: EXECUTION LOOPS
────────────────────────
For each phase in spec:
  /ralph-loop "Execute Phase N..." --max-iterations 10 --completion-promise "PHASE_N_DONE"
Gates: verify_phase.py (pytest + git status)
Signs: E1-E6

ERROR RECOVERY
──────────────
Cancel: /cancel-ralph
Rollback phase: git revert HEAD
Rollback all: git reset --hard $BASELINE
Resume: /ralph-loop "Continue from..." --max-iterations 10

COST CONTROL
────────────
Always set --max-iterations
Start small (10-15), increase as needed
Use appropriate model tiers

SAFETY
──────
Overnight runs: ALWAYS sandbox
Check token consumption: claude --usage
Set spending limits if available
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 4.0.0 | 2026-01-12 | Full Ralph Wiggum integration with autonomous loops, backpressure gates, signs library |
| 3.0.0 | 2026-01-12 | Best practices integration (original) |
| 2.0.0 | 2026-01-12 | Complete rewrite for Claude Code v2.1.6 |
| 1.0.0 | 2026-01-10 | Initial workflow |

---

## Changelog: v4.0.0 (Ralph Integration)

### Core Architecture
- **Architecture Overview**: Visual pipeline showing Ralph loops at each phase
- **Skill Package Structure**: Complete .claude/ directory layout for skill installation
- **Loop Configuration**: Detailed /ralph-loop commands for each phase

### Backpressure System
- **verify_review.py**: Automated Phase 1 validation script
- **verify_spec.py**: Automated Phase 2 validation script
- **verify_phase.py**: Automated Phase 3 per-phase validation
- **Backpressure Summary**: Visual diagram of all gates

### Signs Library
- **Phase 1 Signs (R1-R7)**: Review generation guardrails
- **Phase 2 Signs (S1-S6)**: Spec generation guardrails
- **Phase 3 Signs (E1-E6)**: Execution guardrails
- **Complete Signs Appendix**: Tabular reference

### Loop Management
- **Completion Promises**: Explicit promise format for each phase
- **Error Recovery**: Loop cancellation, rollback, resume procedures
- **Cost Management**: Token budgets and iteration limits

### Claude Code v2.1.6 Integration
- Stop hook integration for loop control
- context: fork for isolated iterations
- Auto-compaction awareness
- Parallel tool call optimization
