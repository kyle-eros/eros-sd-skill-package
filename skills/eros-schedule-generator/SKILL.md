---
name: eros-schedule-generator
description: Generate optimized weekly schedules for OnlyFans creators. Invoke PROACTIVELY for schedule generation, PPV optimization, or content planning requests.
version: 5.1.0
allowed-tools: get_creator_profile, get_volume_config, get_vault_availability, get_content_type_rankings, get_persona_profile, get_active_volume_triggers, get_performance_trends, get_batch_captions_by_content_types, get_send_type_captions, save_schedule, save_volume_triggers
triggers:
  - generate schedule
  - weekly schedule
  - content plan
  - PPV optimization
  - schedule for [creator]
---

# EROS Schedule Generator v1.0

## Activation Protocol (REQUIRED)

**Before generating ANY schedule, complete this checklist:**

Step 1 - EVALUATE: Is this an EROS task?
- [ ] Involves OnlyFans schedule generation?
- [ ] Mentions PPV, captions, timing, or pricing?
- [ ] References a creator by name?

Step 2 - LOAD LEARNINGS: Read `LEARNINGS.md` NOW
- [ ] Check HIGH confidence corrections (mandatory compliance)
- [ ] Review MEDIUM confidence patterns (prefer these approaches)

Step 3 - LOAD REFERENCES: Based on task, read relevant files:
- [ ] `REFERENCE/SEND_TYPES.md` for allocation
- [ ] `REFERENCE/TIMING_RULES.md` for scheduling
- [ ] `REFERENCE/PRICING_RULES.md` for PPV prices

**CRITICAL**: The evaluation is WORTHLESS unless you LOAD the learnings.
Skipping Step 2 will repeat past mistakes.

---

## What This Does

Generates 35-40 optimized sends per week for OnlyFans creators, balancing revenue (PPV), engagement (bumps/promos), and retention (renewals).

## Three-Phase Pipeline

| Phase | Executor | Purpose | Can Block |
|-------|----------|---------|-----------|
| 1. Preflight | Python (deterministic) | Gather all creator context | YES |
| 2. Generate | Sonnet Agent | Build schedule items | NO |
| 3. Validate | Opus Agent | Enforce hard gates | YES |

### Execution Flow

```
preflight.py --> CreatorContext --> generator-agent --> ScheduleOutput --> validator-agent --> ValidationCertificate --> save_schedule
```

---

## Quick Start

```bash
# Step 1: Run preflight (deterministic)
python python/preflight.py --creator grace_bennett --week 2026-01-06

# Step 2: Invoke generator agent with CreatorContext output
# Step 3: Invoke validator agent with ScheduleOutput
# Step 4: If APPROVED, call save_schedule with ValidationCertificate
```

---

## CreatorContext (Preflight Output)

| Field | Type | Source MCP Tool |
|-------|------|-----------------|
| `creator_id` | string | `get_creator_profile` |
| `page_type` | "paid" \| "free" | `get_creator_profile` |
| `vault_types` | string[] | `get_vault_availability` |
| `avoid_types` | string[] | `get_content_type_rankings` |
| `top_content_types` | {type, tier}[] | `get_content_type_rankings` |
| `volume_config` | VolumeConfig | `get_volume_config` |
| `persona` | Persona | `get_persona_profile` |
| `active_triggers` | Trigger[] | `get_active_volume_triggers` |
| `pricing_config` | PricingConfig | `get_creator_profile` |

### VolumeConfig Shape

```json
{
  "tier": "STANDARD",
  "revenue_per_day": [4, 6],
  "engagement_per_day": [4, 6],
  "retention_per_day": [2, 3],
  "weekly_distribution": { "monday": {...}, ... },
  "bump_multiplier": 1.5,
  "calendar_boosts": [{ "date": "2026-01-15", "multiplier": 1.2 }]
}
```

---

## ScheduleOutput (Generator Output)

```json
{
  "creator_id": "grace_bennett",
  "week_start": "2026-01-06",
  "items": [
    {
      "send_type_key": "ppv_unlock",
      "caption_id": 12345,
      "content_type": "lingerie",
      "scheduled_date": "2026-01-06",
      "scheduled_time": "19:23",
      "price": 15.00,
      "flyer_required": 1,
      "channel_key": "mass_message"
    }
  ],
  "followups": [
    {
      "parent_item_index": 0,
      "send_type_key": "ppv_followup",
      "scheduled_time": "19:51",
      "delay_minutes": 28
    }
  ]
}
```

