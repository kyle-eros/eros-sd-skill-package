# RALPH_SKILL_EDIT_INLINE.md
# Copy-paste ready Ralph loops for skill package editing

---

## ADD Section

```bash
/ralph-loop "
# ADD SECTION TO SKILL FILE

## TASK
Add new section to TARGET_FILE.

## PARAMETERS
- TARGET_FILE: [YOUR_FILE_PATH]
- SECTION_NAME: [YOUR_SECTION_NAME]
- INSERT_AFTER: [SECTION_TO_INSERT_AFTER]
- DESCRIPTION: [WHAT_THIS_SECTION_DOES]

## SUCCESS CRITERIA
1. Section exists with correct header level
2. Follows patterns from rest of file
3. No placeholders: grep -c '\[TBD\]\|\[TODO\]' TARGET_FILE = 0
4. Code blocks have language specifiers
5. If AGENTS.md: wc -l ≤ 60
6. If PROMPT_*.md: has SUCCESS CRITERIA, BACKPRESSURE, SIGNS

## PROCESS
1. Read TARGET_FILE to understand structure and patterns
2. Find INSERT_AFTER section
3. Determine correct header level (match surrounding)
4. Write new section following existing patterns
5. Update any TOC/index if present
6. Run all SUCCESS CRITERIA checks
7. If all pass → output completion

## SIGNS
- DON'T skip header levels (no ### under #)
- DON'T leave placeholders
- DON'T invent new patterns — follow existing
- DON'T forget code block language specifiers

## COMPLETION
When all criteria pass: <promise>SKILL_EDIT_COMPLETE</promise>
" --max-iterations 10 --completion-promise "SKILL_EDIT_COMPLETE"
```

---

## EDIT Section

```bash
/ralph-loop "
# EDIT EXISTING SECTION

## TASK
Modify existing section in TARGET_FILE.

## PARAMETERS
- TARGET_FILE: [YOUR_FILE_PATH]
- SECTION_NAME: [SECTION_TO_EDIT]
- CHANGES: [WHAT_TO_CHANGE]

## SUCCESS CRITERIA
1. Section updated as described
2. Structure preserved (same header level)
3. Formatting matches rest of file
4. No placeholders left
5. All internal links still work
6. Version/date updated if file has header

## PROCESS
1. Read TARGET_FILE completely
2. Locate SECTION_NAME exactly
3. Understand current content and structure
4. Make ONLY the requested changes
5. Preserve all formatting conventions
6. Verify no broken references
7. Run all SUCCESS CRITERIA checks
8. If all pass → output completion

## SIGNS
- DON'T change more than requested
- DON'T break formatting consistency
- DON'T leave partial edits
- DON'T forget to update version/date

## COMPLETION
When all criteria pass: <promise>SKILL_EDIT_COMPLETE</promise>
" --max-iterations 10 --completion-promise "SKILL_EDIT_COMPLETE"
```

---

## REFACTOR Across Files

```bash
/ralph-loop "
# REFACTOR PATTERN ACROSS FILES

## TASK
Update pattern consistently across multiple files.

## PARAMETERS
- TARGET_FILE: [PRIMARY_FILE]
- SECTION_NAME: [PATTERN_TO_CHANGE]
- RELATED_FILES: [FILE1, FILE2, ...]
- OLD_PATTERN: [WHAT_EXISTS_NOW]
- NEW_PATTERN: [WHAT_IT_SHOULD_BE]

## SUCCESS CRITERIA
1. Pattern updated in TARGET_FILE
2. Pattern updated in ALL RELATED_FILES
3. No instances of OLD_PATTERN remain: grep -r 'OLD_PATTERN' . = 0
4. All cross-references still valid
5. Formatting consistent across all files

## PROCESS
1. grep -r 'OLD_PATTERN' to find ALL occurrences
2. List every file that needs updating
3. Update TARGET_FILE first
4. Update each RELATED_FILE
5. Verify OLD_PATTERN no longer exists anywhere
6. Check all cross-references work
7. Run all SUCCESS CRITERIA checks
8. If all pass → output completion

## SIGNS
- DON'T miss any occurrences — grep ALL files
- DON'T update partially — all or nothing
- DON'T break cross-references
- DON'T forget hidden files or subdirectories

## COMPLETION
When all criteria pass: <promise>SKILL_EDIT_COMPLETE</promise>
" --max-iterations 15 --completion-promise "SKILL_EDIT_COMPLETE"
```

---

## DELETE Section

```bash
/ralph-loop "
# DELETE SECTION WITH CLEANUP

## TASK
Remove section and all references to it.

## PARAMETERS
- TARGET_FILE: [YOUR_FILE_PATH]
- SECTION_NAME: [SECTION_TO_DELETE]
- RELATED_FILES: [FILES_THAT_MIGHT_REFERENCE]

## SUCCESS CRITERIA
1. Section removed from TARGET_FILE
2. All references to section removed
3. No broken internal links remain
4. TOC/index updated if present
5. File structure still valid

## PROCESS
1. grep -r 'SECTION_NAME' to find ALL references
2. List every file that references this section
3. Remove all references first
4. Remove the section itself
5. Update any TOC/index
6. Verify no broken links: grep for internal links, test each
7. Run all SUCCESS CRITERIA checks
8. If all pass → output completion

## SIGNS
- DON'T delete before removing references
- DON'T leave orphaned links
- DON'T forget TOC/index updates
- DON'T miss references in subdirectories

## COMPLETION
When all criteria pass: <promise>SKILL_EDIT_COMPLETE</promise>
" --max-iterations 8 --completion-promise "SKILL_EDIT_COMPLETE"
```

---

## ADD New Prompt File

