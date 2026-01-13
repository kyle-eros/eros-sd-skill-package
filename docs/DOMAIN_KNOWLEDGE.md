# EROS Domain Knowledge Extract

**Version**: 5.1.0 | **Extracted**: 2026-01-05 | **Target**: v5 Pipeline Rebuild

---

## 1. The 22 Send Types

### Revenue Types (9)

| Key | Page Type | Daily Max | Weekly Max | Min Gap | Requires Media | Requires Price |
|-----|-----------|-----------|------------|---------|----------------|----------------|
| `ppv_unlock` | both | 4 | - | 2h | YES | YES |
| `ppv_wall` | FREE only | 3 | - | 3h | YES | YES |
| `tip_goal` | PAID only | 2 | - | 4h | NO | YES |
| `bundle` | both | 1 | - | 3h | YES | YES |
| `flash_bundle` | both | 1 | - | 6h | YES | YES |
| `vip_program` | both | 1 | 1 | 24h | NO | NO |
| `game_post` | both | 1 | - | 4h | NO | NO |
| `snapchat_bundle` | both | 1 | 1 | 24h | YES | NO |
| `first_to_tip` | both | 1 | - | 6h | NO | NO |

### Engagement Types (9)

| Key | Page Type | Daily Max | Min Gap | Requires Media |
|-----|-----------|-----------|---------|----------------|
| `link_drop` | both | 2 | 2h | NO |
| `wall_link_drop` | both | 2 | 3h | YES |
| `bump_normal` | both | 3 | 1h | NO |
| `bump_descriptive` | both | 2 | 2h | NO |
| `bump_text_only` | both | 2 | 2h | NO |
| `bump_flyer` | both | 2 | 4h | YES |
| `dm_farm` | both | 2 | 4h | NO |
| `like_farm` | both | 1 | 24h | NO |
| `live_promo` | both | 2 | 2h | YES |

### Retention Types (4)

| Key | Page Type | Daily Max | Min Gap | Notes |
|-----|-----------|-----------|---------|-------|
| `renew_on_post` | PAID only | 2 | 12h | Subscription renewal via post |
| `renew_on_message` | PAID only | 1 | 24h | Subscription renewal via DM |
| `ppv_followup` | both | 5 | 1h | Auto-generated 15-45min after parent PPV |
| `expired_winback` | PAID only | 1 | 24h | Win back expired subscribers |

### Page Type Restrictions

- **FREE pages**: Cannot use `tip_goal`, `renew_on_post`, `renew_on_message`, `expired_winback`
- **PAID pages**: Cannot use `ppv_wall`

---

## 2. Volume Tiers

> **Implementation Note**: Canonical tier thresholds are defined in
> `mcp_server/volume_utils.py`. All consumers (`get_volume_config`,
> `get_creator_profile`, `preflight.py`) import from this single source of truth.
> This eliminates the risk of threshold drift between components.

### Revenue-Based Tiers (MM Revenue = posts_net + message_net)

| Tier | MM Revenue/Month | Revenue/Day | Engagement/Day | Retention/Day |
|------|------------------|-------------|----------------|---------------|
| MINIMAL | $0 - $149 | 1-2 | 1-2 | 1 |
| LITE | $150 - $799 | 2-4 | 2-4 | 1-2 |
| STANDARD | $800 - $2,999 | 4-6 | 4-6 | 2-3 |
| HIGH_VALUE | $3,000 - $7,999 | 6-9 | 5-8 | 2-4 |
| PREMIUM | $8,000+ | 8-12 | 6-10 | 3-5 |

### Fallback for New Creators

```
IF monthly_revenue is NULL:
    estimated_revenue = fan_count * $2.50
```

### Tier Smoothing (Always Active)

Logarithmic interpolation at tier boundaries (±10% zone):
- MINIMAL→LITE: $135-$165
- LITE→STANDARD: $720-$880
- STANDARD→HIGH_VALUE: $2,700-$3,300
- HIGH_VALUE→PREMIUM: $7,200-$8,800

