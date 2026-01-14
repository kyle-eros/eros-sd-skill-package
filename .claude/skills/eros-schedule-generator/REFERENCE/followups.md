# Followup Rules Reference

**Version**: 5.0.0

---

## Eligible Parent Types

| Parent Type | Followup Type | Channel | Target Audience |
|-------------|---------------|---------|-----------------|
| `ppv_unlock` | `ppv_followup` | targeted_message | ppv_non_purchasers |
| `ppv_wall` | `ppv_followup` | targeted_message | ppv_non_purchasers |
| `tip_goal` | `ppv_followup` | targeted_message | tip_goal_non_tippers |

---

## Timing Window

```python
OPTIMAL_DELAY = 28 minutes  # Truncated normal distribution mean
MIN_DELAY = 15 minutes      # HARD minimum
MAX_DELAY = 45 minutes      # HARD maximum
STD_DEV = 8 minutes

delay = truncated_normal(mean=28, std=8, min=15, max=45)
```

### Distribution Shape

Most followups cluster around 24-32 minutes, with tails at 15 and 45.

---

## Late Night Cutoff

```python
CUTOFF = 23:30  # 11:30 PM

IF followup_time > 23:30:
    push_to = next_day + 08:00  # 8:00 AM
```

### Example

- Parent PPV at 23:15 → Followup would be 23:43
- Followup > 23:30 → Push to next day 08:00

---

## Daily Limit

```python
MAX_FOLLOWUPS_PER_DAY = 5
```

### Priority When Over Limit

1. Followups for highest-revenue parent PPVs
2. Followups for TOP tier content types
3. Earlier scheduled parents

---

## Hard Constraints

| Constraint | Value | Enforcement |
|------------|-------|-------------|
| No cascading | true | Followups cannot have followups |
| Unique captions | per day | Same caption cannot repeat |
| Min gap | 1 hour | Between any two followups |

---

## Followup Generation Flow

```
1. Identify eligible parent items (ppv_unlock, ppv_wall, tip_goal)
2. For each parent:
   a. Calculate delay using truncated normal (28 ± 8, [15, 45])
   b. Compute followup_time = parent_time + delay
   c. Check late night cutoff
   d. Check daily followup count
3. If count > 5, drop lowest priority followups
4. Assign unique captions to each followup
```

---

## Output Schema

```json
{
  "parent_item_index": 0,
  "send_type_key": "ppv_followup",
  "scheduled_time": "19:51",
  "delay_minutes": 28
}
```

---

*End of Followup Rules Reference*
