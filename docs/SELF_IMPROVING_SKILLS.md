# EROS Self-Improving Skills Protocol

**Version**: 1.0.0
**Last Updated**: 2026-01-06
**Status**: Active (Phase 7)

---

## Overview

The EROS v1.0.0 self-improving skills protocol enables the schedule generator to learn from operational feedback and continuously improve its decision-making. Unlike static rule systems, this protocol captures validated patterns, corrections, and performance insights in version-controlled documentation that agents read at execution time.

### Key Principles

1. **Explicit over implicit**: All learnings are documented, not embedded in model weights
2. **Graduated confidence**: Learnings progress from LOW to MEDIUM to HIGH based on evidence
3. **Git-versioned**: Every learning is tracked with full rollback capability
4. **Agent-readable**: Learnings are Markdown files read at pipeline start

---

## Learning Sources

Three distinct sources feed the learning system, each with different latency and confidence characteristics.

### 1. Validation Feedback (Immediate)

Captured automatically by the `schedule-validator` agent after each pipeline run.

| Signal | Confidence | Trigger |
|--------|------------|---------|
| Hard gate violation (VAULT, AVOID, PAGE_TYPE) | HIGH | `certificate.status == "REJECTED"` |
| Quality score >= 85 | MEDIUM | `certificate.quality_score >= 85` |
| Quality score < 60 | LOW | `certificate.quality_score < 60` |

**Capture mechanism:**
```python
# In validator agent post-validation hook
if certificate.status == "REJECTED":
    feedback.capture(
        confidence="HIGH",
        source="validation",
        violation_code=certificate.violations[0].code,
        pattern=context.decisions_made,
        correction="Exclude {violation.content_type} from selection"
    )
```

### 2. User Feedback (Immediate)

Captured when users provide explicit corrections or approvals during interactive sessions.

| Signal | Confidence | Detection Pattern |
|--------|------------|-------------------|
| Explicit correction | HIGH | "No, do X instead", "That's wrong", "Actually," |
| Regeneration request | HIGH | Schedule rejected, regenerated with different params |
| Explicit approval | MEDIUM | "That's right", "Perfect", "Looks good" |
| Schedule accepted | MEDIUM | `save_schedule` called without prior rejection |

**Detection examples:**
```
HIGH: "No, alexia should never get tip_goal - she's a free page"
HIGH: "That price is too high, cap softcore at $12"
MEDIUM: "Perfect, that schedule looks exactly right"
```

### 3. Performance Feedback (Delayed 7-14 days)

Captured by scheduled analysis comparing schedule decisions to actual revenue/engagement outcomes.

| Signal | Confidence | Criteria | Latency |
|--------|------------|----------|---------|
| RPS above baseline | MEDIUM | schedule.rps > creator_median * 1.15 | 7 days |
| Conversion improvement | MEDIUM | schedule.conversion > baseline + 2% | 7 days |
| Revenue trend up | LOW | 3+ consecutive positive weeks | 14 days |
| Content type winner | MEDIUM | content_type RPS top 10% | 14 days |

**Capture mechanism:**
```python
# In weekly performance analysis job
for schedule in completed_schedules_7d_ago:
    actual_rps = get_schedule_rps(schedule.id)
    if actual_rps > creator_baseline * 1.15:
        feedback.capture(
            confidence="MEDIUM",
            source="performance",
            pattern=schedule.key_decisions,
            metric_impact=f"+{delta_pct}% RPS"
        )
```

---

## Confidence Levels Explained

### HIGH Confidence (MUST follow)

These are corrections, not suggestions. The agent violated a rule or the user explicitly corrected a mistake.

**Characteristics:**
- Single failure creates the learning
- No sample size requirement
- Applies immediately
- Cannot be overridden without explicit deprecation

**Examples:**
- Hard gate violation (vault, AVOID, page type)
- User explicit correction ("No, that's wrong because...")
- Regeneration after rejection

**Agent behavior:** HIGH learnings are mandatory constraints. The generator MUST NOT produce output that violates any HIGH learning.

### MEDIUM Confidence (SHOULD follow)

These are validated patterns that worked well. The agent should prefer these approaches.

**Characteristics:**
- Requires quality >= 85 OR user approval OR sample >= 10
- Can be overridden with justification
- Guides decision-making but allows flexibility

**Examples:**
- Quality 87 schedule used 28-minute followup delays
- User approved the lingerie-at-8pm pattern
- 15 schedules with softcore-first allocation outperformed

**Agent behavior:** MEDIUM learnings are strong preferences. The generator SHOULD follow these patterns unless context requires deviation.

### LOW Confidence (MAY inform)

These are observations worth tracking but not yet validated.

**Characteristics:**
- Sample size < 10
- No user confirmation
- Emerging trends to monitor
- Cannot drive hard decisions

**Examples:**
- New timing pattern observed 3 times
- Hypothesis about content ordering
- Single successful experiment

**Agent behavior:** LOW learnings provide context only. The generator MAY consider these but should not prioritize them over established rules.

---

## Reflection Workflow