### Tier Hysteresis

15% buffer prevents tier flip-flopping near boundaries.

---

## 3. Hard Gates (Zero Tolerance)

### Gate 1: Vault Compliance

```
FOR item in schedule:
    IF item.content_type NOT IN vault_matrix.available_types:
        REJECT("VAULT_VIOLATION")
```

### Gate 2: AVOID Tier Exclusion

```python
# v1.4.0: Use pre-computed avoid_types and metadata hashes
rankings = mcp__eros-db__get_content_type_rankings(creator_id)
avoid_types = rankings["avoid_types"]  # Pre-computed list
avoid_hash = rankings["metadata"]["avoid_types_hash"]  # For ValidationCertificate
FOR item IN schedule.items:
    IF item.content_type IN avoid_types: REJECT("AVOID_TIER_VIOLATION")
```

### Gate 3: Page Type Restrictions

```
IF page_type == 'free' AND send_type == 'tip_goal':
    REJECT("PAGE_TYPE_VIOLATION")
IF page_type == 'paid' AND send_type == 'ppv_wall':
    REJECT("PAGE_TYPE_VIOLATION")
IF page_type == 'free' AND send_type IN ['renew_on_post', 'renew_on_message', 'expired_winback']:
    REJECT("PAGE_TYPE_VIOLATION")
```

### Gate 4: Send Type Diversity

| Metric | Threshold | Severity |
|--------|-----------|----------|
| Total unique send_type_keys | >= 10 | HARD REJECT |
| Unique revenue types | >= 4 | HARD REJECT |
| Unique engagement types | >= 4 | HARD REJECT |
| Unique retention types (paid) | >= 2 | HARD REJECT |

### Gate 5: Flyer Requirement

```
FLYER_REQUIRED = ['ppv_unlock', 'ppv_wall', 'bundle', 'flash_bundle',
                  'vip_program', 'snapchat_bundle', 'first_to_tip',
                  'bump_flyer', 'live_promo']

IF send_type IN FLYER_REQUIRED AND flyer_required != 1:
    REJECT("FLYER_REQUIREMENT_VIOLATION")
```

---

## 4. Pricing Rules

### Hard Bounds

| Bound | Value |
|-------|-------|
| Floor | $5.00 |
| Ceiling | $50.00 |
| Default | Creator base price OR $15.00 |

### Adjustment Stack (Multiplicative)

```
final_price = base_price * (1 + sum(adjustments))
final_price = clamp($5.00, round(final_price), $50.00)
```

| Adjustment Type | Range | Trigger |
|-----------------|-------|---------|
| Prediction Bonus | +10-25% | predicted_rps > median_rps |
| Time Premium | +15% | Weekend evening (Fri-Sun, 6-10 PM) |
| Time Discount | -10% | Weekday morning (Mon-Fri, 6-10 AM) |
| Scarcity Premium | +20% | Content type unused 14+ days |
| Performance Premium | +15% | TOP tier content type |
| Freshness Premium | +10% | Caption never used before |
| Bundle Discount | -15% | Part of multi-PPV bundle |

### Prediction Bonus Thresholds

```
IF confidence_score < 0.6: skip prediction adjustment
IF predicted_rps > median * 1.5: +25%
IF predicted_rps > median * 1.2: +15%
IF predicted_rps > median: +10%
IF predicted_rps < median * 0.7: -10%
```

### Skip Optimization When

- `fan_count < 1000`
- Active A/B price experiments running
- Content type in AVOID tier

---

## 5. Timing Rules

### Jitter Algorithm

```
JITTER_MIN = -7 minutes
JITTER_MAX = +8 minutes
ROUND_MINUTES = {0, 15, 30, 45}  # NEVER land on these

jitter = random.randint(-7, +8)
WHILE (base_minute + jitter) % 15 == 0:
    jitter = random.randint(-7, +8)
```

### Minimum Gap Between Same Send Type

