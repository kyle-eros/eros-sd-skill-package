# SIGNS.md — Skill Editor Failure Patterns

---

## Structure Failures

### SIGN-SE01: Header Hierarchy Skip
**Trigger:** Added `###` section directly under `#` (skipped `##`)
**Symptom:** Broken document structure, rendering issues
**Sign:** "ALWAYS check existing header hierarchy before adding — maintain proper nesting"
**Added:** 2026-01-12

### SIGN-SE02: Orphan Section
**Trigger:** Added section with no logical parent or context
**Symptom:** Section makes no sense in isolation
**Sign:** "Every new section must have clear relationship to surrounding content"
**Added:** 2026-01-12

### SIGN-SE03: TOC Neglect
**Trigger:** Added section but didn't update table of contents
**Symptom:** TOC out of sync with actual content
**Sign:** "If file has TOC/index, update it when adding/removing sections"
**Added:** 2026-01-12

---

## Content Failures

### SIGN-SE04: Placeholder Left Behind
**Trigger:** Output "done" while placeholders remained
**Symptom:** Backpressure check failed on `[TBD]` grep
**Sign:** "NEVER complete until grep for placeholders returns 0"
**Added:** 2026-01-12

### SIGN-SE05: Untyped Code Block
**Trigger:** Used ``` without language specifier
**Symptom:** No syntax highlighting, looks unprofessional
**Sign:** "ALWAYS specify language: ```bash, ```python, ```markdown, etc."
**Added:** 2026-01-12

### SIGN-SE06: Vague Prompt Language
**Trigger:** Used "as needed" or "if appropriate" in prompt file
**Symptom:** Prompt can't converge — no measurable completion
**Sign:** "Prompts require EXPLICIT, MEASURABLE instructions — no vague language"
**Added:** 2026-01-12

---

## File Failures

### SIGN-SE07: AGENTS.md Overflow
**Trigger:** Added to AGENTS.md without checking line count
**Symptom:** File exceeded 60 lines, too much for context loading
**Sign:** "ALWAYS check `wc -l AGENTS.md` after edits — must be ≤ 60"
**Added:** 2026-01-12

### SIGN-SE08: Missing Prompt Sections
**Trigger:** Created prompt without required structure
**Symptom:** Prompt missing SUCCESS CRITERIA, BACKPRESSURE, or SIGNS
**Sign:** "Every PROMPT_*.md MUST have: SUCCESS CRITERIA, BACKPRESSURE, SIGNS sections"
**Added:** 2026-01-12

### SIGN-SE09: New File Not Indexed
**Trigger:** Created new skill file but didn't add to main index
**Symptom:** Skill invisible, not discoverable
**Sign:** "When creating new files, add entry to parent SKILL.md or index"
**Added:** 2026-01-12

---

## Reference Failures

### SIGN-SE10: Broken Internal Link
**Trigger:** Added link to non-existent file
**Symptom:** `[text](path)` leads nowhere
**Sign:** "Before adding internal links, verify target exists with `test -f`"
**Added:** 2026-01-12

### SIGN-SE11: Orphaned References After Delete
**Trigger:** Deleted section but left references pointing to it
**Symptom:** Broken links, confusing references
**Sign:** "Before deleting, grep for section name across ALL related files"
**Added:** 2026-01-12

### SIGN-SE12: Rename Without Update
**Trigger:** Renamed section header but didn't update references
**Symptom:** References point to old name
**Sign:** "Renames require: 1) Find all references, 2) Update all, 3) Then rename"
**Added:** 2026-01-12

---

## Pattern Failures

### SIGN-SE13: Invented New Pattern
**Trigger:** Created new format instead of following existing
**Symptom:** Inconsistent with rest of file
**Sign:** "Read existing content FIRST — follow established patterns, don't invent"
**Added:** 2026-01-12

### SIGN-SE14: Assumed Pattern Without Reading
**Trigger:** Wrote content without checking existing style
**Symptom:** Format mismatch, inconsistent tables/lists/structure
**Sign:** "Always READ target file completely before making changes"
**Added:** 2026-01-12

### SIGN-SE15: Format Inconsistency
**Trigger:** Used different table style, list format, or code style
**Symptom:** File looks patched together
**Sign:** "Match EXACT formatting: same table alignment, same list style, same code block format"
**Added:** 2026-01-12

---

## Process Failures

### SIGN-SE16: Premature Completion
**Trigger:** Output completion promise before all checks passed
**Symptom:** Loop terminated with failing backpressure
**Sign:** "Run ALL backpressure checks, verify ALL pass, THEN output promise"
**Added:** 2026-01-12

