# Skill Package Editor — Ralph Wiggum Loop

## Identity

**Name:** skill-editor
**Version:** 1.0.0
**Category:** Developer Tools
**Model Tier:** Sonnet

## Purpose

Add, edit, or refactor sections within Claude Code multi-agent skill packages autonomously using Ralph Wiggum loops with measurable success criteria and backpressure validation.

---

## EROS Context

This skill editor primarily maintains the EROS schedule generation pipeline skills:

| Skill | Location | Model | Purpose |
|-------|----------|-------|---------|
| eros-schedule-generator | `.claude/skills/eros-schedule-generator/` | Sonnet | Phase 2: Build schedule items |
| eros-schedule-validator | `.claude/skills/eros-schedule-validator/` | Opus | Phase 3: Validate hard gates |

### Key EROS Constraints to Verify

When editing EROS skills, ensure changes preserve these invariants:

| Constraint | Count | Source |
|------------|-------|--------|
| Hard Gates | 5 | DOMAIN_KNOWLEDGE.md Section 3 |
| MCP Tools (must-keep) | 16 | DOMAIN_KNOWLEDGE.md Section 11 |
| ValidationCertificate | v3.0 | DOMAIN_KNOWLEDGE.md Section 9 |
| CreatorContext fields | 10 top-level | Generator SKILL.md |
| Pricing bounds | $5-$50 | DOMAIN_KNOWLEDGE.md Section 4 |
| Volume tiers | 5 | DOMAIN_KNOWLEDGE.md Section 2 |

### The 5 Hard Gates

| Gate | Name |
|------|------|
| Gate 1 | Vault Compliance |
| Gate 2 | AVOID Tier Exclusion |
| Gate 3 | Page Type Restrictions |
| Gate 4 | Send Type Diversity |
| Gate 5 | Flyer Requirement |

---

## Dependencies

Before using skill-editor on EROS skills:

1. Read `LEARNINGS.md` - HIGH confidence items affect what can be changed
2. Read `CLAUDE.md` - Hard gates are immutable constraints
3. Read `docs/DOMAIN_KNOWLEDGE.md` - Business rules reference

---

## Quick Start

### One-Liner Commands

```bash
# ADD a new section
/ralph-loop "EDIT_TYPE=add TARGET_FILE=.claude/skills/my_skill/SKILL.md SECTION_NAME='New Feature' DESCRIPTION='Add feature X'
$(cat .claude/skills/skill-editor/PROMPT_skill_edit.md)" --max-iterations 12 --completion-promise "SKILL_EDIT_COMPLETE"

# EDIT an existing section
/ralph-loop "EDIT_TYPE=edit TARGET_FILE=.claude/skills/eros-schedule-generator/SKILL.md SECTION_NAME='MCP Tools' DESCRIPTION='Add new validation'
$(cat .claude/skills/skill-editor/PROMPT_skill_edit.md)" --max-iterations 12 --completion-promise "SKILL_EDIT_COMPLETE"

# REFACTOR across files
/ralph-loop "EDIT_TYPE=refactor TARGET_FILE=.claude/skills/eros-schedule-generator/SKILL.md SECTION_NAME='Error Handling' RELATED_FILES='.claude/skills/eros-schedule-validator/SKILL.md' DESCRIPTION='Standardize errors'
$(cat .claude/skills/skill-editor/PROMPT_skill_edit.md)" --max-iterations 15 --completion-promise "SKILL_EDIT_COMPLETE"

# DELETE a section
/ralph-loop "EDIT_TYPE=delete TARGET_FILE=docs/old.md SECTION_NAME='Deprecated' DESCRIPTION='Remove unused'
$(cat .claude/skills/skill-editor/PROMPT_skill_edit.md)" --max-iterations 8 --completion-promise "SKILL_EDIT_COMPLETE"
```

### Using the Script

```bash
# Make executable
chmod +x .claude/skills/skill-editor/ralph_skill_edit.sh

# Add section to EROS generator
./.claude/skills/skill-editor/ralph_skill_edit.sh add -f .claude/skills/eros-schedule-generator/SKILL.md -s "Phase 4" -d "Add validation phase"

# Edit section in EROS validator
./.claude/skills/skill-editor/ralph_skill_edit.sh edit -f .claude/skills/eros-schedule-validator/REFERENCE/validation.md -s "Hard Gates" -d "Add new gate documentation"

# Refactor across EROS skills
./.claude/skills/skill-editor/ralph_skill_edit.sh refactor -f .claude/skills/eros-schedule-generator/SKILL.md -s "MCP Tools" -r ".claude/skills/eros-schedule-validator/SKILL.md" -d "Update tool references"

# Delete obsolete section
./.claude/skills/skill-editor/ralph_skill_edit.sh delete -f .claude/skills/mcp-refactor/SKILL.md -s "Legacy Pattern" -d "Remove deprecated"
```

