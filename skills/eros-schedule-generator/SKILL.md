---
name: eros-schedule-generator
description: Generate optimized weekly schedules for OnlyFans creators. Invoke PROACTIVELY for schedule generation, PPV optimization, or content planning requests.
version: 5.2.0
allowed-tools: mcp__eros-db__get_creator_profile, mcp__eros-db__get_volume_config, mcp__eros-db__get_allowed_content_types, mcp__eros-db__get_content_type_rankings, mcp__eros-db__get_persona_profile, mcp__eros-db__get_active_volume_triggers, mcp__eros-db__get_performance_trends, mcp__eros-db__get_batch_captions_by_content_types, mcp__eros-db__get_send_type_captions, mcp__eros-db__save_schedule, mcp__eros-db__save_volume_triggers, mcp__eros-db__get_active_creators, mcp__eros-db__validate_caption_structure, mcp__eros-db__get_send_types
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

## MCP Server: eros-db

This skill uses the `eros-db` MCP server for database access.

**Tool Naming**: All tools use format `mcp__eros-db__<tool-name>`

### Verify MCP Connection
Before using tools:
1. Run `/mcp status`
2. Confirm `eros-db` shows as "connected"
3. If not connected, restart Claude Code session

### Available Tools (14 total)

| Tool | Category | Description | GATE |
|------|----------|-------------|------|
| `mcp__eros-db__get_creator_profile` | Creator | **Bundled**: Profile + analytics + volume + rankings | |
| `mcp__eros-db__get_active_creators` | Creator | Paginated list with tier/revenue filters | |
| `mcp__eros-db__get_allowed_content_types` | Creator | Allowed content types | HARD |
| `mcp__eros-db__get_content_type_rankings` | Creator | Performance tiers (also in bundled) | HARD |
| `mcp__eros-db__get_persona_profile` | Creator | Tone/archetype settings | |
| `mcp__eros-db__get_volume_config` | Schedule | Tier and daily volumes (also in bundled) | |
| `mcp__eros-db__get_active_volume_triggers` | Schedule | Performance triggers | |
| `mcp__eros-db__get_performance_trends` | Schedule | Health/saturation metrics | |
| `mcp__eros-db__save_schedule` | Schedule | Persist with certificate | |
| `mcp__eros-db__save_volume_triggers` | Schedule | Persist triggers | |
| `mcp__eros-db__get_batch_captions_by_content_types` | Caption | Batch PPV retrieval | |
| `mcp__eros-db__get_send_type_captions` | Caption | Send-type specific | |
| `mcp__eros-db__validate_caption_structure` | Caption | Anti-patterization | |
| `mcp__eros-db__get_send_types` | Config | 22-type taxonomy | |

### Tool Usage by Phase

**Phase 1 - Preflight** (4 MCP calls via bundled response):
- `mcp__eros-db__get_creator_profile` - **Bundled**: Profile + analytics + volume + rankings (replaces 3 separate calls)
- `mcp__eros-db__get_allowed_content_types` - Allowed content types (HARD GATE)
- `mcp__eros-db__get_persona_profile` - Caption styling
- `mcp__eros-db__get_active_volume_triggers` - Performance triggers

**Phase 2 - Generate** (3 tools):
- `mcp__eros-db__get_batch_captions_by_content_types` - PPV captions
- `mcp__eros-db__get_send_type_captions` - Engagement captions
- `mcp__eros-db__validate_caption_structure` - Quality check

**Phase 3 - Validate** (3 tools):
- `mcp__eros-db__get_allowed_content_types` - Re-verify allowed types (HARD GATE)
- `mcp__eros-db__get_content_type_rankings` - Re-verify HARD GATE
- `mcp__eros-db__save_schedule` - Persist with certificate

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
| `creator_id` | string | `mcp__eros-db__get_creator_profile` |
| `page_type` | "paid" \| "free" | `mcp__eros-db__get_creator_profile` |
| `allowed_types` | string[] | `mcp__eros-db__get_allowed_content_types` |
| `avoid_types` | string[] | `mcp__eros-db__get_content_type_rankings` |
| `top_content_types` | {type, tier}[] | `mcp__eros-db__get_content_type_rankings` |
| `volume_config` | VolumeConfig | `mcp__eros-db__get_volume_config` |
| `persona` | Persona | `mcp__eros-db__get_persona_profile` |
| `active_triggers` | Trigger[] | `mcp__eros-db__get_active_volume_triggers` |
| `pricing_config` | PricingConfig | `mcp__eros-db__get_creator_profile` |

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

### Phase 1: Preflight (4 MCP calls)

| Tool | Purpose |
|------|---------|
| `mcp__eros-db__get_creator_profile` | **Bundled**: Profile + analytics + volume + rankings (43% reduction from 7 to 4 calls) |
| `mcp__eros-db__get_allowed_content_types` | Allowed content types (HARD GATE) |
| `mcp__eros-db__get_persona_profile` | Tone, archetype, voice |
| `mcp__eros-db__get_active_volume_triggers` | Performance-based adjustments |

> **Note**: `get_creator_profile` now includes `analytics_summary`, `volume_assignment`, `top_content_types`, `avoid_types`, and `top_types` by default. Set `include_analytics=False`, `include_volume=False`, or `include_content_rankings=False` to disable bundling.

### Phase 2: Generator (3 tools)

| Tool | Purpose |
|------|---------|
| `mcp__eros-db__get_batch_captions_by_content_types` | Batch PPV caption retrieval |
| `mcp__eros-db__get_send_type_captions` | Send-type specific captions |
| `mcp__eros-db__validate_caption_structure` | Caption quality validation |

### Phase 3: Validator (3 tools)

| Tool | Purpose |
|------|---------|
| `mcp__eros-db__get_allowed_content_types` | Re-verify allowed content types |
| `mcp__eros-db__get_content_type_rankings` | Re-verify AVOID exclusion |
| `mcp__eros-db__save_schedule` | Persist with ValidationCertificate |

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
