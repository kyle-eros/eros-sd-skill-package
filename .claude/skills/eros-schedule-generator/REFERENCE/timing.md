# Timing Rules Reference

**Version**: 5.0.0

---

## Jitter Algorithm

Prevents pattern detection by avoiding round times:

```python
JITTER_MIN = -7 minutes
JITTER_MAX = +8 minutes
ROUND_MINUTES = {0, 15, 30, 45}  # NEVER land on these

jitter = random.randint(-7, +8)
WHILE (base_minute + jitter) % 15 == 0:
    jitter = random.randint(-7, +8)
```

### Valid Output Minutes

Examples: :03, :07, :11, :18, :23, :28, :33, :38, :42, :47, :52, :58

---

## Minimum Gap by Send Type

| Send Type | Min Gap | Category |
|-----------|---------|----------|
| ppv_unlock | 2h | Revenue |
| ppv_wall | 3h | Revenue |
| tip_goal | 4h | Revenue |
| vip_program | 24h | Revenue |
| game_post | 4h | Revenue |
| bundle | 3h | Revenue |
| flash_bundle | 6h | Revenue |
| snapchat_bundle | 24h | Revenue |
| first_to_tip | 6h | Revenue |
| link_drop | 2h | Engagement |
| wall_link_drop | 3h | Engagement |
| bump_normal | 1h | Engagement |
| bump_descriptive | 2h | Engagement |
| bump_text_only | 2h | Engagement |
| bump_flyer | 4h | Engagement |
| dm_farm | 4h | Engagement |
| like_farm | 24h | Engagement |
| live_promo | 2h | Engagement |
| renew_on_post | 12h | Retention |
| renew_on_message | 24h | Retention |
| ppv_followup | 1h | Retention |
| expired_winback | 24h | Retention |

---

## DOW Prime Hours (EST)

| Day | Prime Hours | Secondary Hours |
|-----|-------------|-----------------|
| Mon | 12-2pm, 7-10pm | 10-11am |
| Tue | 12-2pm, 8-11pm | 10-11am |
| Wed | 12-2pm, 8-11pm | 6-7pm |
| Thu | 12-2pm, 8-11pm | 6-7pm |
| Fri | 12-2pm, 9pm-12am | 5-7pm |
| Sat | 11am-2pm, 10pm-1am | 4-6pm |
| Sun | 11am-2pm, 8-11pm | 4-6pm |

---

## Dead Zone: 3-7 AM

```python
IF 3 <= hour < 5:
    shift_to = previous day 23:00 (11 PM)
IF 5 <= hour < 7:
    shift_to = same day 07:00 (7 AM)
```

### Rationale

- 3-5 AM: Lowest engagement, shift to late night prime
- 5-7 AM: Still low, shift to morning start

---

## Collision Resolution

```python
PRIORITY_ORDER = [
    'ppv_unlock',      # Highest priority
    'ppv_followup',    # Supports PPV
    'other_revenue',   # bundle, tip_goal, etc.
    'engagement',      # bumps, link_drops
    'retention'        # renewals
]

INCREMENT = 5 minutes
MAX_OFFSET = 15 minutes
MIN_GAP_BETWEEN_ANY = 45 minutes
```

### Resolution Algorithm

1. Sort scheduled items by time
2. For each collision (< 45 min gap):
   - Keep higher priority item
   - Shift lower priority item by 5-min increments
   - Max offset: 15 minutes
3. If still colliding after max offset, move to next available slot

---

## Category Cooldowns (Hours)

| From → To | REVENUE | ENGAGEMENT | RETENTION |
|-----------|---------|------------|-----------|
| REVENUE | 4h | 1h | 2h |
| ENGAGEMENT | 4h | 1h | 1h |
| RETENTION | 2h | 1h | 4h |

### Design Rationale

- REVENUE→REVENUE: 4h enables AM/PM PPV structure
- ENGAGEMENT→REVENUE: 4h protects drip sexting sets
- ENGAGEMENT→ENGAGEMENT: 1h allows frequent bumps

---

*End of Timing Rules Reference*