---

## File Structure

```
.claude/skills/skill-editor/
├── SKILL.md                    # This file
├── PROMPT_skill_edit.md        # Main Ralph loop prompt
├── RALPH_SKILL_EDIT_INLINE.md  # Copy-paste loop templates
├── ralph_skill_edit.sh         # CLI wrapper script
└── SIGNS.md                    # Accumulated failure patterns (26 signs)
```

---

## Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `EDIT_TYPE` | Yes | Type of change | `add`, `edit`, `refactor`, `delete` |
| `TARGET_FILE` | Yes | Primary file to modify | `.claude/skills/eros-schedule-generator/SKILL.md` |
| `SECTION_NAME` | Yes | Section being worked on | `"Phase 3: Execution"` |
| `DESCRIPTION` | No | Brief description | `"Add new validation step"` |
| `RELATED_FILES` | No | Other files to update | `".claude/skills/eros-schedule-validator/SKILL.md"` |
| `REFERENCE_PATTERN` | No | Existing pattern to follow | `.claude/skills/mcp-refactor/SKILL.md` |

---

## What Each Edit Type Does

### ADD
- Identifies correct insertion point
- Matches existing header hierarchy
- Follows patterns from rest of file
- Updates any TOC/index sections

### EDIT
- Locates exact section
- Preserves structure, updates content
- Maintains formatting consistency
- Updates version/date if present

### REFACTOR
- Finds all instances of pattern
- Creates consistent replacement
- Updates ALL occurrences across files
- Maintains cross-references

### DELETE
- Removes target section
- Finds and removes all references
- Updates indexes/TOCs
- Verifies no orphaned links

---

## Success Criteria

Every edit must pass:

| Check | Description |
|-------|-------------|
| File exists | Target file is valid markdown |
| No placeholders | Zero `[TBD]`, `[TODO]`, `...` |
| No broken links | All internal links resolve |
| Consistent format | Matches rest of file |
| Valid YAML | Frontmatter parses correctly |
| Code blocks typed | All ``` have language (```bash) |
| AGENTS.md ≤ 60 | Line limit respected |
| Prompt structure | Has SUCCESS CRITERIA, BACKPRESSURE, SIGNS |

---

## Common Patterns

### Adding a New Prompt File

```bash
./.claude/skills/skill-editor/ralph_skill_edit.sh add \
  -f .claude/skills/new_skill/PROMPT_new_phase.md \
  -s "Full File" \
  -d "Create new phase prompt" \
  -p .claude/skills/mcp-refactor/SKILL.md  # Pattern to follow
```

### Adding Signs After Failure

```bash
./.claude/skills/skill-editor/ralph_skill_edit.sh edit \
  -f .claude/skills/skill-editor/PROMPT_skill_edit.md \
  -s "SIGNS" \
  -d "Add sign for [failure pattern observed]"
```

### Updating Token Budgets Across Files

```bash
./.claude/skills/skill-editor/ralph_skill_edit.sh refactor \
  -f .claude/skills/eros-schedule-generator/SKILL.md \
  -s "Token Budget" \
  -r ".claude/skills/eros-schedule-validator/SKILL.md" \
  -d "Update token limits from 2500 to 3000"
```

### Adding a New Skill to Package

```bash
# Step 1: Create the skill file
./.claude/skills/skill-editor/ralph_skill_edit.sh add \
  -f .claude/skills/new_skill/SKILL.md \
  -s "Full File" \
  -d "Create new skill" \
  -p .claude/skills/mcp-refactor/SKILL.md

# Step 2: Add to main index
./.claude/skills/skill-editor/ralph_skill_edit.sh edit \
  -f CLAUDE.md \
  -s "Available Skills" \
  -d "Add new_skill to index"
```

---

## Iteration Recommendations

| Edit Type | Typical Iterations | Max Setting |
|-----------|-------------------|-------------|
| Simple add | 2-4 | 8 |
| Section edit | 3-6 | 12 |
| Multi-file refactor | 5-10 | 15 |
| Delete with cleanup | 2-5 | 8 |

---

## Recovery

```bash
# Cancel running loop
/cancel-ralph

# If edit went wrong
git checkout -- $TARGET_FILE

# If multiple files affected
git checkout -- .

# View what changed
git diff
```

---

## Completion Promise

Loop outputs `SKILL_EDIT_COMPLETE` when:
- All success criteria pass
- All backpressure checks pass
- Changes are verified consistent

If blocked, outputs `SKILL_EDIT_BLOCKED` with reason.