| Send Type | Min Gap |
|-----------|---------|
| ppv_unlock | 2h |
| ppv_wall | 3h |
| tip_goal | 4h |
| vip_program | 24h |
| game_post | 4h |
| bundle | 3h |
| flash_bundle | 6h |
| snapchat_bundle | 24h |
| first_to_tip | 6h |
| link_drop | 2h |
| wall_link_drop | 3h |
| bump_normal | 1h |
| bump_descriptive | 2h |
| bump_text_only | 2h |
| bump_flyer | 4h |
| dm_farm | 4h |
| like_farm | 24h |
| live_promo | 2h |
| renew_on_post | 12h |
| renew_on_message | 24h |
| ppv_followup | 1h |
| expired_winback | 24h |

### DOW Prime Hours (EST)

| Day | Prime Hours | Secondary |
|-----|-------------|-----------|
| Mon | 12-2pm, 7-10pm | 10-11am |
| Tue | 12-2pm, 8-11pm | 10-11am |
| Wed | 12-2pm, 8-11pm | 6-7pm |
| Thu | 12-2pm, 8-11pm | 6-7pm |
| Fri | 12-2pm, 9pm-12am | 5-7pm |
| Sat | 11am-2pm, 10pm-1am | 4-6pm |
| Sun | 11am-2pm, 8-11pm | 4-6pm |

### Dead Zone: 3-7 AM

```
IF 3 <= hour < 5:
    shift to previous day 11 PM
IF 5 <= hour < 7:
    shift to same day 7 AM
```

### Collision Resolution

```
PRIORITY_ORDER = [ppv_unlock, ppv_followup, other_revenue, engagement, retention]
INCREMENT = 5 minutes
MAX_OFFSET = 15 minutes
MIN_GAP_BETWEEN_ANY = 45 minutes
```

---

## 6. Followup Rules

### Eligible Parent Types

| Parent Type | Followup Type | Channel | Target |
|-------------|---------------|---------|--------|
| ppv_unlock | ppv_followup | targeted_message | ppv_non_purchasers |
| ppv_wall | ppv_followup | targeted_message | ppv_non_purchasers |
| tip_goal | ppv_followup | targeted_message | tip_goal_non_tippers |

### Timing Window

```
OPTIMAL_DELAY = 28 minutes (truncated normal distribution)
MIN_DELAY = 15 minutes (HARD)
MAX_DELAY = 45 minutes (HARD)
STD_DEV = 8 minutes

delay = truncated_normal(mean=28, std=8, min=15, max=45)
```

### Late Night Cutoff

```
CUTOFF = 23:30 (11:30 PM)

IF followup_time > 23:30:
    push to next day 08:00
```

### Daily Limit

```
MAX_FOLLOWUPS_PER_DAY = 5
```

### Constraints

- No cascading: followups cannot have followups
- Unique captions per day
- Must respect MIN_GAP (1h between followups)

---

## 7. Health Detection

### Death Spiral Detection

```sql
-- death_spiral_detection template
WITH weekly_metrics AS (
    SELECT
        week_number,
        SUM(total_earnings) AS weekly_earnings,
        AVG(view_rate) AS weekly_view_rate,
        AVG(conversion_rate) AS weekly_conv
    FROM mass_messages
    WHERE creator_id = :creator_id
    AND sent_date >= DATE('now', '-8 weeks')
    GROUP BY week_number
)
SELECT
    CASE
        WHEN COUNT(CASE WHEN weekly_earnings < LAG(weekly_earnings) OVER (ORDER BY week_number) THEN 1 END) >= 4
        THEN 'DEATH_SPIRAL'
        WHEN COUNT(CASE WHEN weekly_earnings < LAG(weekly_earnings) OVER (ORDER BY week_number) THEN 1 END) >= 2
        THEN 'WARNING'
        ELSE 'HEALTHY'
    END AS health_status
FROM weekly_metrics
```

### Thresholds