### SIGN-SE17: No Change Plan
**Trigger:** Started editing without documenting plan
**Symptom:** Unclear what was supposed to change, hard to verify
**Sign:** "Always write CHANGE PLAN before making edits"
**Added:** 2026-01-12

### SIGN-SE18: Scope Creep
**Trigger:** Made additional "improvements" beyond requested change
**Symptom:** Unexpected modifications, hard to review
**Sign:** "Only change what was requested — no bonus edits"
**Added:** 2026-01-12

---

## EROS Domain Failures

### SIGN-SE19: Hard Gate Contradiction
**Trigger:** Modified hard gate definition that contradicts DOMAIN_KNOWLEDGE.md Section 3
**Symptom:** Pipeline rejects schedules that should pass, or accepts invalid ones
**Sign:** "Before modifying any Gate 1-5 definition (Vault, AVOID, Page Type, Diversity, Flyer), verify exact wording matches docs/DOMAIN_KNOWLEDGE.md Section 3"
**Added:** 2026-01-13

### SIGN-SE20: MCP Tool Reference Invalid
**Trigger:** Added reference to MCP tool that doesn't exist in the 16 must-keep tools
**Symptom:** Pipeline fails with "tool not found" or similar
**Sign:** "Before adding MCP tool reference, verify tool exists by checking CLAUDE.md MCP section or DOMAIN_KNOWLEDGE.md Section 11"
**Added:** 2026-01-13

### SIGN-SE21: ValidationCertificate Schema Drift
**Trigger:** Modified ValidationCertificate field names or structure
**Symptom:** save_schedule rejects valid schedules, or accepts invalid ones
**Sign:** "ValidationCertificate is v3.0 schema — any changes require updating ALL references in validator, generator, and DOMAIN_KNOWLEDGE.md Section 9 simultaneously"
**Added:** 2026-01-13

### SIGN-SE22: CreatorContext Mutation Attempt
**Trigger:** Added code that attempts to modify CreatorContext fields
**Symptom:** Pipeline corruption, inconsistent state between phases
**Sign:** "CreatorContext has 10 top-level fields and is IMMUTABLE — generator/validator receive it read-only from preflight. NEVER add code that modifies context fields."
**Added:** 2026-01-13

### SIGN-SE23: HIGH Confidence Learning Contradiction
**Trigger:** Made change that contradicts HIGH confidence learning in LEARNINGS.md
**Symptom:** Repeated failures that were previously fixed
**Sign:** "Before editing EROS skills, read LEARNINGS.md HIGH confidence section. These are corrections from actual failures — do not contradict them."
**Added:** 2026-01-13

### SIGN-SE24: Send Type Constraint Mismatch
**Trigger:** Hardcoded send type constraint that differs from database (Gate 3: Page Type Restrictions)
**Symptom:** Schedules using valid send types get rejected, or invalid ones pass
**Sign:** "Send type constraints (daily max, min gap, page type) are defined in database. Verify with get_send_types_constraints() before hardcoding values. Relates to Gate 3."
**Added:** 2026-01-13

### SIGN-SE25: Pricing/Volume Bound Mismatch
**Trigger:** Hardcoded pricing floor/ceiling or volume ranges that differ from DOMAIN_KNOWLEDGE.md Section 2/4
**Symptom:** Valid prices rejected, or invalid prices accepted
**Sign:** "Pricing bounds ($5-$50) and volume tier ranges (5 tiers) are defined in DOMAIN_KNOWLEDGE.md Section 2/4. Verify before hardcoding."
**Added:** 2026-01-13

### SIGN-SE26: Pipeline Phase Boundary Violation
**Trigger:** Added logic that blurs phase boundaries (e.g., generator doing validation, or gate logic relates to Gate 4: Diversity or Gate 5: Flyer)
**Symptom:** Phase responsibilities confused, harder to debug failures
**Sign:** "Pipeline phases have strict responsibilities: Preflight=build context, Generator=create items, Validator=verify gates (Gate 1-5). Do not cross boundaries."
**Added:** 2026-01-13

---

## Adding New Signs

### Generic Signs (SIGN-SE01 through SIGN-SE18)
For universal skill editing failures not specific to EROS.

### EROS Signs (SIGN-SE19 through SIGN-SE26)
For failures specific to EROS pipeline skills. Include:
- Which hard gate or constraint was violated (Gate 1-5)
- Which MCP tool or schema was affected
- Which DOMAIN_KNOWLEDGE.md section to reference

### Template for New Signs

When you observe a new failure, add it using this format:

```markdown
## SIGN-SE[NUMBER]: [Short Name]
Trigger: [What caused Claude to fail]
Symptom: [Observable result of failure]
Sign: "[Explicit instruction to prevent this]"
Added: [Date]
```

Then copy the **Sign** text to PROMPT_skill_edit.md under `## SIGNS`.