The `/reflect` command consolidates session learnings into LEARNINGS.md through a 5-step workflow.

### Step 1: Scan

The system scans the current Claude Code session for learning signals.

```
$ /reflect

Scanning session... Found: 2 HIGH, 3 MEDIUM, 1 LOW signals.

HIGH:
  - AVOID_TIER_VIOLATION on content_type "feet"
  - User correction: "alexia is a free page"

MEDIUM:
  - Quality 89 schedule accepted
  - Quality 86 schedule accepted
  - User: "That timing looks perfect"

LOW:
  - Unconfirmed pattern: lingerie performs better at 7pm

Continue? [Y/n]
```

### Step 2: Extract

Signals are categorized by domain for targeted documentation updates.

| Domain | Examples | Target File |
|--------|----------|-------------|
| Caption Selection | Content type rankings, AVOID violations | LEARNINGS.md |
| Timing Rules | Dead zone violations, optimal hours | LEARNINGS.md |
| Pricing Strategy | Price cap corrections, tier pricing | LEARNINGS.md |
| Volume Distribution | Daily volume adjustments, DOW patterns | LEARNINGS.md |
| Creator-Specific | Individual creator constraints | LEARNINGS.md |

### Step 3: Format

Learnings are formatted using the standard template:

```markdown
### [2026-01-06] AVOID tier content_type "feet" for alexia
**Pattern**: Selected "feet" content for grace_bennett
**Issue**: "feet" is in AVOID tier for this creator
**Correction**: Always check get_content_type_rankings before caption selection
**Source**: validation | **Violation Code**: AVOID_TIER_VIOLATION
**Applies To**: creator:grace_bennett
```

### Step 4: Preview

Before writing, the system shows proposed changes for confirmation.

```
Proposed additions to LEARNINGS.md:

+ ### [2026-01-06] AVOID tier check for "feet" content
+   **Pattern**: Selected AVOID-tier content
+   **Correction**: Verify content_type not in avoid_types
+   **Source**: validation | **Violation Code**: AVOID_TIER_VIOLATION
+   **Applies To**: all

+ ### [2026-01-06] Free page cannot use tip_goal
+   **Pattern**: Assigned tip_goal to free page creator
+   **Correction**: Check page_type before retention sends
+   **Source**: user | **Applies To**: all

Apply? [Y/n]
```

### Step 5: Commit

Confirmed learnings are written to LEARNINGS.md and committed to Git.

```bash
git add LEARNINGS.md
git commit -m "chore(eros): reflect - 5 learnings added

HIGH: 2 corrections
MEDIUM: 3 patterns
LOW: 0 observations"
```

---

## Git Versioning Approach

All learnings are tracked in Git for auditability and rollback capability.

### Commit Format

```
chore(eros): reflect - {count} learnings added

HIGH: {n} corrections
MEDIUM: {n} patterns
LOW: {n} observations

[Optional body with learning titles]
```

### Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production learnings |
| `learning/*` | Experimental learnings (before promotion) |

### Viewing History

```bash
# Recent learning commits
git log --oneline --grep="reflect" -10

# Changes to LEARNINGS.md
git log -p LEARNINGS.md

# Diff between versions
git diff HEAD~5 LEARNINGS.md
```

---

## Rollback Procedures

When a learning proves incorrect or causes regressions, it must be rolled back.

### Identifying Bad Learnings

Signs that a learning may be incorrect:

1. **Increased rejection rate**: More schedules failing validation after learning was added
2. **User complaints**: Multiple users correcting the same pattern
3. **Performance drop**: Metrics decline after learning took effect
4. **Contradictory evidence**: New data contradicts the learning

### Rollback Methods

#### Method 1: Deprecate in Place (Preferred)

Move the learning to the "Deprecated Learnings" section with an explanation.

```markdown
## Deprecated Learnings

### [2026-01-06] Some incorrect pattern (Deprecated: 2026-01-10)
**Original**: What we thought was true
**Reason**: Invalidated - User correction showed opposite is true
**Superseded By**: [2026-01-10] Correct pattern
```

**When to use:** Learning was technically applied correctly but the pattern was wrong.

#### Method 2: Git Revert (Urgent)

Revert the specific commit that added the bad learning.

```bash
# Find the commit
git log --oneline --grep="reflect" | head -10

# Revert it
git revert <commit-sha>

# Message
git commit -m "revert(eros): rollback learning - caused regression

Reverted: [2026-01-06] Bad pattern title
Reason: Increased rejection rate from 2% to 15%"
```

**When to use:** Learning is causing immediate production issues.

#### Method 3: Edit and Recommit

For minor corrections to existing learnings.

```bash
# Edit LEARNINGS.md
# ...fix the learning...

git add LEARNINGS.md
git commit -m "fix(eros): correct learning - wrong content_type

Fixed: [2026-01-06] Pattern title
Change: feet -> toes in AVOID check"
```

**When to use:** Learning is mostly correct but has a detail error.

### Rollback Checklist

