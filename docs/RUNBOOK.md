# EROS v1.0 Operations Runbook

**Version**: 1.0.0
**Target Audience**: On-call engineers, operations team

---

## 1. System Overview

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    PipelineRouter                           │
│              (Feature Flag Decision)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│  v4.0 Pipeline  │         │  v1.0 Pipeline  │
│  (10 phases)    │         │  (3 phases)     │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │         ┌─────────────────┤
         │         ▼                 │
         │  ┌──────────────┐         │
         │  │   Preflight  │◄────────┤
         │  │  (4 MCP)     │         │
         │  └──────┬───────┘         │
         │         ▼                 │
         │  ┌──────────────┐         │
         │  │  Generator   │         │
         │  │  (Sonnet)    │         │
         │  └──────┬───────┘         │
         │         ▼                 │
         │  ┌──────────────┐         │
         │  │  Validator   │         │
         │  │  (Opus)      │         │
         │  └──────────────┘         │
         │                           │
         └───────────┬───────────────┘
                     ▼
              ┌──────────────┐
              │   MCP DB     │
              │ save_schedule│
              └──────────────┘
```

### Component Responsibilities

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| Router | Feature flag routing | `router.py` |
| Preflight | Context generation | `preflight.py` |
| Orchestrator | Pipeline coordination | `orchestrator.py` |
| Monitoring | SLO tracking | `monitoring.py` |
| Rollback | Automated recovery | `rollback.py` |
| Adapters | MCP/Task integration | `adapters.py` |

### Data Flow
1. Request arrives at PipelineRouter
2. Router decides v4 or v5 based on flags
3. v5: Preflight fetches creator context (4 MCP calls via bundled `get_creator_profile`)
4. v5: Generator creates schedule (Sonnet agent)
5. v5: Validator checks hard gates (Opus agent)
6. Schedule saved via MCP `save_schedule`

> **Optimization Note (v1.1.0)**: Preflight reduced from 7 to 4 MCP calls (43% reduction) by bundling analytics, volume, and content rankings into `get_creator_profile`.

---

## 2. Monitoring & Dashboards

### Key Metrics

| Metric | Normal | Warning | Critical |
|--------|--------|---------|----------|
| Success Rate | >95% | 90-95% | <90% |
| P95 Latency | <90s | 90-120s | >120s |
| Hard Gate Rate | <2% | 2-5% | >5% |
| Quality Avg | >80 | 75-80 | <75 |

### Log Locations

| Logger | Content |
|--------|---------|
| `eros.orchestrator` | Pipeline execution |
| `eros.router` | Routing decisions |
| `eros.comparator` | Shadow comparisons |
| `eros.monitoring` | Metrics events |
| `eros.rollback` | Rollback events |
| `eros.adapters` | MCP/Task calls |

### Checking Current Status
```python
from python.monitoring import PipelineMonitor
from python.rollback import RollbackController
from python.router import FeatureFlags

# Feature flags
flags = FeatureFlags()
print(f"V5 Enabled: {flags.v5_enabled}")
print(f"Shadow Mode: {flags.shadow_mode}")
print(f"Percentage: {flags.v5_percentage}%")

# Health status
monitor = PipelineMonitor()
status = monitor.get_status()
print(f"Health: {status['health']}")
print(f"Success Rate: {status['success_rate']:.2%}")

# Rollback state
rollback = RollbackController()
print(f"Rollback State: {rollback.state}")
```

### Alert Definitions

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| V5_SUCCESS_LOW | success_rate < 90% | WARNING | Investigate |
| V5_SUCCESS_CRITICAL | success_rate < 85% | CRITICAL | Prepare rollback |
| V5_LATENCY_HIGH | p95 > 120s | WARNING | Check agents |
| V5_LATENCY_CRITICAL | p95 > 180s | CRITICAL | Consider rollback |
| V5_HARD_GATE_SPIKE | rate > 5% | CRITICAL | Investigate vault/AVOID |
| V5_AUTO_ROLLBACK | triggered | CRITICAL | Post-mortem required |

---

## 3. Common Issues

### 3.1 v5 Pipeline Timeout

**Symptoms:**
- Execution exceeds 180s
- Agent phases hang

**Diagnosis:**
```python
# Check which phase is slow
result = await orchestrator.run(creator_id, week_start)
for phase, metrics in result.metrics.items():
    if metrics.get("duration_ms", 0) > 60000:
        print(f"Slow phase: {phase} ({metrics['duration_ms']}ms)")
