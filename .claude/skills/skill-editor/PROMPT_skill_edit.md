# PROMPT_skill_edit.md — Universal Skill Package Editor

## IDENTITY
**Purpose:** Add, edit, or refactor sections within EROS skill packages and other Claude Code multi-agent skill packages
**Output:** Modified skill files with verified consistency
**Max Iterations:** 12
**Domain:** EROS Schedule Generation Pipeline (primary), Generic Skill Packages (secondary)

---

## PARAMETERS (set before running)

```bash
# Required
export EDIT_TYPE="add|edit|refactor|delete"       # What kind of change
export TARGET_FILE="path/to/file.md"               # Primary file to modify
export SECTION_NAME="Section Name"                 # Section being worked on
export DESCRIPTION="Brief description of change"  # What you're doing

# Optional
export RELATED_FILES="file1.md,file2.md"          # Other files to update
export REFERENCE_PATTERN="existing/pattern.md"    # Pattern to follow
```

---

## SUCCESS CRITERIA (ALL must pass)

### Universal Criteria (always apply)
1. Target file exists and is valid markdown
2. No broken internal references (all `[links]` resolve)
3. No placeholder text: `[TBD]`, `[TODO]`, `[PLACEHOLDER]`, `...`
4. Consistent formatting with rest of file
5. YAML frontmatter valid (if present)
6. Code blocks have language specifiers