1. [ ] Identify the problematic learning
2. [ ] Determine rollback method (deprecate/revert/edit)
3. [ ] Execute rollback
4. [ ] Verify LEARNINGS.md is valid Markdown
5. [ ] Run test schedule generation
6. [ ] Monitor rejection rate for 24 hours
7. [ ] Document incident in changelog

---

## Confidence Promotion Rules

Learnings progress through confidence levels based on accumulated evidence.

### LOW to MEDIUM Promotion

**Criteria:**
- Sample size >= 10 schedules
- Pattern consistent in 80% of samples
- No contradictory HIGH learnings

**Process:**
1. System flags eligible LOW learnings in `/reflect status`
2. Operator reviews and confirms promotion
3. Learning moved from LOW section to MEDIUM section
4. Statistics updated

```markdown
# Before (LOW section)
### [2026-01-06] Lingerie performs better at 7pm
**Observation**: 8 schedules with 7pm lingerie had quality > 85
**Sample Size**: 8 (<10)
**Promote When**: Sample >= 10 AND consistent

# After (MEDIUM section)
### [2026-01-06] Lingerie performs better at 7pm
**Pattern**: Schedule lingerie content at 7pm
**Source**: performance | **Quality Score**: 87 avg | **Sample Size**: 12
**Applies To**: all
**Metric Impact**: +8% conversion
```

### MEDIUM to HIGH Promotion

**Criteria:**
- User explicit confirmation ("Yes, always do this")
- OR 5+ consecutive validation successes with this pattern
- OR incorporated into SKILL.md as permanent rule

**Process:**
1. System identifies candidates based on criteria
2. Operator reviews with `/reflect promote`
3. Learning moved to HIGH section
4. Original SKILL.md may be updated

---

## Statistics Tracking

LEARNINGS.md includes a statistics block that is auto-updated by the reflect command.

```yaml
by_confidence: { high: 5, medium: 12, low: 3 }
by_source: { validation: 8, user: 7, performance: 5 }
by_scope: { all_creators: 15, tier_specific: 3, creator_specific: 2 }
last_7_days: { added: 4, promoted: 1, deprecated: 0 }
```

### Metrics Explanation

| Metric | Description |
|--------|-------------|
| `by_confidence` | Count of learnings at each confidence level |
| `by_source` | Count by origin (validation, user, performance) |
| `by_scope` | Count by applicability (all, tier-specific, creator-specific) |
| `last_7_days` | Activity in rolling 7-day window |

---

## Integration with Pipeline

### Agent Startup Protocol

Every agent invocation begins with learning integration.

```
1. Read LEARNINGS.md
2. Filter to HIGH + MEDIUM learnings
3. Filter to applicable scope (all, tier, creator)
4. Load as constraints/preferences
5. Proceed with generation
```

### Generator Agent

```markdown
# In schedule-generator.md system prompt

## MANDATORY: Load Learnings
Before generating any schedule:
1. Read LEARNINGS.md
2. All HIGH learnings are CONSTRAINTS - never violate
3. All MEDIUM learnings are PREFERENCES - follow when possible
```

### Validator Agent

```markdown
# In schedule-validator.md system prompt

## Learning Generation
After validation:
1. If REJECTED: Capture violation as HIGH learning signal
2. If quality >= 85: Capture patterns as MEDIUM learning signal
3. Write signals to feedback buffer for /reflect
```

---

## Automatic vs Manual Reflection

### Automatic Reflection

Enabled with `/reflect on`. Triggers at session end if signals detected.

**Configuration:**
```json
{
  "auto_reflect": true,
  "min_signals": 1,
  "require_confirmation": true
}
```

**Behavior:**
- Scans session automatically before exit
- Shows preview and requires confirmation
- Does not commit without user approval

### Manual Reflection

Default mode. User invokes `/reflect` explicitly.

**Recommended cadence:**
- After each schedule generation session
- Before ending a working session
- Weekly consolidation review

---

## Best Practices

### For Operators

1. **Review weekly**: Run `/reflect status` weekly to check accumulation rates
2. **Promote judiciously**: Don't rush LOW to MEDIUM promotions
3. **Document rollbacks**: Always add context when deprecating
4. **Test after changes**: Generate a test schedule after manual LEARNINGS.md edits

### For Learning Quality

1. **Be specific**: "Check AVOID tier for feet" beats "Check content types"
2. **Include context**: Why did this fail? What was the creator/tier/situation?
3. **Limit scope appropriately**: Don't make all learnings apply to "all" if they're tier-specific
4. **Avoid duplicates**: Check existing learnings before adding similar ones

### For Git Hygiene

1. **Small commits**: One reflect session = one commit
2. **Clear messages**: Include learning count in commit message
3. **No manual edits without commits**: Always commit LEARNINGS.md changes
4. **Review before merge**: If using branches, review learning PRs

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| `LEARNINGS.md` | Accumulated learnings storage |
| `commands/reflect.md` | Reflect command reference |
| `skills/eros-schedule-generator/SKILL.md` | Main skill with activation protocol |
| `docs/RUNBOOK.md` | Operational procedures including learning ops |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-06 | Initial protocol documentation |