```

**Resolution:**
1. Check if agents are responsive (Task tool timeout)
2. Verify MCP server is healthy
3. If persistent, increase timeout or rollback

### 3.2 Hard Gate False Positives

**Symptoms:**
- Valid schedules rejected
- Vault/AVOID errors on correct content

**Diagnosis:**
```python
# Check vault availability
vault = await mcp.get_allowed_content_types(creator_id)
print(f"Vault types: {vault}")

# Check content rankings
rankings = await mcp.get_content_type_rankings(creator_id)
avoid = [r for r in rankings.get('content_types', []) if r.get('performance_tier') == 'AVOID']
print(f"AVOID types: {avoid}")
```

**Resolution:**
1. Verify vault_matrix is synced
2. Check if content_type_rankings is stale
3. Clear MCP cache if needed

### 3.3 MCP Connection Failures

**Symptoms:**
- Preflight fails with connection errors
- Retry exhausted messages

**Diagnosis:**
```python
# Check MCP health
from python.adapters import ProductionMCPClient
client = ProductionMCPClient(mcp_tools)
try:
    await client.get_active_creators(limit=1)
    print("MCP healthy")
except Exception as e:
    print(f"MCP error: {e}")
```

**Resolution:**
1. Restart MCP server
2. Check database file permissions
3. Verify EROS_DB_PATH is correct

### 3.4 Agent Invocation Errors

**Symptoms:**
- Generator or Validator phase fails
- Task tool returns errors

**Diagnosis:**
```python
# Check agent invocation
from python.adapters import ProductionTaskTool
tool = ProductionTaskTool(task_invoker)
result = await tool.invoke("schedule-generator", "test prompt", model="sonnet")
print(f"Agent response: {result}")
```

**Resolution:**
1. Verify Claude API is accessible
2. Check agent definitions exist
3. Review prompt for issues

---

## 4. Troubleshooting Steps

### General Debugging
```bash
# 1. Check feature flags
env | grep EROS_V5

# 2. Check logs
grep "eros\." /var/log/app.log | tail -50

# 3. Check recent rollbacks
python -c "
from python.rollback import RollbackController
c = RollbackController()
print(c.get_history())
"
```

### Debug Mode
```python
import logging
logging.getLogger("eros").setLevel(logging.DEBUG)

# Run with verbose logging
result = await orchestrator.run(creator_id, week_start)
```

### Test Commands
```bash
# Test preflight only
python python/preflight.py --creator alexia --week 2026-01-06

# Test with mock MCP
python -c "
from python.preflight import PreflightEngine, MockMCP
import asyncio
ctx = asyncio.run(PreflightEngine(MockMCP()).execute('test', '2026-01-06'))
print(f'Preflight OK: {ctx.creator_id}, {ctx.volume_config[\"tier\"]}')
"
```

---

## 5. Rollback Procedure

### When to Rollback
- Success rate < 85% for 5+ minutes
- P95 latency > 180s for 3+ consecutive runs
- Hard gate violations > 10%
- Quality avg < 70 for 10+ runs
- Any critical bug discovered

### Manual Rollback Steps

1. **Disable v5 immediately**
```bash
export EROS_V5_ENABLED=false
```

2. **Verify v4 is serving**
```python
from python.router import PipelineRouter
router = PipelineRouter()
decision = router.decide("any_creator")
assert decision.pipeline.value == "v4", "V4 not active!"
```

3. **Alert team**
```
Slack #eros-alerts:
"[ROLLBACK] v5 disabled. Reason: <reason>. Investigating."
```

4. **Gather diagnostics**
```python
from python.monitoring import PipelineMonitor
monitor = PipelineMonitor()
status = monitor.get_status()
# Save status for post-mortem
```

5. **Post-mortem**
- Document timeline
- Identify root cause
- Plan fix
- Re-validate in shadow mode

### Automatic Rollback
The system auto-rolls back when thresholds are exceeded:
```python
from python.rollback import RollbackController
from python.monitoring import PipelineMonitor

