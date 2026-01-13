# EROS Self-Improving Skills - Learning Accumulation

**Version**: 1.1.0 | **Last Updated**: 2026-01-12 | **Total Learnings**: 0

---

## Feedback Sources & Confidence Levels

| Level | Behavior | Sources |
|-------|----------|---------|
| **HIGH** | MUST follow | Hard gate violations, explicit user corrections |
| **MEDIUM** | SHOULD follow | Quality >= 85 patterns, user approvals, sample >= 10 |
| **LOW** | MAY inform | Sample < 10, emerging trends to monitor |

---

## Statistics

```yaml
by_confidence: { high: 0, medium: 0, low: 0 }
by_source: { validation: 0, user: 0, performance: 0 }
by_scope: { all_creators: 0, tier_specific: 0, creator_specific: 0 }
last_7_days: { added: 0, promoted: 0, deprecated: 0 }
```

---

## HIGH Confidence Learnings

> MUST follow - Hard gate violations and explicit user corrections

<!-- Entry Template:
### [YYYY-MM-DD] Title
**Pattern**: What was done
**Issue**: Why it was wrong
**Correction**: What to do instead
**Source**: validation | user | **Violation Code**: CODE | **Sample Size**: N
**Applies To**: all | tier:TIER_NAME | creator:creator_id
-->

---

## MEDIUM Confidence Learnings

> SHOULD follow - Patterns from quality >= 85 schedules and user approvals

<!-- Entry Template:
### [YYYY-MM-DD] Title
**Pattern**: What was observed | **Insight**: Why it works
**Source**: validation | user | performance | **Quality Score**: N | **Sample Size**: N
**Applies To**: all | tier:TIER_NAME | creator:creator_id
**Metric Impact**: +N% RPS | +N% conversion | etc.
-->

---

## LOW Confidence Learnings

> MAY inform - Observations with sample < 10, trends to monitor

### [2026-01-12] save_schedule v2.0.0 Schema Alignment
**Observation**: 6 column name mismatches between MCP tool and database schema caused silent failures
**Hypothesis**: Schema drift between documentation, code, and database is a recurring risk
**Source**: refactor | **Sample Size**: 1
**Applies To**: all
**Promote When**: Similar schema issues found in other MCP tools

<!-- Entry Template:
### [YYYY-MM-DD] Title
**Observation**: What was noticed | **Hypothesis**: Why it might matter
**Source**: validation | user | performance | **Sample Size**: N (<10)
**Applies To**: all | tier:TIER_NAME | creator:creator_id
**Promote When**: Sample >= 10 AND consistent results
-->

---

## Deprecated Learnings

> Superseded, invalidated, or expired learnings

### [2026-01-12] Test Artifacts Removed
**Original**: 47 "High Quality Pattern (90)" entries from test/mock validations
**Reason**: Invalidated - entries were from test runs with mock data, not production schedules

---

## Changelog

| Date | Action | Learning | Confidence | Source |
|------|--------|----------|------------|--------|
| 2026-01-12 | CLEANED | Removed 47 test-generated entries | - | refactor |
| 2026-01-12 | ADDED | save_schedule v2.0.0 Schema Alignment | LOW | refactor |
| 2026-01-06 | CREATED | Initial structure | - | system |

---

## Integration Hooks

### Validation Phase (Immediate)
```python
if certificate.status == "REJECTED":
    add_learning(confidence="HIGH", source="validation",
                 violation=certificate.violations, pattern=context)
if certificate.quality_score >= 85:
    add_learning(confidence="MEDIUM", source="validation",
                 quality=certificate.quality_score, pattern=decisions)
```

### Performance Feedback (7-14 days delayed)
```python
if rps > baseline * 1.15:
    add_learning(confidence="MEDIUM", source="performance",
                 impact=f"+{delta}% RPS", pattern=schedule_decisions)
```

### Promotion Rules
| LOW -> MEDIUM | Sample >= 10 AND 80% consistent |
| MEDIUM -> HIGH | User confirms OR 5+ validation successes |

---

## Agent Usage

- **schedule-generator**: Read HIGH/MEDIUM at start, apply corrections
- **schedule-validator**: Reference when scoring, generate learnings on reject
- **reflect command**: Extract session learnings, update stats, Git commit

---

*Ready to receive learnings*