---

## Hard Gates (Zero Tolerance)

| Gate | Check | Rejection Code |
|------|-------|----------------|
| **Vault** | content_type IN vault_types | `VAULT_VIOLATION` |
| **AVOID** | content_type NOT IN avoid_types | `AVOID_TIER_VIOLATION` |
| **Page Type** | send_type compatible with page_type | `PAGE_TYPE_VIOLATION` |
| **Diversity** | >= 10 unique send types, >= 4 revenue, >= 4 engagement | `INSUFFICIENT_DIVERSITY` |
| **Flyer** | flyer_required=1 for PPV/bundle types | `FLYER_REQUIREMENT_VIOLATION` |

### Page Type Restrictions

| Page Type | Cannot Use |
|-----------|------------|
| FREE | `tip_goal`, `renew_on_post`, `renew_on_message`, `expired_winback` |
| PAID | `ppv_wall` |

---

## MCP Tools by Phase

### Phase 1: Preflight (6 tools)

| Tool | Purpose |
|------|---------|
| `get_creator_profile` | Creator data + analytics |
| `get_volume_config` | Tier + daily volumes + DOW distribution |
| `get_vault_availability` | Available content types (HARD GATE) |
| `get_content_type_rankings` | TOP/MID/LOW/AVOID tiers (HARD GATE) |
| `get_persona_profile` | Tone, archetype, voice |
| `get_active_volume_triggers` | Performance-based adjustments |

### Phase 2: Generator (2 tools)

| Tool | Purpose |
|------|---------|
| `get_batch_captions_by_content_types` | Batch PPV caption retrieval |
| `get_send_type_captions` | Send-type specific captions |

### Phase 3: Validator (3 tools)

| Tool | Purpose |
|------|---------|
| `get_vault_availability` | Re-verify vault compliance |
| `get_content_type_rankings` | Re-verify AVOID exclusion |
| `save_schedule` | Persist with ValidationCertificate |

---

## When to Load References

| Topic | Reference File | Load When |
|-------|----------------|-----------|
| 22 send types | `REFERENCE/SEND_TYPES.md` | Building allocation |
| Timing rules | `REFERENCE/TIMING_RULES.md` | Scheduling times |
| Pricing rules | `REFERENCE/PRICING_RULES.md` | Setting PPV prices |
| Followup rules | `REFERENCE/FOLLOWUP_RULES.md` | Generating followups |
| Validation | `REFERENCE/VALIDATION_RULES.md` | Phase 3 validation |
| Volume tiers | `REFERENCE/VOLUME_TIERS.md` | Understanding config |

---

## Volume Tiers

| Tier | MM Revenue/Month | Revenue/Day | Engagement/Day | Retention/Day |
|------|------------------|-------------|----------------|---------------|
| MINIMAL | $0 - $149 | 1-2 | 1-2 | 1 |
| LITE | $150 - $799 | 2-4 | 2-4 | 1-2 |
| STANDARD | $800 - $2,999 | 4-6 | 4-6 | 2-3 |
| HIGH_VALUE | $3,000 - $7,999 | 6-9 | 5-8 | 2-4 |
| PREMIUM | $8,000+ | 8-12 | 6-10 | 3-5 |

---

## Send Type Categories

### Revenue (9 types)

`ppv_unlock`, `ppv_wall`, `tip_goal`, `bundle`, `flash_bundle`, `vip_program`, `game_post`, `snapchat_bundle`, `first_to_tip`

### Engagement (9 types)

`link_drop`, `wall_link_drop`, `bump_normal`, `bump_descriptive`, `bump_text_only`, `bump_flyer`, `dm_farm`, `like_farm`, `live_promo`

### Retention (4 types)

`renew_on_post`, `renew_on_message`, `ppv_followup`, `expired_winback`

---

## Key Constraints

