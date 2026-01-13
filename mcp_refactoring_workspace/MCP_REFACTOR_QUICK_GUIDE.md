# MCP Refactor Quick Guide

**Your cheat sheet for refactoring MCP tools with Ralph Wiggum loops**

---

## What This Does

Takes an MCP tool (like `get_creator_profile`) and refactors it through 3 phases:
1. **Review** - Analyze the tool, find issues
2. **Spec** - Create a detailed fix plan
3. **Execute** - Make the changes, one commit at a time

The "Ralph Wiggum" part means Claude keeps trying until it actually works, not just when it *thinks* it's done.

---

## Before You Start

```bash
# 1. Make sure you're in the right directory
cd /Users/kylemerriman/Developer/eros-sd-skill-package

# 2. Make sure git is clean
git status  # Should show no uncommitted changes

# 3. Know which tool you want to refactor
# Example: get_creator_profile, get_volume_config, etc.
```

---

## The 3 Phases

### Phase 1: Review (Automatic)

**What happens:** Claude analyzes your tool and creates `review.md`

**Command:**
```
/ralph-loop "Generate technical review for YOUR_TOOL_NAME.
Read mcp_server/main.py to find the tool.
Create mcp_refactoring/YOUR_TOOL_NAME/review.md with all issues found.
Output <promise>REVIEW_DONE</promise> when complete." --max-iterations 25 --completion-promise "REVIEW_DONE"
```

**Replace:** `YOUR_TOOL_NAME` with your actual tool (e.g., `get_creator_profile`)

**Output:** `mcp_refactoring/YOUR_TOOL_NAME/review.md`

---

### Phase 2: Interview + Spec (Semi-Automatic)

**Step 1 - Review the review.md:**
```bash
# Look at Section 6 "Interview Questions"
cat mcp_refactoring/YOUR_TOOL_NAME/review.md
```

**Step 2 - Answer the questions** (Claude will ask you)

**Step 3 - Generate the spec:**
```
/ralph-loop "Generate refactoring spec for YOUR_TOOL_NAME.
Use the review at mcp_refactoring/YOUR_TOOL_NAME/review.md.
Create mcp_refactoring/YOUR_TOOL_NAME/YOUR_TOOL_NAME.md with implementation phases.
Output <promise>SPEC_DONE</promise> when complete." --max-iterations 15 --completion-promise "SPEC_DONE"
```

**Output:** `mcp_refactoring/YOUR_TOOL_NAME/YOUR_TOOL_NAME.md`

---

### Phase 3: Execute (Automatic per phase)

**For each implementation phase in the spec:**

```
/ralph-loop "Execute YOUR_TOOL_NAME Phase 1.
Follow the spec at mcp_refactoring/YOUR_TOOL_NAME/YOUR_TOOL_NAME.md.
Make the changes, run tests, commit if passing.
Output <promise>PHASE_1_DONE</promise> when complete." --max-iterations 10 --completion-promise "PHASE_1_DONE"
```

**Then Phase 2:**
```
/ralph-loop "Execute YOUR_TOOL_NAME Phase 2..." --max-iterations 10 --completion-promise "PHASE_2_DONE"
```

**And so on for each phase.**

---

## Emergency Commands

| Situation | Command |
|-----------|---------|
| Loop is stuck | `/cancel-ralph` |
| Undo last phase | `git revert HEAD --no-edit` |
| Undo everything | `git reset --hard HEAD~3` (adjust number) |
| Check progress | `git log --oneline -5` |

---

## Tips for Success

1. **Start small** - Pick a simple tool for your first refactor

2. **Set max iterations** - Always include `--max-iterations` (start with 10-15)

3. **Watch the output** - If Claude keeps looping on the same error, cancel and read what's wrong

4. **Clean git first** - Commit or stash any work before starting

5. **One tool at a time** - Don't try to refactor multiple tools simultaneously

---

## What "Done" Looks Like

After a successful refactor you'll have:

```
mcp_refactoring/
└── YOUR_TOOL_NAME/
    ├── review.md          # Analysis of the tool
    ├── YOUR_TOOL_NAME.md  # The refactoring plan
    └── execution_log.md   # What was done

git log --oneline:
abc1234 fix(YOUR_TOOL_NAME): phase 3 changes
def5678 fix(YOUR_TOOL_NAME): phase 2 changes
ghi9012 fix(YOUR_TOOL_NAME): phase 1 changes
```

---

## Example: Refactoring get_volume_config

```bash
# 1. Go to project
cd /Users/kylemerriman/Developer/eros-sd-skill-package

# 2. Phase 1 - Generate review
/ralph-loop "Generate technical review for get_volume_config..." --max-iterations 25 --completion-promise "REVIEW_DONE"

# 3. Check the review
cat mcp_refactoring/get_volume_config/review.md

# 4. Phase 2 - Answer questions, generate spec
/ralph-loop "Generate spec for get_volume_config..." --max-iterations 15 --completion-promise "SPEC_DONE"

# 5. Phase 3 - Execute each phase
/ralph-loop "Execute get_volume_config Phase 1..." --max-iterations 10 --completion-promise "PHASE_1_DONE"
/ralph-loop "Execute get_volume_config Phase 2..." --max-iterations 10 --completion-promise "PHASE_2_DONE"

# 6. Verify
git log --oneline -5
pytest python/tests/ -q
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────┐
│         MCP REFACTOR CHEAT SHEET            │
├─────────────────────────────────────────────┤
│                                             │
│  PHASE 1: Review                            │
│  /ralph-loop "Generate review..."           │
│  --completion-promise "REVIEW_DONE"         │
│  Output: review.md                          │
│                                             │
│  PHASE 2: Spec                              │
│  /ralph-loop "Generate spec..."             │
│  --completion-promise "SPEC_DONE"           │
│  Output: [tool].md                          │
│                                             │
│  PHASE 3: Execute (repeat per phase)        │
│  /ralph-loop "Execute Phase N..."           │
│  --completion-promise "PHASE_N_DONE"        │
│  Output: commits                            │
│                                             │
│  CANCEL: /cancel-ralph                      │
│  UNDO:   git revert HEAD                    │
│                                             │
└─────────────────────────────────────────────┘
```

---

**Questions?** Ask Claude: "Help me refactor [tool_name]"

**Full docs:** `/Users/kylemerriman/Developer/eros-sd-skill-package/docs/MCP_TOOL_REFACTORING_WORKFLOW_RALPH.md`
