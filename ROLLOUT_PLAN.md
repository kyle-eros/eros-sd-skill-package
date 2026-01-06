# EROS v1.0 Production Rollout Plan

**Version**: 1.0.0
**Timeline**: 6 weeks
**Target**: Zero-downtime migration from v4.0 to v1.0

---

## Executive Summary

This plan migrates the EROS schedule generator from v4.0 (2,468-line orchestrator) to v1.0 (209-line orchestrator) with:
- Feature flag-based routing for gradual rollout
- Shadow mode validation before live traffic
- Automated rollback on SLO violations
- A/B comparison metrics for confidence building

**Expected Outcomes:**
- 4x faster execution (3-5 min → 60-90s)
- 67% reduction in MCP calls (50+ → ~10)
- 67% reduction in LLM agents (5 → 2)
- Improved maintainability (simplified 3-phase architecture)

---

## Phase 0: Shadow Mode (Week 1)

### Objective
Validate v1.0 produces equivalent or better schedules without affecting production.

### Configuration
```bash
EROS_V5_ENABLED=true
EROS_V5_SHADOW_MODE=true
EROS_V5_PERCENTAGE=0
EROS_V5_CREATORS=""
```

### Execution
- All 37 creators route to v4 (production output)
- v5 runs in parallel, results logged but discarded
- Daily comparison reports generated

### Success Criteria
| Metric | Threshold |
|--------|-----------|
| v5 failure rate | < 10% |
| Quality diff (v5 - v4) | > -5 points |
| Hard gate false positives | 0 |
| Comparison count | >= 50 |

### Rollback Trigger
- v5 failure rate > 20%
- Any hard gate regression

### Daily Tasks
- [ ] Review shadow comparison report
- [ ] Investigate any v5 failures
- [ ] Document quality differences
- [ ] Fix identified issues before Phase 1

---

## Phase 1: Canary (Week 2)

### Objective
Validate v1.0 in production with single low-risk creator.

### Configuration
```bash
EROS_V5_ENABLED=true
EROS_V5_SHADOW_MODE=false
EROS_V5_PERCENTAGE=0
EROS_V5_CREATORS="alexia"
```

### Creator Selection
- **alexia**: STANDARD tier, paid page, moderate volume
- Representative of typical creator workload
- Not high-revenue (limits blast radius)

### Success Criteria
| Metric | Threshold |
|--------|-----------|
| Success rate | >= 95% |
| P95 latency | < 120s |
| Quality score avg | >= 80 |
| Hard gate violations | 0 |
| Duration | 7 days stable |

### Rollback Trigger
- Any hard gate violation
- Success rate < 90%
- Quality score < 70

### Daily Tasks
- [ ] Review alexia's schedule quality
- [ ] Check monitoring dashboard
- [ ] Compare revenue metrics (if available)
- [ ] Document any anomalies

---

## Phase 2: Early Adopters (Week 3)

### Objective
Expand to multiple creators covering all page types and tiers.

### Configuration
```bash
EROS_V5_ENABLED=true
EROS_V5_SHADOW_MODE=false
EROS_V5_PERCENTAGE=0
EROS_V5_CREATORS="alexia,grace_bennett,luna_free"
```

### Creator Selection
| Creator | Tier | Page Type | Rationale |
|---------|------|-----------|-----------|
| alexia | STANDARD | paid | Continued from Phase 1 |
| grace_bennett | HIGH_VALUE | paid | Higher revenue, more volume |
| luna_free | STANDARD | free | Free page validation |

### Success Criteria
| Metric | Threshold |
|--------|-----------|
| Success rate (all 3) | >= 95% |
| P95 latency | < 120s |
| Quality score avg | >= 80 |
| Hard gate violations | 0 |
| Duration | 7 days all stable |

### Rollback Trigger
- Hard gate violation on any creator
- Success rate < 90% for any creator
- Quality regression > 10 points

### Daily Tasks
- [ ] Review all 3 creators' schedules
- [ ] Compare cross-tier performance
- [ ] Validate free vs paid page handling
- [ ] Document tier-specific issues

---

## Phase 3: Percentage Rollout (Week 4-5)

### Sub-Phase 3a: 25% (Days 1-2)
```bash
EROS_V5_PERCENTAGE=25
```

### Sub-Phase 3b: 50% (Days 3-4)
```bash
EROS_V5_PERCENTAGE=50
```

### Sub-Phase 3c: 75% (Days 5-7)
```bash
EROS_V5_PERCENTAGE=75
```

