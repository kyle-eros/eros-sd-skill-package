# EROS v1.0 Migration Guide

**Version**: 1.0.0
**Target Audience**: Engineers deploying v1.0

---

## Overview

This guide provides step-by-step instructions for migrating from EROS v4.0 to v1.0. The migration uses feature flags for gradual rollout with zero downtime.

### Architecture Changes

| Aspect | v4.0 | v1.0 |
|--------|------|------|
| Orchestrator | 2,468 lines | 209 lines |
| Pipeline phases | 10 | 3 |
| LLM agents | 5 | 2 |
| MCP calls | 50+ | ~10 |
| Execution time | 3-5 min | 60-90s |

---

## Pre-Migration Checklist

### 1. Environment Verification
```bash
# Verify Python environment
python --version  # Requires 3.10+

# Verify v1.0 modules exist
ls python/
# Expected: orchestrator.py, preflight.py, router.py, etc.
```

### 2. Database Compatibility
```bash
# Verify MCP tools are functional
# Test with a single creator
python -c "
from python.preflight import PreflightEngine, MockMCP
import asyncio
asyncio.run(PreflightEngine(MockMCP()).execute('test', '2026-01-06'))
"
```

### 3. Feature Flag Defaults
Ensure all feature flags are set to safe defaults:
```bash
export EROS_V5_ENABLED=false
export EROS_V5_SHADOW_MODE=false
export EROS_V5_PERCENTAGE=0
export EROS_V5_CREATORS=""
export EROS_V5_AUTO_FALLBACK=true
```

---

## Migration Steps

### Step 1: Deploy v1.0 Code

Deploy the eros-sd-skill-package to production:
```bash
# Clone the skill package
git clone https://github.com/kyle-eros/eros-sd-skill-package.git
cd eros-sd-skill-package
```

### Step 2: Configure Router Integration

Update your entry point to use the PipelineRouter:

```python
from python.router import PipelineRouter, FeatureFlags
from python.adapters import create_production_adapters

# Create adapters
mcp_client, task_tool = create_production_adapters(mcp_tools, task_invoker)

# Create router
router = PipelineRouter(FeatureFlags())

# Route requests
result = await router.route(
    mcp=mcp_client,
    task=task_tool,
    creator_id="alexia",
    week_start="2026-01-06",
    v4_runner=your_v4_function  # Required for fallback
)
```

### Step 3: Enable Shadow Mode

Start shadow mode to validate v5 without affecting production:

```bash
export EROS_V5_ENABLED=true
export EROS_V5_SHADOW_MODE=true
```

Monitor shadow comparisons:
```python
from python.comparator import get_metrics, generate_report
print(generate_report())
```

### Step 4: Canary Rollout

After shadow mode validation, enable v5 for a single creator:

```bash
export EROS_V5_SHADOW_MODE=false
export EROS_V5_CREATORS="alexia"
```

### Step 5: Percentage Rollout

Gradually increase traffic to v5:

```bash
# 25% -> 50% -> 75% -> 100%
export EROS_V5_PERCENTAGE=25
# Wait 48 hours, then:
export EROS_V5_PERCENTAGE=50
# Continue...
```

### Step 6: Full Cutover

After stable percentage rollout:
```bash
export EROS_V5_PERCENTAGE=100
export EROS_V5_CREATORS=""  # Clear allowlist
```

---

## Configuration Reference

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `EROS_V5_ENABLED` | bool | `false` | Global kill switch |
| `EROS_V5_SHADOW_MODE` | bool | `false` | Run both pipelines |
| `EROS_V5_PERCENTAGE` | int | `0` | % of traffic to v5 (0-100) |
| `EROS_V5_CREATORS` | string | `""` | Comma-separated creator IDs |
| `EROS_V5_AUTO_FALLBACK` | bool | `true` | Fall back to v4 on v5 error |

### Routing Priority

1. If `EROS_V5_ENABLED=false` → v4
2. If `EROS_V5_SHADOW_MODE=true` → Both (return v4)
3. If creator in `EROS_V5_CREATORS` → v5
4. If random < `EROS_V5_PERCENTAGE` → v5
5. Default → v4

---

## Verification Procedures

### Verify Shadow Mode
```python
from python.comparator import get_metrics
m = get_metrics()
assert m.v5_failed / max(m.total, 1) < 0.10, "v5 failure rate too high"
assert m.avg_quality_diff > -5, "Quality regression detected"
```

### Verify Live Traffic
```python
from python.monitoring import PipelineMonitor
monitor = PipelineMonitor()
status = monitor.get_status()
assert status["success_rate"] >= 0.95, "Success rate below threshold"
assert status["health"] == "healthy", f"Unhealthy: {status}"
```

### Verify Rollback Works
```python
from python.rollback import RollbackController
controller = RollbackController()
# Test rollback
result = await controller.execute_rollback("test", "manual")
assert result.success
# Restore
result = await controller.restore_v5("RESTORE_V5_CONFIRMED")
assert result.success
```

---

## Rollback Procedure

### Manual Rollback
```bash
# Option 1: Environment variable
export EROS_V5_ENABLED=false

# Option 2: Python
python -c "
import os
os.environ['EROS_V5_ENABLED'] = 'false'
print('V5 disabled')
"
```

### Automatic Rollback
The system automatically rolls back when:
- Success rate < 85% for 5 minutes
- P95 latency > 180s for 3 runs
- Hard gate violations > 10%
- Quality avg < 70 for 10 runs

---

## Post-Migration Tasks

### Week 1 Post-Cutover
- [ ] Monitor all 37 creators for anomalies
- [ ] Review quality scores daily
- [ ] Compare revenue metrics week-over-week
- [ ] Document any issues

### Week 2-4 Post-Cutover
- [ ] Evaluate v4 deprecation timeline
- [ ] Remove shadow mode code path (optional)
- [ ] Update documentation
- [ ] Archive v4 for emergency use

### After 30 Days
- [ ] Mark v4 as deprecated
- [ ] Plan v4 removal
- [ ] Finalize migration documentation

---

## Troubleshooting

### v5 Not Running
```bash
# Check feature flags
env | grep EROS_V5

# Verify enabled
python -c "
from python.router import FeatureFlags
f = FeatureFlags()
print(f'enabled={f.v5_enabled}, shadow={f.shadow_mode}, pct={f.v5_percentage}')
"
```

### Routing to Wrong Pipeline
```python
from python.router import PipelineRouter
router = PipelineRouter()
decision = router.decide("alexia")
print(f"Pipeline: {decision.pipeline}, Reason: {decision.reason}")
```

### Rollback Not Working
```python
from python.rollback import RollbackController
c = RollbackController()
print(f"State: {c.state}, In-flight: {c.in_flight}")
```

---

## Support

- **Slack**: #eros-engineering
- **Escalation**: See RUNBOOK.md
- **Architecture Questions**: See ARCHITECTURE_DECISION_RECORD.md
