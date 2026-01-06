# EROS v1.0 Architecture Decision Record

**Status**: Accepted
**Date**: 2026-01-06
**Authors**: EROS Engineering Team

---

## ADR-001: Rebuild vs Refactor

### Context
The v4.0 orchestrator had grown to 2,468 lines with 10 phases and 5 LLM agents. This created:
- Long execution times (3-5 minutes per schedule)
- High token costs from excessive agent invocations
- Difficulty debugging phase-to-phase data flow
- Maintenance burden from complex interdependencies

### Decision
**Rebuild from scratch** with a minimal 3-phase architecture instead of incrementally refactoring v4.0.

### Rationale
1. **Clean slate enables optimal design**: Refactoring would carry forward v4's structural debt
2. **Clear separation of concerns**: Each phase has single responsibility
3. **Testability**: Smaller modules are easier to unit test
4. **Onboarding**: New engineers can understand 209 lines faster than 2,468

### Consequences
- **Positive**: 4x faster execution, 67% fewer agent calls
- **Negative**: Parallel maintenance of v4 and v5 during rollout
- **Risk**: New bugs in fresh code (mitigated by shadow mode validation)

---

## ADR-002: Three-Phase Pipeline Architecture

### Context
v4.0 used a 10-phase pipeline:
1. Preflight validation
2. Send type allocation
3. Caption selection
4. Timing optimization
5. Followup generation
6. Schedule assembly
7. Revenue optimization
8. Validation gate
9. (Plus phases 0.5 and 1 for analysis)

Many phases were deterministic and didn't require LLM reasoning.

### Decision
Consolidate into **3 phases**:
1. **Preflight** (deterministic Python): All context gathering and volume calculation
2. **Generator** (Sonnet agent): Schedule creation with full context
3. **Validator** (Opus agent): Hard gate enforcement and certificate generation

### Rationale
1. **Preflight is pure computation**: Volume tiers, pricing, timing slots are formula-based
2. **Generator has full context**: Can make coherent scheduling decisions
3. **Validator provides independence**: Re-fetches vault/AVOID for integrity

### Trade-offs
| Aspect | v4.0 (10 phases) | v1.0 (3 phases) |
|--------|------------------|-----------------|
| Granularity | Fine-grained control | Coarser control |
| Debugging | Phase-by-phase inspection | Fewer checkpoints |
| Flexibility | Easy to modify single phase | Changes affect whole phase |
| Performance | 50+ MCP calls, 5 agents | ~10 MCP calls, 2 agents |
| Maintainability | Complex dependencies | Clear boundaries |

### Consequences
- **Positive**: Dramatic simplification and speed improvement
- **Negative**: Less granular phase-by-phase debugging
- **Mitigation**: Comprehensive logging within each phase

---

## ADR-003: Deterministic Preflight Engine

### Context
v4.0 mixed deterministic computation with LLM reasoning in early phases, causing:
- Inconsistent results between runs
- Unnecessary token usage
- Slow execution

### Decision
Move all deterministic logic into `PreflightEngine`:
- Volume tier calculation
- Trigger detection
- Timing slot generation
- Health/death spiral detection
- Pricing configuration

### Rationale
1. **Reproducibility**: Same inputs → same context every time
2. **Performance**: Python is faster than LLM for formulas
3. **Cost**: Zero tokens for deterministic work
4. **Testability**: Unit tests for business logic

### Implementation Details
```python
class PreflightEngine:
    async def execute(self, creator_id, week_start) -> CreatorContext:
        # 7 parallel MCP calls
        # Pure Python computation
        # Returns immutable context
```

### Consequences
- **Positive**: Preflight completes in ~500ms (was 30-60s)
- **Positive**: 100% testable business logic
- **Negative**: Logic changes require code deployment (not prompt changes)

---

## ADR-004: Agent Model Selection

### Context
Need to choose models for Generator and Validator agents balancing:
- Quality of output
- Execution speed
- Token cost

### Decision
- **Generator**: Sonnet (fast, good enough for schedule creation)
- **Validator**: Opus (highest quality for critical gate enforcement)

### Rationale
| Phase | Model | Reasoning |
|-------|-------|-----------|
| Generator | Sonnet | Creative task, speed matters, quality acceptable |
| Validator | Opus | Critical safety gate, accuracy paramount |

### Cost/Performance Analysis
| Model | Speed | Quality | Cost |
|-------|-------|---------|------|
| Haiku | Fastest | Lower | Lowest |
| Sonnet | Fast | Good | Medium |
| Opus | Slower | Highest | Higher |

Generator uses Sonnet because:
- Schedule creation benefits from speed
- Full context provided by Preflight
- Validator catches quality issues

Validator uses Opus because:
- Hard gate violations are expensive (bad schedules)
- Independent verification requires highest accuracy
- Quality score impacts production decisions

### Consequences
- **Positive**: Balanced cost/quality trade-off
- **Positive**: Critical path protected by best model
- **Trade-off**: Validator is slower but more reliable

---

## ADR-005: Feature Flag-Based Migration

### Context
Need to migrate 37 active creators from v4 to v5 without disruption.

### Decision
Implement comprehensive feature flag system:
1. Global kill switch
2. Per-creator allowlist
3. Percentage rollout
4. Shadow mode
5. Automatic fallback