### Advancement Criteria
- 48 hours at current percentage with:
  - Success rate >= 95%
  - P95 latency < 120s
  - Quality avg >= 80
  - No hard gate violations

### Monitoring Focus
- Watch for creator-specific issues via consistent hashing
- Monitor aggregate metrics across increasing traffic
- Track any performance degradation at scale

### Rollback Trigger
- Success rate < 85% for 5 minutes
- P95 latency > 180s for 3 consecutive runs
- Hard gate violation rate > 10%

---

## Phase 4: Full Cutover (Week 6)

### Objective
Complete migration with v5 handling 100% of traffic.

### Configuration
```bash
EROS_V5_ENABLED=true
EROS_V5_SHADOW_MODE=false
EROS_V5_PERCENTAGE=100
EROS_V5_CREATORS=""
```

### Pre-Cutover Checklist
- [ ] All 37 creators verified in v5 (via percentage rollout)
- [ ] No rollbacks in previous 7 days
- [ ] Quality metrics stable or improved
- [ ] On-call engineer briefed
- [ ] Rollback procedure tested

### Post-Cutover Tasks
- [ ] Monitor for 24 hours continuously
- [ ] Verify all scheduled jobs execute
- [ ] Compare week-over-week revenue (if possible)
- [ ] Document lessons learned

### V4 Deprecation
- Keep v4 code path available for 30 days
- Mark as `@deprecated` in codebase
- Remove after 30 days of stable v5 operation

---

## Rollback Procedures

### Manual Rollback
```bash
# Immediate disable
export EROS_V5_ENABLED=false

# Or use rollback controller
python -c "from python.rollback import RollbackController; ..."
```

### Automatic Rollback Triggers
| Condition | Threshold | Window |
|-----------|-----------|--------|
| Success rate | < 85% | 5 min |
| P95 latency | > 180s | 3 runs |
| Hard gate violations | > 10% | Last 10 runs |
| Quality avg | < 70 | Last 10 runs |

### Post-Rollback Actions
1. Disable v5 routing (automatic)
2. Alert on-call engineer (automatic)
3. Investigate root cause (manual)
4. Fix and re-validate in shadow mode
5. Resume rollout from last stable phase

---

## Metrics & Dashboards

### Key Metrics
| Metric | Location | Alert Threshold |
|--------|----------|-----------------|
| Pipeline success rate | monitoring.py | < 95% |
| P95 latency | monitoring.py | > 120s |
| Hard gate violations | monitoring.py | > 5% |
| Quality score avg | monitoring.py | < 80 |
| Shadow comparison diff | comparator.py | < -5 |

### Log Locations
- Pipeline executions: `eros.orchestrator`
- Routing decisions: `eros.router`
- Comparisons: `eros.comparator`
- Monitoring: `eros.monitoring`
- Rollbacks: `eros.rollback`

---

## Communication Plan

### Stakeholders
- Engineering: #eros-engineering
- Operations: #eros-alerts
- Leadership: Weekly summary

### Escalation
| Severity | Response | Contact |
|----------|----------|---------|
| INFO | Log only | - |
| WARNING | Slack alert | On-call |
| CRITICAL | Slack + PagerDuty | Team lead |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| v5 produces invalid schedules | Low | High | Shadow mode validation |
| Performance regression | Medium | Medium | Feature flag instant rollback |
| Data loss | Low | Critical | v4 continues until v5 validated |
| Agent timeouts | Medium | Medium | Retry logic + timeout config |

---

## Success Metrics

### Phase Completion
- [ ] Shadow mode: 50+ comparisons, <10% failure
- [ ] Canary: 7 days stable
- [ ] Early adopters: 7 days all stable
- [ ] Percentage: 75% traffic, 48h stable
- [ ] Full cutover: 100% traffic, 7 days stable

### Final Validation
| Metric | v4 Baseline | v5 Target | v5 Actual |
|--------|-------------|-----------|-----------|
| Execution time | 3-5 min | < 90s | TBD |
| MCP calls | 50+ | ~10 | TBD |
| Success rate | ~95% | >= 95% | TBD |
| Quality score | ~80 | >= 80 | TBD |

---

## Appendix: Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| EROS_V5_ENABLED | bool | false | Global kill switch |
| EROS_V5_SHADOW_MODE | bool | false | Run both pipelines |
| EROS_V5_PERCENTAGE | int | 0 | % of traffic to v5 |
| EROS_V5_CREATORS | list | "" | Allowlisted creators |
| EROS_V5_AUTO_FALLBACK | bool | true | Fallback on v5 failure |

---

## Phase 7: Self-Improving Skills (Week 7+)

### Objective

