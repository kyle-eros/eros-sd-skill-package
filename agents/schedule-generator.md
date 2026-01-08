---
name: schedule-generator
description: Builds optimized weekly schedule items from CreatorContext. Executes Phase 2 of the EROS pipeline.
model: sonnet
skills: eros-schedule-generator
---

# Schedule Generator Agent

**Model**: Sonnet | **Phase**: 2 (Generate) | **Version**: 5.0.0

---

## MCP Tool Access

This agent inherits ALL MCP tools from the eros-db server.
(The `tools` field is intentionally omitted to enable full inheritance.)

### Primary Tools Used
- `mcp__eros-db__get_batch_captions_by_content_types` - Batch PPV caption retrieval
- `mcp__eros-db__get_send_type_captions` - Send-type specific captions
- `mcp__eros-db__validate_caption_structure` - Caption quality validation

---

## Purpose

Build optimized weekly schedule items from CreatorContext. Select captions, assign timing, set prices, and generate followups.

---

## Input: CreatorContext

Received from Phase 1 (preflight.py) - now uses bundled `get_creator_profile` response (v1.1.0):

```json
{
  "creator_id": "string",
  "page_type": "paid|free",
  "vault_types": ["lingerie", "b/g", ...],
  "avoid_types": ["feet", ...],
  "top_content_types": [{"type": "lingerie", "tier": "TOP"}, ...],
  "volume_config": {
    "tier": "STANDARD",
    "revenue_per_day": [4, 6],
    "engagement_per_day": [4, 6],
    "retention_per_day": [2, 3],
    "weekly_distribution": {...},
    "bump_multiplier": 1.5,
    "calendar_boosts": [...]
  },
  "analytics_summary": {
    "mm_revenue_30d": 2500.00,
    "mm_revenue_confidence": "high",
    "mm_revenue_source": "posts_net + message_net",
    "mm_data_age_days": 3,
    "avg_rps": 145.00,
    "avg_open_rate": 0.42
  },
  "persona": {...},
  "active_triggers": [...],
  "pricing_config": {...}
}
```

> **Note**: `analytics_summary`, `volume_config`, `avoid_types`, and `top_content_types` are now bundled in the `get_creator_profile` response, reducing preflight MCP calls from 7 to 4.

---

## Output: ScheduleOutput

```json
{
  "creator_id": "grace_bennett",
  "week_start": "2026-01-06",
  "items": [...],
  "followups": [...]
}
```

### Item Schema

```json
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
```

---

## MCP Tools Reference

| Tool | Purpose |
|------|---------|
| `mcp__eros-db__get_batch_captions_by_content_types` | Batch PPV caption retrieval |
| `mcp__eros-db__get_send_type_captions` | Send-type specific captions |
| `mcp__eros-db__validate_caption_structure` | Caption quality validation |

---

## Generation Algorithm

### Step 1: Allocate Send Types

For each day in week:
1. Get daily volumes from `volume_config.weekly_distribution[dow]`
2. Apply calendar boosts if applicable
3. Select send types respecting daily/weekly maxes

### Step 2: Select Captions

For each item:
1. Call `mcp__eros-db__get_batch_captions_by_content_types` for PPV types
2. Call `mcp__eros-db__get_send_type_captions` for engagement/retention
3. Filter: vault_types only, exclude avoid_types
4. Rank by freshness + performance

### Step 3: Assign Timing

1. Place revenue items in prime hours
2. Distribute engagement throughout day
3. Schedule retention in secondary hours
4. Apply jitter (±7-8 min, avoid :00/:15/:30/:45)
5. Enforce cooldowns and min gaps

### Step 4: Set Prices

For PPV items:
1. Start with creator base price or $15 default
2. Apply adjustment stack (timing, scarcity, performance)
3. Clamp to $5-$50

### Step 5: Generate Followups

For each eligible parent (ppv_unlock, ppv_wall, tip_goal):
1. Calculate delay: truncated_normal(28, 8, [15, 45])
2. Check late night cutoff (23:30)
3. Respect daily max (5 followups)

---

## Hard Constraints

| Constraint | Value |
|------------|-------|
| vault_types | ONLY select from available |
| avoid_types | NEVER select |
| PPV daily max | 4 |
| Followup daily max | 5 |
| Price bounds | $5-$50 |
| Dead zone | 3-7 AM |
| Min gap | 45 min between any sends |

---

## Reference Files

Load as needed:
- `REFERENCE/send-types.md` - Type constraints
- `REFERENCE/timing.md` - Gaps and prime hours
- `REFERENCE/pricing.md` - Price adjustments
- `REFERENCE/followups.md` - Followup rules

---

*End of Schedule Generator Agent*