| Status | Condition |
|--------|-----------|
| HEALTHY | < 2 consecutive weeks declining |
| WARNING | 2-3 consecutive weeks declining |
| DEATH_SPIRAL | 4+ consecutive weeks declining |

### Saturation Detection

```
saturation_score = calculated from get_performance_trends(period='14d')

IF saturation_score > 70: reduce volume by 1 send/day
IF saturation_score < 30: opportunity to increase volume
```

---

## 8. Volume Triggers

### Trigger Types

| Type | Detection Criteria | Adjustment |
|------|-------------------|------------|
| HIGH_PERFORMER | RPS > $200 AND conversion > 6% | +20% |
| TRENDING_UP | Week-over-week RPS +15% | +10% |
| EMERGING_WINNER | RPS > $150 AND <3 uses/30d | +30% |
| SATURATING | Declining RPS 3+ consecutive days | -15% |
| AUDIENCE_FATIGUE | Open rate dropped -10%/7d | -25% |

### Trigger Schema

```json
{
    "content_type": "lingerie",
    "trigger_type": "HIGH_PERFORMER",
    "adjustment_multiplier": 1.20,
    "confidence": "high",
    "reason": "RPS $245, conversion 7.2%",
    "expires_at": "2026-01-12"
}
```

### Application

Triggers apply at Phase 2 (allocation) via `get_active_volume_triggers()`.

---

## 9. Validation Certificate

### Required Fields (v3.0)

```json
{
    "certificate_version": "3.0",
    "creator_id": "string",
    "validation_timestamp": "ISO8601",
    "schedule_hash": "sha256:...",
    "avoid_types_hash": "sha256:...",
    "vault_types_hash": "sha256:...",
    "items_validated": 54,
    "quality_score": 87,
    "validation_status": "APPROVED|NEEDS_REVIEW|REJECTED",
    "checks_performed": {
        "vault_compliance": true,
        "avoid_tier_exclusion": true,
        "send_type_diversity": true,
        "timing_validation": true,
        "caption_quality": true,
        "volume_config": true
    },
    "violations_found": {
        "vault": 0,
        "avoid_tier": 0,
        "critical": 0
    },
    "upstream_proof_verified": true,
    "certificate_signature": "vg-{hash8}-{timestamp}"
}
```

### Freshness Requirement

Certificate must be < 5 minutes old at save_schedule time.

### Quality Score Thresholds

| Score | Status | Action |
|-------|--------|--------|
| 85-100 | APPROVED | Save and deploy |
| 75-84 | APPROVED with notes | Proceed with recommendations |
| 60-74 | NEEDS_REVIEW | Flag for human review |
| < 60 | REJECTED | Return to previous phase |

---

## 10. Schedule Persistence

### save_schedule Workflow (v2.0.0)

1. **Input Validation** - creator_id required, week_start YYYY-MM-DD format
2. **Items Validation** - Required keys (send_type_key, scheduled_date, scheduled_time), format checks, $5-$50 price bounds
3. **Certificate Freshness** - Soft gate: 300s TTL + 30s tolerance, expired = draft status
4. **Database Operation** - Status-aware UPSERT with revision tracking

### Status Lifecycle

```
draft → approved → queued → completed
  ↓        ↓         ↓          ↓
UPSERT   UPSERT   LOCKED    LOCKED
```

| Status | Meaning | Modifiable |
|--------|---------|------------|
| draft | Initial save without certificate or with expired certificate | Yes |
| approved | Valid fresh certificate with APPROVED status | Yes |
| queued | Locked for execution (cannot modify) | No |
| completed | Historical record (immutable) | No |

### Error Codes

| Code | Cause | Resolution |
|------|-------|------------|
| CREATOR_NOT_FOUND | Invalid creator_id/page_name | Verify creator exists |
| VALIDATION_ERROR | Items failed structural validation | Fix item format |
| INVALID_DATE | week_start not YYYY-MM-DD | Use correct date format |
| SCHEDULE_LOCKED | Status is 'queued' | Wait for execution |
| SCHEDULE_COMPLETED | Status is 'completed' | Create new schedule |
| DATABASE_ERROR | SQLite operation failed | Check DB connection |