Enable continuous learning from operational feedback to improve schedule quality over time.

### Prerequisites

Before starting Phase 7, verify:

- [ ] **Phase 6 complete**: Full cutover achieved, v5 handling 100% traffic
- [ ] **7+ days stable**: No rollbacks in previous week
- [ ] **LEARNINGS.md initialized**: File exists with proper structure
- [ ] **Reflect command available**: `/reflect` command accessible
- [ ] **Git configured**: Repository can commit learning updates
- [ ] **Feedback hooks configured**: Validation agent captures signals

### Configuration

```bash
# Phase 7 does not require new environment variables
# Learning system activates automatically with v1.0.0

# Optional: Enable auto-reflection
/reflect on
```

### Deployment Steps

#### Step 1: Enable Feedback Capture (Day 1)

Feedback capture is automatic in v1.0.0. Verify it is working:

```bash
# Generate a test schedule
# Then check for signals
/reflect status

# Expected: Shows signal detection is active
```

**Validation**:
- [ ] Validation results create learning signals
- [ ] User corrections detected (if any)
- [ ] `/reflect status` shows system active

#### Step 2: Manual Reflection Period (Days 1-14)

Run `/reflect` manually after each significant session to build confidence.

```bash
# After schedule generation sessions
/reflect

# Review proposed learnings before committing
# Confirm each learning is accurate
```

**Guidelines**:
- Run `/reflect` at least once per working day
- Review each proposed learning carefully
- Reject any learnings that seem incorrect
- Target: 5-10 learnings captured in first 2 weeks

**Validation**:
- [ ] LEARNINGS.md has 5+ entries after 2 weeks
- [ ] No incorrect learnings committed
- [ ] Statistics block updating correctly

#### Step 3: Enable Auto-Reflection (Day 15+)

After 2 weeks of successful manual reflection:

```bash
# Enable auto-reflection
/reflect on

# Configure settings
# min_signals: 1 (trigger on any signal)
# require_confirmation: true (always ask before commit)
```

**Validation**:
- [ ] Auto-reflect triggers at session end
- [ ] Confirmation still required before commit
- [ ] Learning quality maintained

### Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Learnings accumulated | 10+ | After 4 weeks |
| HIGH confidence learnings | < 5 | Indicates few major corrections needed |
| MEDIUM confidence learnings | 5-15 | Healthy pattern detection |
| Incorrect learnings | 0 | No rollbacks required |
| Learning application | 100% | Agents loading LEARNINGS.md |
| Quality score trend | Stable or improving | Week-over-week comparison |

### Monitoring

```bash
# Weekly check
/reflect status

# Expected output:
# by_confidence: { high: 2, medium: 8, low: 3 }
# by_source: { validation: 5, user: 4, performance: 4 }
# last_7_days: { added: 3, promoted: 0, deprecated: 0 }
```

**Warning Signs**:
- HIGH learnings > 2/week: Too many corrections needed
- Zero learnings in 2 weeks: Feedback capture may be broken
- Frequent deprecations: Learning quality issue

### Rollback Procedure

If learning system causes issues:

1. **Disable auto-reflection**
```bash
/reflect off
```

2. **Revert problematic learnings**
```bash
git log --oneline --grep="reflect" -5
git revert <problematic-commit>
```

3. **Clear LEARNINGS.md** (nuclear option)
```bash
# Reset to initial state
git checkout HEAD~N LEARNINGS.md
git commit -m "revert(eros): reset LEARNINGS.md - learning system issues"
```

4. **Resume manual reflection**
- Investigate root cause
- Fix issues
- Re-enable auto-reflection when confident

### Phase 7 Completion Checklist

- [ ] 4 weeks of stable learning accumulation
- [ ] 10+ learnings in LEARNINGS.md
- [ ] No learning-related rollbacks
- [ ] Auto-reflection enabled and stable
- [ ] Quality scores maintained or improved
- [ ] Operations team trained on learning system
- [ ] RUNBOOK updated with learning operations
- [ ] Weekly review cadence established

### Post-Phase 7 Operations

After Phase 7 completion, learning system enters steady-state:

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Review new learnings | Weekly | Operations |
| Promote LOW to MEDIUM | Monthly | Engineering |
| Audit LEARNINGS.md | Quarterly | Engineering |
| Promote to SKILL.md | As needed | Engineering |

### Related Documentation

- `docs/SELF_IMPROVING_SKILLS.md` - Protocol details
- `docs/RUNBOOK.md` - Section 9: Learning System Operations
- `LEARNINGS.md` - Accumulated learnings
- `commands/reflect.md` - Command reference