controller = RollbackController(monitor=PipelineMonitor())
# This is called periodically
result = await controller.check_auto_rollback()
if result:
    print(f"Auto-rollback triggered: {result.reason}")
```

### Post-Rollback Verification
```python
import os
assert os.environ.get("EROS_V5_ENABLED", "false").lower() != "true"

# Verify traffic routing
from python.router import PipelineRouter
router = PipelineRouter()
for creator in ["alexia", "test1", "test2"]:
    decision = router.decide(creator)
    assert decision.pipeline.value == "v4", f"{creator} not on v4!"
```

---

## 6. Escalation

### L1: On-Call Engineer
- Monitor alerts
- Execute runbook procedures
- Manual rollback if needed
- Escalate if unresolved in 30 min

### L2: EROS Team Lead
- Complex debugging
- Architecture decisions
- Coordinate fixes
- Escalate if P0 impact

### L3: Platform Team
- Infrastructure issues
- MCP server problems
- Claude API issues

### Contact Information
| Role | Contact |
|------|---------|
| On-Call | PagerDuty rotation |
| EROS Lead | #eros-engineering |
| Platform | #platform-support |

---

## 7. Recovery Procedures

### After Fixing an Issue
1. Run fix through tests
2. Deploy fix
3. Re-enable shadow mode
4. Validate 24h in shadow
5. Resume rollout from last stable phase

### After Auto-Rollback
1. Investigate immediately (don't leave in rolled-back state)
2. Identify root cause within 4 hours
3. Fix and validate
4. Restore v5 with explicit confirmation:
```python
controller = RollbackController()
result = await controller.restore_v5("RESTORE_V5_CONFIRMED")
```

---

## 8. Maintenance Procedures

### Cache Management
```python
# MCP cache stats (if implemented)
# Check cache hit rate, evictions
```

### Log Rotation
```bash
# Ensure eros.* logs are rotated
# Max size: 100MB
# Retention: 7 days
```

### Health Checks
```python
# Periodic health check
from python.monitoring import PipelineMonitor
monitor = PipelineMonitor()
status = monitor.get_status()
if status["health"] != "healthy":
    # Alert
    pass
```

---

## 9. Learning System Operations

### Overview

The self-improving skills system captures learnings from validation, user feedback, and performance data. Expected accumulation rate is 2-5 learnings per week during normal operation.

### Monitoring Learning Accumulation

#### Check Current Status
```bash
# Via reflect command
/reflect status

# Expected output:
# LEARNINGS.md Statistics:
#   by_confidence: { high: 5, medium: 12, low: 3 }
#   by_source: { validation: 8, user: 7, performance: 5 }
#   last_7_days: { added: 4, promoted: 1, deprecated: 0 }
```

#### Manual Inspection
```bash
# Count learnings by section
grep -c "^### \[" LEARNINGS.md

# View recent additions
git log --oneline --grep="reflect" -5

# Check learning distribution
grep -A1 "by_confidence" LEARNINGS.md
```

#### Expected Rates

| Metric | Normal | Warning | Action |
|--------|--------|---------|--------|
| Learnings/week | 2-5 | < 1 or > 10 | Investigate |
| HIGH learnings/week | 0-1 | > 2 | Check validation config |
| Promotion rate | 1-2/month | 0 for 30 days | Review LOW learnings |
| Deprecation rate | 0-1/month | > 2/month | Learning quality issue |

### Troubleshooting Reflection Failures

#### Symptom: Reflect Command Hangs

**Cause**: Large session with many signals

**Resolution**:
```bash
# Check signal count first
/reflect status

