---
name: mcp-refactor
description: "Ralph-powered MCP tool refactoring with autonomous convergent loops"
model: opus
context: fork
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Task, AskUserQuestion]
---

# MCP Tool Refactor - Ralph Wiggum Powered

## Overview

This command initiates a Ralph Wiggum-powered refactoring workflow for MCP tools. The workflow uses autonomous loops with backpressure gates to ensure each phase converges to completion.

## CRITICAL: Project Scope

**ALWAYS search for MCP tools in the CURRENT WORKING DIRECTORY only.**

| Rule | Details |
|------|---------|
| MCP Server Location | `./mcp_server/main.py` (relative to current directory) |
| Do NOT search | Other projects referenced in global CLAUDE.md |
| Do NOT search | `~/Developer/EROS-SD-MAIN-PROJECT/` or any external paths |
| Output directory | `./mcp_refactoring_workspace/<tool_name>/` |

Before starting Phase 1, verify the tool exists:
```bash
grep -n "def <tool_name>" ./mcp_server/main.py
```

If the tool is not found in `./mcp_server/main.py`, STOP and ask the user for the correct location.

## Usage

```
/mcp-refactor <tool_name> [options]
```

**Arguments:**
- `tool_name` (required): The MCP tool to refactor (e.g., `get_creator_profile`)

**Options:**
- `--phase <1|2|3>`: Start from specific phase (default: 1)
- `--max-iterations <N>`: Override default iteration limits
- `--skip-interview`: Use defaults for Phase 2 decisions

## Execution Protocol

### Phase 1: Technical Review Generation (Ralph Loop)

**Objective:** Generate comprehensive review.md with all quality gates passing.

**Loop Configuration:**
- Max iterations: 25
- Completion promise: `REVIEW_DONE`
- Backpressure: verify_review.py

**Success Criteria:**
1. Tool location verified (file:line via Read)
2. All SQL columns cross-referenced against schema
3. Return schema documented with field naming audit
4. Error handling pattern identified
5. All issues have correct severity
6. No placeholder text
7. Pipeline position identified
8. Consumer impact analysis complete

**Signs to Follow:**
- R1: Don't guess line numbers - verify via Read
- R2: PRAGMA table_info() for every column
- R3: Apply severity definitions strictly
- R4: Compare error handling to best practices
- R5: Grep all consumers, don't assume

### Phase 2: Interview & Spec Generation (Semi-Auto)

**Part A - Interview (Human Required):**
- Review Section 6 of review.md
- Answer architectural decision questions
- Determine scope (in/out) for MEDIUM issues

**Part B - Spec Generation (Ralph Loop):**
- Max iterations: 15
- Completion promise: `SPEC_DONE`
- Backpressure: verify_spec.py

**Success Criteria:**
1. All CRITICAL issues have implementation phases
2. All HIGH issues have implementation phases
3. Each phase has before/after code blocks
4. Each phase has verification command
5. Each phase has exact commit message
6. No vague language ("as needed", "if appropriate")
7. Line numbers verified

**Signs to Follow:**
- S1: Build DISTILLED_CONTEXT once, don't re-read review.md
- S2: Verify line numbers before writing spec
- S3: Specific changes only, no vague instructions
- S4: Every phase needs verification command
- S5: Exact commit messages in spec

### Phase 3: Refactoring Execution (Ralph Loops)

**Objective:** Execute each implementation phase as an independent loop.

**Loop Configuration (per phase):**
- Max iterations: 10
- Completion promise: `PHASE_N_DONE`
- Backpressure: pytest + git status

**Success Criteria (per phase):**
1. Code changes match spec exactly
2. All tests pass
3. Commit created with correct message
4. Working tree clean

**Signs to Follow:**
- E1: Verify file contents before modifying
- E2: Determine if test failure is old behavior vs regression
- E3: One phase = one commit
- E4: Log stale line number discrepancies
- E5: Never commit failing tests

## Backpressure Gates

Each phase has automated validation that must pass before the loop can exit:

```
Phase 1 → verify_review.py
  ├── File exists
  ├── No placeholders
  ├── All sections complete
  ├── Line numbers filled
  └── Schema verified

Phase 2 → verify_spec.py
  ├── File exists
  ├── All phases have before/after
  ├── No vague language
  └── Valid Python syntax

Phase 3 → verify_phase.py
  ├── pytest passes
  ├── Working tree clean
  └── Commit exists
```

## Error Recovery

**Cancel active loop:**
```bash
/cancel-ralph
```

**Rollback single phase:**
```bash
git revert HEAD --no-edit
```

**Rollback all phases:**
```bash
git reset --hard $BASELINE_COMMIT
```

**Resume from checkpoint:**
```bash
/mcp-refactor <tool_name> --phase <N>
```

## Cost Awareness

| Phase | Max Iterations | Actual Time | Estimated Cost |
|-------|----------------|-------------|----------------|
| 1 | 25 | ~3 min | $8-15 |
| 2 | 15 | ~2 min (with interview) | $5-10 |
| 3 (all phases) | 10 | ~3 min | $10-20 |
| /reflect | N/A | ~1.5 min | $2-4 |

**Total typical cost: $25-45** (lower than originally estimated based on actual runs)

Always start with conservative iteration limits. Failed attempts still cost money.

## Output Artifacts

```
./mcp_refactoring_workspace/
└── <tool_name>/
    ├── review.md          # Phase 1 output
    ├── <tool_name>.md     # Phase 2 output
    └── execution_log.md   # Phase 3 output
```

## Quick Reference

```
START REFACTOR
/mcp-refactor get_creator_profile

CANCEL LOOP
/cancel-ralph

CHECK STATUS
cat ./mcp_refactoring_workspace/get_creator_profile/execution_log.md

ROLLBACK
git reset --hard $(git rev-parse HEAD~3)
```