```bash
/ralph-loop "
# CREATE NEW PROMPT FILE

## TASK
Create new PROMPT_[name].md following established patterns.

## PARAMETERS
- NEW_FILE: .claude/skills/[skill]/PROMPT_[NAME].md
- REFERENCE: .claude/skills/mcp-refactor/SKILL.md
- PURPOSE: [WHAT_THIS_PROMPT_DOES]

## SUCCESS CRITERIA
1. File created at NEW_FILE
2. Has ## IDENTITY section
3. Has ## SUCCESS CRITERIA with measurable items
4. Has ## BACKPRESSURE CHECKS with bash commands
5. Has ## PROCESS with numbered steps
6. Has ## SIGNS with failure patterns
7. Has ## COMPLETION with promise tag
8. Follows format from REFERENCE exactly
9. No placeholders

## PROCESS
1. Read REFERENCE file completely
2. Understand its structure and patterns
3. Create NEW_FILE with same structure
4. Fill all sections with PURPOSE-specific content
5. Ensure all success criteria are measurable
6. Ensure backpressure checks are executable bash
7. Include at least 5 relevant signs
8. Run all SUCCESS CRITERIA checks
9. If all pass → output completion

## SIGNS
- DON'T skip required sections
- DON'T use vague success criteria
- DON'T make backpressure checks non-executable
- DON'T forget the completion promise format

## COMPLETION
When all criteria pass: <promise>SKILL_EDIT_COMPLETE</promise>
" --max-iterations 12 --completion-promise "SKILL_EDIT_COMPLETE"
```

---

## Quick Add Sign After Failure

```bash
/ralph-loop "
# ADD SIGN TO PROMPT

## TASK
Add new failure pattern sign to existing prompt.

## PARAMETERS
- TARGET_FILE: .claude/skills/[skill]/PROMPT_[NAME].md
- SIGN_ID: SIGN-[PREFIX][NUMBER]
- TRIGGER: [What caused Claude to fail]
- SYMPTOM: [Observable result]
- SIGN_TEXT: [Instruction to prevent]

## SUCCESS CRITERIA
1. Sign added under ## SIGNS section
2. Follows existing sign format exactly
3. Sign is actionable (starts with verb)
4. No duplicate sign IDs

## PROCESS
1. Read TARGET_FILE
2. Find ## SIGNS section
3. Count existing signs for next number
4. Add new sign in format:
   - DON'T [thing to avoid] — [why]
5. Verify format matches existing signs
6. Check for duplicates
7. If all pass → output completion

## COMPLETION
When all criteria pass: <promise>SKILL_EDIT_COMPLETE</promise>
" --max-iterations 6 --completion-promise "SKILL_EDIT_COMPLETE"
```

---

## EROS Skill Edit (Domain-Specific)

```bash
/ralph-loop "
# EDIT EROS PIPELINE SKILL

## TASK
Modify EROS schedule generator/validator skill with domain awareness.

## PARAMETERS
- TARGET_FILE: .claude/skills/eros-schedule-[generator|validator]/SKILL.md
- SECTION_NAME: [SECTION_TO_EDIT]
- CHANGES: [WHAT_TO_CHANGE]

## SUCCESS CRITERIA
1. Section updated as described
2. Hard gates preserved (Gate 1-5: Vault, AVOID, Page Type, Diversity, Flyer)
3. MCP tool references valid (verify in CLAUDE.md - 16 must-keep tools)
4. No contradictions with DOMAIN_KNOWLEDGE.md
5. No contradictions with HIGH confidence LEARNINGS.md
6. ValidationCertificate v3.0 schema preserved
7. CreatorContext 10-field schema preserved
8. No broken internal references
9. No placeholders left

## PROCESS
1. Read LEARNINGS.md HIGH confidence section
2. Read TARGET_FILE completely
3. Read docs/DOMAIN_KNOWLEDGE.md relevant section
4. Locate SECTION_NAME exactly
5. Verify changes don't contradict hard gates
6. Make changes preserving domain constraints
7. Verify MCP tool references with grep against CLAUDE.md
8. Run all SUCCESS CRITERIA checks
9. If all pass → output completion

## SIGNS
- DON'T modify hard gate definitions without DOMAIN_KNOWLEDGE.md check
- DON'T add/remove MCP tools without verification
- DON'T change ValidationCertificate schema
- DON'T modify CreatorContext structure
- DON'T contradict HIGH confidence learnings
- DON'T hardcode pricing/volume without verification ($5-$50, 5 tiers)

## COMPLETION
When all criteria pass: <promise>SKILL_EDIT_COMPLETE</promise>
" --max-iterations 12 --completion-promise "SKILL_EDIT_COMPLETE"
```

---

## USAGE TIPS

### Replace Parameters Before Running
Before pasting, replace all `[BRACKETED_VALUES]`:
```bash
# Example: Adding section to EROS generator
/ralph-loop "
...
- TARGET_FILE: .claude/skills/eros-schedule-generator/SKILL.md      # ← replaced
- SECTION_NAME: Phase 4: Validation                                  # ← replaced
- INSERT_AFTER: Phase 3: Execution                                   # ← replaced
- DESCRIPTION: Add post-execution validation                         # ← replaced
...
" --max-iterations 10 --completion-promise "SKILL_EDIT_COMPLETE"
```

### Adjust Iterations
| Complexity | Iterations |
|------------|------------|
| Simple add/edit | 6-8 |
| Multi-section | 10-12 |
| Multi-file refactor | 12-15 |
| EROS skill edit | 10-12 |

### Cancel If Needed
```bash
/cancel-ralph
```

### Recovery
```bash
git checkout -- [file]  # Undo changes
git diff               # See what changed
```