### Add/Edit Criteria
7. New content follows existing patterns in file
8. Section headers use correct hierarchy (##, ###, etc.)
9. If adding to AGENTS.md: total lines ≤ 60
10. If adding prompts: has SUCCESS CRITERIA, BACKPRESSURE, SIGNS sections

### Refactor Criteria
11. All references to old patterns updated
12. Related files updated for consistency
13. No orphaned sections

### Delete Criteria
14. All references to deleted content removed
15. No broken cross-references remain

### EROS Skill Criteria (when TARGET_FILE is under .claude/skills/eros-*)
16. If modifying hard gate definitions: verify against `docs/DOMAIN_KNOWLEDGE.md` Section 3 (5 gates: Vault, AVOID, Page Type, Diversity, Flyer)
17. If modifying MCP tool references: verify tool exists in CLAUDE.md MCP section (16 must-keep tools)
18. If modifying send type constraints: verify against `get_send_types_constraints()` response
19. If modifying volume/pricing: numbers match DOMAIN_KNOWLEDGE.md Section 2/4 (tiers, $5-$50 bounds)
20. If modifying ValidationCertificate: schema matches v3.0 spec in DOMAIN_KNOWLEDGE.md Section 9
21. CreatorContext fields: must match 10 top-level field schema from generator SKILL.md
22. No hardcoded values that contradict database state (check LEARNINGS.md HIGH confidence items)

---

## BACKPRESSURE CHECKS

```bash
# 1. File validity
test -f "$TARGET_FILE" && echo "✅ File exists" || echo "❌ File missing"

# 2. No placeholders
grep -c "\[TBD\]\|\[TODO\]\|\[PLACEHOLDER\]\|\.\.\." "$TARGET_FILE"
# Must return 0

# 3. No broken markdown links (internal)
grep -oP '\[.*?\]\((?!http)[^)]+\)' "$TARGET_FILE" | while read link; do
  target=$(echo "$link" | grep -oP '\(.*?\)' | tr -d '()')
  test -f "$target" && echo "✅ $target" || echo "❌ BROKEN: $target"
done

# 4. YAML frontmatter valid (if present)
head -1 "$TARGET_FILE" | grep -q "^---" && {
  sed -n '1,/^---$/p' "$TARGET_FILE" | tail -n +2 | head -n -1 | python3 -c "import yaml, sys; yaml.safe_load(sys.stdin)" && echo "✅ YAML valid" || echo "❌ YAML invalid"
}

# 5. Code blocks have language
grep -P '```$' "$TARGET_FILE" | wc -l
# Should return 0 (all ``` should have language like ```bash)

# 6. AGENTS.md line count (if applicable)
[[ "$TARGET_FILE" == *"AGENTS.md" ]] && {
  wc -l < "$TARGET_FILE" | xargs test 60 -ge && echo "✅ AGENTS.md ≤ 60 lines" || echo "❌ AGENTS.md too long"
}

# 7. Prompt structure (if adding/editing prompts)
[[ "$TARGET_FILE" == *"PROMPT"* ]] && {
  grep -q "## SUCCESS CRITERIA" "$TARGET_FILE" && echo "✅ Has SUCCESS CRITERIA" || echo "❌ Missing SUCCESS CRITERIA"
  grep -q "## BACKPRESSURE" "$TARGET_FILE" && echo "✅ Has BACKPRESSURE" || echo "❌ Missing BACKPRESSURE"
  grep -q "## SIGNS" "$TARGET_FILE" && echo "✅ Has SIGNS" || echo "❌ Missing SIGNS"
}

# 8. EROS Hard Gate Consistency (if editing eros-* skills)
[[ "$TARGET_FILE" == *"eros-"* ]] && {
  echo "=== EROS Hard Gate Check ==="
  # Verify hard gate references match DOMAIN_KNOWLEDGE.md
  grep -oP 'Gate \d:' "$TARGET_FILE" 2>/dev/null | while read gate; do
    grep -q "$gate" docs/DOMAIN_KNOWLEDGE.md 2>/dev/null && echo "✅ $gate verified" || echo "⚠️ $gate - verify in DOMAIN_KNOWLEDGE.md"
  done
}

# 9. MCP Tool Reference Check (if editing eros-* skills)
[[ "$TARGET_FILE" == *"eros-"* ]] && {
  echo "=== MCP Tool Reference Check ==="
  grep -oP 'mcp__eros-db__\w+' "$TARGET_FILE" 2>/dev/null | sort -u | while read tool; do
    grep -q "$tool" CLAUDE.md 2>/dev/null && echo "✅ $tool documented" || echo "⚠️ $tool - verify exists"
  done
}

# 10. LEARNINGS.md HIGH confidence check
[[ "$TARGET_FILE" == *"eros-"* ]] && {
  echo "=== LEARNINGS.md HIGH Confidence Review ==="
  # Extract HIGH learnings that might conflict with changes
  grep -A5 "## HIGH Confidence" LEARNINGS.md 2>/dev/null | head -20 || echo "⚠️ LEARNINGS.md not found - verify manually"
  echo "⚠️ Verify changes don't contradict HIGH confidence learnings"
}
```

---

## PROCESS (each iteration)

### Step 1: Context Analysis
```
Read: $TARGET_FILE (full file to understand structure)
Read: $REFERENCE_PATTERN (if provided, for pattern matching)
Read: $RELATED_FILES (if provided, for consistency check)
```

**For EROS skills, also read:**
- `LEARNINGS.md` HIGH confidence section
- `docs/DOMAIN_KNOWLEDGE.md` relevant section

**Extract:**
- Current file structure (headers, sections)
- Formatting conventions used
- Existing patterns to follow
- Cross-references to maintain

### Step 2: Plan Changes
Before editing, document:
```markdown
## CHANGE PLAN
**Type:** $EDIT_TYPE
**Target:** $TARGET_FILE
**Section:** $SECTION_NAME

**Current State:**
[describe what exists now]

**Desired State:**
[describe what should exist after]

**Files Affected:**
- $TARGET_FILE (primary)
- [related files if any]

**Pattern Source:**
[what existing pattern to follow]

**EROS Constraints (if applicable):**
- Hard gates affected: [none/list]
- MCP tools affected: [none/list]
- Schema changes: [none/list]
```

### Step 3: Execute Changes

**For ADD:**
1. Identify insertion point (after which section?)
2. Match header hierarchy of surrounding content
3. Write new section following existing patterns
4. Update any table of contents / index sections

**For EDIT:**
1. Locate exact section to modify
2. Preserve header and structure
3. Update content while maintaining formatting
4. Update version/date if present in file header

**For REFACTOR:**
1. Identify all instances of pattern to change
2. Create consistent replacement
3. Update ALL occurrences (grep to find them all)
4. Update related files for consistency

**For DELETE:**
1. Locate section to remove
2. Check for references TO this section
3. Remove section
4. Remove or update all references
5. Update any indexes/TOCs

### Step 4: Consistency Verification
```
# Check related files still reference correctly
for file in $RELATED_FILES; do
  grep -l "$SECTION_NAME" "$file" && echo "Reference found in $file"
done

# Verify internal structure
grep "^#" "$TARGET_FILE"  # Check header hierarchy makes sense
```

### Step 5: Run Backpressure Checks
Execute ALL checks from BACKPRESSURE CHECKS section.
ALL must pass.

### Step 6: Completion Check
If ALL success criteria pass → Output completion promise.

---

## SIGNS (do not repeat these failures)

### Structure
- DON'T add sections without checking header hierarchy first
- DON'T use `###` under `#` (skip levels) — maintain proper nesting
- DON'T create orphan sections with no parent context

### Content
- DON'T leave placeholder text — fill everything or mark with `<!-- TODO: ... -->`
- DON'T use vague language in prompts ("as needed", "if appropriate")
- DON'T add code blocks without language specifier (use ```bash not ```)

### Files
- DON'T edit AGENTS.md without checking line count after
- DON'T add prompts without SUCCESS CRITERIA, BACKPRESSURE, SIGNS sections
- DON'T create new files without adding to relevant index/SKILL.md

### Cross-References
- DON'T delete sections without removing all references
- DON'T rename sections without updating all references
- DON'T add internal links without verifying target exists

### Patterns
- DON'T invent new patterns when existing ones work
- DON'T break consistency with rest of file
- DON'T assume you know the pattern — read existing content first

### EROS Domain
- DON'T modify hard gate definitions without checking DOMAIN_KNOWLEDGE.md Section 3
- DON'T add/remove MCP tools without verification against 16 must-keep tools
- DON'T change ValidationCertificate schema without updating v3.0 references everywhere
- DON'T modify CreatorContext fields — they're immutable 10-field structure across pipeline
- DON'T add MCP tool calls without verifying tool exists (test with get_active_creators)
- DON'T contradict HIGH confidence learnings in LEARNINGS.md
- DON'T hardcode pricing/volume bounds without database verification ($5-$50, 5 tiers)

---

## OUTPUT TEMPLATES

### Change Summary
```markdown
═══════════════════════════════════════════════════════════════
SKILL EDIT COMPLETE
═══════════════════════════════════════════════════════════════

**Type:** $EDIT_TYPE
**Target:** $TARGET_FILE
**Section:** $SECTION_NAME

**Changes Made:**
- [specific change 1]
- [specific change 2]

**Files Modified:**
- $TARGET_FILE ✅
- [related files] ✅

**Verification:**
- Placeholders: 0 ✅
- Broken links: 0 ✅
- Format consistent: ✅
- [type-specific checks]: ✅
- [EROS checks if applicable]: ✅

═══════════════════════════════════════════════════════════════
```

### Blocked Report
```markdown
═══════════════════════════════════════════════════════════════
SKILL EDIT BLOCKED
═══════════════════════════════════════════════════════════════

**Reason:** [why blocked]
**Details:** [specific issue]

**To Resolve:**
[what human needs to provide/decide]

═══════════════════════════════════════════════════════════════
```

---

## COMPLETION

When ALL success criteria verified and ALL backpressure checks pass, output exactly:

<promise>SKILL_EDIT_COMPLETE</promise>

Then output the Change Summary template.

---

## BLOCKED OUTPUT

If cannot complete, output:

<blocked>SKILL_EDIT_BLOCKED</blocked>

Then output the Blocked Report template.
DO NOT output completion promise if blocked.