### Rationale
1. **Safety**: Can disable v5 instantly
2. **Gradual**: Test with low-risk creators first
3. **Validation**: Shadow mode proves equivalence
4. **Recovery**: Auto-rollback prevents extended outages

### Flag Hierarchy
```
EROS_V5_ENABLED=false → All traffic to v4
                │
                ▼ true
EROS_V5_SHADOW_MODE=true → Both, return v4
                │
                ▼ false
EROS_V5_CREATORS contains creator → v5
                │
                ▼ no
hash(creator) < EROS_V5_PERCENTAGE → v5
                │
                ▼ no
Default → v4
```

### Consequences
- **Positive**: Zero-risk rollout capability
- **Positive**: A/B comparison data
- **Negative**: Additional complexity in routing
- **Negative**: Maintaining both pipelines during rollout

---

## ADR-006: Shadow Mode Comparison

### Context
Need confidence that v5 produces equivalent schedules before live traffic.

### Decision
Implement shadow mode that:
1. Runs both pipelines in parallel
2. Returns v4 result (production safe)
3. Logs detailed comparison
4. Tracks aggregate metrics

### Comparison Metrics
| Metric | Weight | Pass Criteria |
|--------|--------|---------------|
| Hard gate compliance | Critical | v5 passes all v4 passes |
| Quality score | High | v5 >= v4 - 5 |
| Item count | Medium | v5 within ±10% |
| Execution time | Info | v5 ideally faster |

### Rationale
1. **Safety**: Production unaffected during validation
2. **Data-driven**: Objective comparison, not subjective review
3. **Regression detection**: Catches quality drops before live traffic
4. **Performance baseline**: Proves speed improvement

### Consequences
- **Positive**: High confidence before cutover
- **Positive**: Quantifiable improvement metrics
- **Negative**: 2x resource usage during shadow mode
- **Mitigation**: Shadow mode is temporary (Week 1 only)

---

## ADR-007: Automated Rollback

### Context
Need fast recovery if v5 causes issues in production.

### Decision
Implement automated rollback with:
1. SLO-based triggers
2. Graceful drain of in-flight requests
3. Instant flag toggle
4. Automatic alerting

### Rollback Triggers
| Condition | Threshold | Window |
|-----------|-----------|--------|
| Success rate | < 85% | 5 min |
| P95 latency | > 180s | 3 runs |
| Hard gate rate | > 10% | 10 runs |
| Quality avg | < 70 | 10 runs |

### Rationale
1. **Speed**: Automated response faster than manual intervention
2. **Consistency**: Objective thresholds, not human judgment
3. **Safety**: Graceful drain prevents orphaned requests
4. **Visibility**: Automatic alerting ensures awareness

### Consequences
- **Positive**: Sub-minute recovery from failures
- **Positive**: Reduced on-call burden
- **Negative**: Risk of false positive rollbacks
- **Mitigation**: Conservative thresholds, require sustained violations

---

## ADR-008: Immutable CreatorContext

### Context
Need to pass rich context from Preflight to Generator and Validator.

### Decision
Use frozen dataclass for `CreatorContext`:
```python
@dataclass(frozen=True, slots=True)
class CreatorContext:
    creator_id: str
    vault_types: tuple[str, ...]  # Immutable collections
    volume_config: dict  # Consider making this frozen too
    ...
```

### Rationale
1. **Thread safety**: Immutable data safe for parallel access
2. **Debugging**: Context cannot change after creation
3. **Caching**: Hashable for potential caching
4. **API contract**: Clear what data flows between phases

### Trade-offs
- **Positive**: Eliminates mutation bugs
- **Negative**: Cannot update context without recreation
- **Acceptable**: Phases shouldn't modify context anyway

---

## ADR-009: Production Adapters with Retry

### Context
v5 needs to interface with existing MCP tools and Task tool.

### Decision
Create adapter layer with:
1. Protocol-compliant interfaces
2. Exponential backoff retry
3. Configurable timeouts
4. Request tracing

### Implementation
```python
class ProductionMCPClient:
    @with_retry(RetryConfig(max_retries=3, base_delay=1.0))
    async def get_creator_profile(self, creator_id: str) -> dict:
        return await self._call("get_creator_profile", creator_id=creator_id)
```

### Rationale
1. **Resilience**: Transient failures don't break pipeline
2. **Observability**: Trace IDs for debugging
3. **Flexibility**: Configurable retry behavior
4. **Compatibility**: Wraps existing tools without modification

### Consequences
- **Positive**: More robust in production
- **Positive**: Easy to swap implementations
- **Negative**: Additional layer of abstraction
- **Acceptable**: Abstraction provides valuable guarantees

---

## Summary of Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Approach | Rebuild | Clean design vs. tech debt |
| Phases | 3 | Minimal necessary |
| Deterministic | Preflight | Speed and reproducibility |
| Generator model | Sonnet | Fast, good quality |
| Validator model | Opus | Critical accuracy |
| Migration | Feature flags | Safe rollout |
| Validation | Shadow mode | Prove equivalence |
| Recovery | Auto-rollback | Fast recovery |
| Context | Immutable | Thread safety |
| Integration | Adapters | Resilience |

---

## Future Considerations

1. **Further optimization**: Could Preflight be cached across runs?
2. **Model evolution**: As models improve, reassess Generator/Validator choices
3. **Feature flag consolidation**: Remove after stable rollout
4. **v4 deprecation**: Plan removal after 30 days stable
