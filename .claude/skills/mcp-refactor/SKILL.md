# MCP Tool Refactor Skill

## Identity

**Name:** mcp-refactor
**Version:** 4.0.0
**Category:** Refactoring / Code Quality
**Model Tier:** opus (coordination), sonnet (execution)

## Purpose

This skill provides a Ralph Wiggum-powered autonomous refactoring workflow for MCP tools. It uses iterative loops with backpressure gates to ensure convergent, high-quality refactoring outcomes.

## Core Methodology: Ralph Wiggum

The Ralph Wiggum method keeps Claude running in a continuous loop until tasks are actually complete—not just when Claude thinks it's done.

**Key Principles:**
1. Define success criteria upfront
2. Let the agent iterate toward them
3. Failures become data for the next iteration
4. Backpressure (tests, validation) automatically rejects wrong outputs

## Workflow Phases

### Phase 1: Technical Review Generation
- **Mode:** Fully autonomous loop
- **Max Iterations:** 25
- **Completion Promise:** `REVIEW_DONE`
- **Output:** `review.md`

### Phase 2: Interview & Spec Generation

**Mode:** Semi-autonomous (interview + loop)  
**Max Iterations:** 15  
**Completion Signal:** `SPEC_DONE`  
**Output:** `[tool_name].md`

#### Interview Requirements

1. Use `AskUserQuestionTool` to gather specification details
2. Ask probing, non-obvious questions—avoid surface-level queries Claude could infer
3. Cover edge cases, error handling, input/output formats, and integration points
4. be very in-depth and continue interviewing me continually until it’s complete
5. Generate `[tool_name].md` spec file upon completion
6. Replace existing `fixes.md` with finalized version

### Phase 3: Refactoring Execution
- **Mode:** Sequential autonomous loops (one per phase)
- **Max Iterations:** 10 per phase
- **Completion Promise:** `PHASE_N_DONE`
- **Output:** N commits + `execution_log.md`

## Backpressure System

Each phase has validation gates that must pass before the loop can exit:

| Phase | Validator | Key Checks |
|-------|-----------|------------|
| 1 | verify_review.py | No placeholders, all sections, schema verified |
| 2 | verify_spec.py | All phases have before/after, no vague language |
| 3 | verify_phase.py | pytest passes, tree clean, commit exists |

## Signs Library

Pre-configured guardrails based on common failure patterns:

### Review Signs (R1-R7)
- R1: Don't guess line numbers
- R2: Verify every column
- R3: Don't inflate severity
- R4: Check error handling
- R5: Don't skip consumer analysis
- R6: Progressive context disclosure
- R7: Parallel tool calls

### Spec Signs (S1-S6)
- S1: Don't re-read review.md
- S2: Verify line numbers
- S3: No vague instructions
- S4: Every phase needs verification
- S5: Commit messages from spec
- S6: Use context:fork if >2500 tokens

### Execution Signs (E1-E6)
- E1: Verify before modifying
- E2: Distinguish old behavior vs regression
- E3: Atomic commits only
- E4: Report stale line numbers
- E5: Never commit failing tests
- E6: Respect phase dependencies

## Dependencies

**Required Context Files:**
- `CLAUDE.md` (project conventions)
- `LEARNINGS.md` (prior corrections)
- `docs/mcp_best_practices.md` (tool standards)

**Required Tools:**
- Read, Write, Edit, Bash, Grep, Glob
- Task (for subagents)
- AskUserQuestion (for Phase 2 interview)

## Integration Points

**Stop Hook:**
```yaml
hooks:
  stop:
    command: "check-completion-promise"
    exit_code: 2  # Continue loop if promise not found
```

**Context Management:**
- Use `context: fork` for high-output operations (>2500 tokens)
- Each loop iteration maintains independent context
- Auto-compaction applies separately to subagent transcripts

## Cost Model

| Operation | Estimated Cost |
|-----------|----------------|
| Full refactor (3 impl phases) | $35-55 |
| Review only | $15-25 |
| Spec only | $12-18 |
| Single impl phase | $2-5 |

## Success Metrics

A successful refactor produces:
1. Comprehensive review.md with verified information
2. Complete spec with executable phases
3. Atomic commits for each implementation phase
4. All tests passing
5. Clean git history
6. Captured learnings for future reference

## Failure Handling

**Loop stuck:** `/cancel-ralph`
**Phase failed:** `git revert HEAD`
**Full abort:** `git reset --hard $BASELINE`
**Resume:** `/mcp-refactor <tool> --phase <N>`

---

## Lessons Learned (Updated 2026-01-13)

### From get_send_type_captions v2.0.0 Refactor

1. **Dead Code Detection**: Data analysis (SELECT DISTINCT, COUNT GROUP BY) reveals when hardcoded mappings don't match actual data

2. **Pattern Consistency**: Caption tools should share patterns - freshness JOIN, pool_stats, metadata block

3. **Test Fixture Completeness**: Helper functions define implicit schema requirements - read them before writing fixtures

4. **Phase Consolidation**: Tightly-coupled changes to single function are better as one commit than artificial separation

5. **Interview Quality**: Detailed user answers with implementation specifics dramatically improve execution accuracy