| Constraint | Value |
|------------|-------|
| PPV daily max | 4 |
| Followup daily max | 5 |
| Followup delay | 15-45 min (optimal: 28) |
| VIP program weekly max | 1 |
| Snapchat bundle weekly max | 1 |
| Dead zone | 3-7 AM (shift to 11 PM or 7 AM) |
| Min gap between any sends | 45 min |
| Price floor | $5.00 |
| Price ceiling | $50.00 |

---

## Cooldown Matrix (Hours Between Categories)

| From / To | REVENUE | ENGAGEMENT | RETENTION |
|-----------|---------|------------|-----------|
| REVENUE | 4h | 1h | 2h |
| ENGAGEMENT | 4h | 1h | 1h |
| RETENTION | 2h | 1h | 4h |

---

## ValidationCertificate (Required for save_schedule)

```json
{
  "certificate_version": "3.0",
  "creator_id": "grace_bennett",
  "validation_timestamp": "2026-01-05T14:30:00Z",
  "schedule_hash": "sha256:abc123...",
  "items_validated": 54,
  "quality_score": 87,
  "validation_status": "APPROVED",
  "checks_performed": {
    "vault_compliance": true,
    "avoid_tier_exclusion": true,
    "send_type_diversity": true,
    "timing_validation": true
  },
  "violations_found": { "vault": 0, "avoid_tier": 0, "critical": 0 }
}
```

### Quality Score Thresholds

| Score | Status | Action |
|-------|--------|--------|
| 85-100 | APPROVED | Save and deploy |
| 75-84 | APPROVED | Proceed with recommendations |
| 60-74 | NEEDS_REVIEW | Flag for human review |
| < 60 | REJECTED | Return to generator |

---

## Error Handling

| Error Code | Phase | Action |
|------------|-------|--------|
| `VAULT_VIOLATION` | Validate | REJECT - reselect caption |
| `AVOID_TIER_VIOLATION` | Validate | REJECT - exclude content type |
| `PAGE_TYPE_VIOLATION` | Validate | REJECT - remove incompatible send |
| `INSUFFICIENT_DIVERSITY` | Validate | REJECT - add more send types |
| `FLYER_REQUIREMENT_VIOLATION` | Validate | REJECT - set flyer_required=1 |
| `PRICE_OUTLIER` | Validate | REJECT - adjust to $5-$50 |
| `TIME_CONFLICT` | Validate | REJECT - resolve collision |

---

## Calendar Awareness

| Event Type | Multiplier | Days |
|------------|------------|------|
| Payday | +20% | 1st, 15th, last of month |
| Holiday | +30% | Valentine's, July 4th, Halloween, Christmas |
| Overlap | Max multiplier | When payday + holiday coincide |

---

## Self-Improvement Protocol

### Learning Sources

| Source | Signal Type | Confidence | Latency |
|--------|-------------|------------|---------|
| Hard gate violation | Correction | HIGH | Immediate |
| User correction | Correction | HIGH | Immediate |
| Quality score >= 85 | Pattern | MEDIUM | Immediate |
| User approval | Pattern | MEDIUM | Immediate |
| RPS > median | Pattern | MEDIUM | 7-14 days |
| Conversion > baseline | Pattern | MEDIUM | 7-14 days |

### Feedback Capture

After each schedule generation:
1. **Automatic**: Validation results captured to LEARNINGS.md
2. **Manual**: User corrections captured when acknowledged

### Reflection Schedule

| Frequency | Action | Trigger |
|-----------|--------|---------|
| Per-session | Capture feedback | Automatic |
| On-demand | `/reflect` command | Manual |
| Weekly | Consolidate learnings | Cron/manual |
| Monthly | Promote patterns to SKILL.md | Review |

### Learning Integration

**HIGH confidence learnings**: MUST be followed (they're corrections)
**MEDIUM confidence learnings**: SHOULD be followed (they worked before)
**LOW confidence learnings**: MAY inform decisions (still testing)

See `LEARNINGS.md` for current accumulated knowledge.

---

## Related Files

| File | Purpose |
|------|---------|
| `python/preflight.py` | Phase 1 executor |
| `agents/generator.md` | Phase 2 agent definition |
| `agents/validator.md` | Phase 3 agent definition |
| `DOMAIN_KNOWLEDGE.md` | Complete domain rules |
| `LEARNINGS.md` | Accumulated corrections and patterns |