# If > 20 signals, process in batches
# Close session, start new one, run /reflect
```

#### Symptom: "No signals found"

**Cause**: Session had no schedule generation activity

**Expected**: Normal if no schedules were generated

**If unexpected**:
1. Verify schedule generation completed
2. Check validation agent produced certificates
3. Verify LEARNINGS.md is readable

#### Symptom: Git Commit Fails

**Cause**: LEARNINGS.md has merge conflicts or invalid Markdown

**Resolution**:
```bash
# Check file validity
cat LEARNINGS.md | head -50

# Check git status
git status LEARNINGS.md

# If conflicts, resolve manually then:
git add LEARNINGS.md
git commit -m "fix(eros): resolve LEARNINGS.md conflicts"
```

#### Symptom: Learnings Not Applied

**Cause**: Agent not loading LEARNINGS.md at startup

**Diagnosis**:
```bash
# Verify file exists and is readable
ls -la LEARNINGS.md

# Check for syntax errors in Markdown
# Look for unclosed code blocks or broken tables
```

**Resolution**:
1. Verify SKILL.md includes learning load step
2. Check agent is reading LEARNINGS.md
3. Validate Markdown syntax

### Manual Learning Entry Guidelines

When manual entry is required (rare), follow this format exactly:

#### HIGH Confidence Entry
```markdown
### [YYYY-MM-DD] Brief title describing the correction
**Pattern**: What was incorrectly done
**Issue**: Why it was wrong
**Correction**: What to do instead
**Source**: validation | user | **Violation Code**: CODE
**Applies To**: all | tier:TIER_NAME | creator:creator_id
```

#### MEDIUM Confidence Entry
```markdown
### [YYYY-MM-DD] Brief title describing the pattern
**Pattern**: What was observed | **Insight**: Why it works
**Source**: validation | user | performance | **Quality Score**: N | **Sample Size**: N
**Applies To**: all | tier:TIER_NAME | creator:creator_id
**Metric Impact**: +N% RPS | +N% conversion | etc.
```

#### Manual Entry Checklist
- [ ] Date format is [YYYY-MM-DD]
- [ ] Placed in correct confidence section
- [ ] All required fields populated
- [ ] Source is one of: validation, user, performance
- [ ] Applies To is one of: all, tier:NAME, creator:ID
- [ ] Statistics block updated
- [ ] Git commit with proper message

### Learning Rollback Procedures

#### Scenario: Learning Caused Regression

**Symptoms**:
- Increased rejection rate after learning added
- Quality scores dropping
- User complaints about schedule quality

**Steps**:
1. Identify the problematic learning
```bash
git log --oneline --grep="reflect" -10
git diff <commit>~1 <commit> LEARNINGS.md
```

2. Choose rollback method:

**Option A: Deprecate (Preferred)**
```markdown
# Move to Deprecated section with reason
### [2026-01-06] Bad pattern (Deprecated: 2026-01-10)
**Original**: What it said
**Reason**: Invalidated - caused 15% rejection increase
```

**Option B: Git Revert (Urgent)**
```bash
git revert <commit-sha>
git push
```

3. Verify fix
```bash
# Generate test schedule
# Check rejection rate returns to normal
```

4. Document incident
```bash
# Add to CHANGELOG.md under current version
### Fixed
- Reverted learning "[title]" - caused regression
```

#### Scenario: Conflicting Learnings

**Symptoms**:
- Two learnings contradict each other
- Agent behavior inconsistent

**Resolution**:
1. Identify the conflict
2. Deprecate the less-reliable learning
3. Keep the higher-confidence one (HIGH > MEDIUM > LOW)
4. If same confidence, keep newer one with more samples

### Periodic Maintenance

#### Weekly Tasks
- [ ] Run `/reflect status` to check accumulation
- [ ] Review any new HIGH learnings
- [ ] Check for promotion candidates (LOW with sample >= 10)

#### Monthly Tasks
- [ ] Audit LEARNINGS.md for stale entries
- [ ] Review deprecated section - can any be removed?
- [ ] Check statistics block accuracy
- [ ] Verify learnings align with current business rules

#### Quarterly Tasks
- [ ] Consider promoting stable MEDIUM learnings to SKILL.md
- [ ] Archive old deprecated learnings (> 90 days)
- [ ] Review learning quality metrics with team