### Duplicate Handling (UPSERT)

When saving a schedule that already exists for the same creator_id + week_start:

- **draft** → Replaced with new schedule
- **approved** → Replaced with new schedule
- **queued** → Rejected with SCHEDULE_LOCKED
- **completed** → Rejected with SCHEDULE_COMPLETED

---

## 11. Essential MCP Tools

### Must Keep (15 Tools)

| Tool | Category | Purpose |
|------|----------|---------|
| `get_active_creators` | Creator | Paginated list with filters (tier, page_type, revenue) |
| `get_creator_profile` | Creator | **Bundled**: Profile + analytics + volume + rankings + vault + **persona** (v1.5.0) |
| `get_persona_profile` | Creator | Standalone persona access (management/debug only) |
| `get_allowed_content_types` | Creator | Allowed content types (HARD GATE) |
| `get_send_type_captions` | Caption | Send-type compatible captions |
| `get_batch_captions_by_content_types` | Caption | Batch PPV caption retrieval |
| `get_content_type_rankings` | Performance | TOP/MID/LOW/AVOID (HARD GATE) - v1.4.0: returns `rankings`, `avoid_types`, `metadata.rankings_hash`, `metadata.avoid_types_hash` |
| `get_performance_trends` | Performance | Saturation/opportunity |
| `get_dow_performance` | Performance | ALPHA/BETA/GAMMA classification |
| `get_send_types` | Config | Full 22-type taxonomy |
| `get_volume_config` | Config | Volume + DOW distribution |
| `get_active_volume_triggers` | Volume | Active performance triggers |
| `save_volume_triggers` | Volume | Persist trigger detections |
| `validate_caption_structure` | Validation | Anti-patterization check |
| `save_schedule` | Operations | Persist schedule + certificate |

### Nice-to-Have (6 Tools)

| Tool | Purpose |
|------|---------|
| `resolve_creator_id` | Fuzzy matching for creator ID |
| `get_best_timing` | Historical timing optimization |
| `get_attention_metrics` | Caption quality scoring |
| `get_churn_risk_scores` | Retention risk analysis |
| `get_active_experiments` | A/B experiment awareness |
| `execute_query` | Custom analysis queries |

### Deprecated (Do Not Use)

- ML prediction tools (5)
- A/B write tools (2)
- Legacy caption tools (3)
- Volume assignment tool (1)

---

## Quick Reference: Error Codes

| Code | Stage | Action |
|------|-------|--------|
| VAULT_VIOLATION | Hard Gate | REJECT - fix content selection |
| AVOID_TIER_VIOLATION | Hard Gate | REJECT - exclude content type |
| PAGE_TYPE_VIOLATION | Hard Gate | REJECT - wrong page type |
| INSUFFICIENT_DIVERSITY | Structural | REJECT - add more send types |
| FLYER_REQUIREMENT_VIOLATION | Hard Gate | REJECT - set flyer_required=1 |
| LOW_QUALITY_SCORE | Quality | NEEDS_REVIEW or REJECT |
| PRICE_OUTLIER | Anomaly | REJECT - adjust pricing |
| TIME_CONFLICT | Anomaly | REJECT - resolve collision |

---

## Cooldown Matrix (Category Transitions)

| From → To | REVENUE | ENGAGEMENT | RETENTION |
|-----------|---------|------------|-----------|
| REVENUE | 4h | 1h | 2h |
| ENGAGEMENT | 4h | 1h | 1h |
| RETENTION | 2h | 1h | 4h |

---

## Calendar Awareness

### Payday Boost: +20%

Days: 1st, 15th, last day of month

### Holiday Boost: +30%

Fixed: New Year's, Valentine's Day, July 4th, Halloween, Christmas
Moveable: Easter, Thanksgiving, Black Friday

### Overlap Strategy

Use maximum multiplier when payday and holiday coincide.

---

*End of Domain Knowledge Extract*
