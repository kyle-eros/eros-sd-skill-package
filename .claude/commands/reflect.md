---
name: reflect
description: Analyze session and update LEARNINGS.md with validated patterns.
version: 1.0.0
argument-hint: [on|off|status|history] or no args to run
---

# Reflect Command

Extract learnings from Claude Code session and consolidate into EROS skill documentation.

## Arguments

| Arg | Description |
|-----|-------------|
| (none) | Run reflection on current session |
| `on` | Enable auto-reflect on session end |
| `off` | Disable auto-reflect |
| `status` | Show settings and stats |
| `history` | Show recent reflection commits |

## Signal Detection

### HIGH (MUST follow)
- **Validation rejections**: VAULT_VIOLATION, AVOID_TIER_VIOLATION, PAGE_TYPE_VIOLATION
- **User corrections**: "No, do X instead", "That's wrong", "Actually,"
- **Regeneration**: Schedule rejected then regenerated with different params

### MEDIUM (SHOULD follow)
- **User approvals**: "That's right", "Perfect", "Good job", "Looks good"
- **Quality threshold**: ValidationCertificate.quality_score >= 85
- **Schedule accepted**: save_schedule without prior rejection

### LOW (MAY inform)
- **Pattern mentions**: Unconfirmed optimization discussions
- **Speculation**: "might work", "could try", "worth testing"
- **Emerging trends**: Sample size < 10

## Domain Categories

| Domain | Promotion Target |
|--------|------------------|
| Caption Selection | SKILL.md |
| Timing Rules | REFERENCE/timing.md |
| Pricing Strategy | REFERENCE/pricing.md |
| Volume Distribution | SKILL.md |
| Followup Rules | REFERENCE/followups.md |

## 5-Step Workflow

### Step 1: Scan
```
Scanning session... Found: 2 HIGH, 3 MEDIUM, 1 LOW signals.
Continue? [Y/n]
```

### Step 2: Extract
Categorize by domain (caption, timing, pricing, volume, creator-specific).

### Step 3: Format
```markdown
### [YYYY-MM-DD] Title
**Pattern**: What happened | **Correction**: What to do instead
**Source**: validation | **Violation Code**: CODE
**Applies To**: all | tier:TIER | creator:ID
```

### Step 4: Preview
```
Proposed additions to LEARNINGS.md:
+ ### [2026-01-06] AVOID tier check before caption selection
+   **Pattern**: Selected AVOID-tier content
+   **Correction**: Check get_content_type_rankings first
Apply? [Y/n]
```

### Step 5: Commit
```bash
git commit -m "chore(eros): reflect - N learnings added

HIGH: N corrections, MEDIUM: N patterns, LOW: N observations"
```

## Toggle Commands

**`/reflect on`** - Enable auto-reflect
```json
{ "auto_reflect": true, "min_signals": 1, "require_confirmation": true }
```

**`/reflect off`** - Disable auto-reflect

**`/reflect status`** - Show settings + LEARNINGS.md stats

**`/reflect history`** - List recent commits: `git log --oneline --grep="reflect"`

## Promotion Rules

| Transition | Criteria |
|------------|----------|
| LOW -> MEDIUM | Sample >= 10 AND 80% consistent |
| MEDIUM -> HIGH | User confirms OR 5+ validation successes |

## Git Commit Format

```
chore(eros): reflect - {count} learnings added

HIGH: {n} corrections
MEDIUM: {n} patterns
LOW: {n} observations
```

## Files Modified

- `LEARNINGS.md` - Learning entries
- `.claude/settings/reflect.json` - Toggle settings

$ARGUMENTS
