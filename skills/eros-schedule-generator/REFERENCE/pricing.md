# Pricing Rules Reference

**Version**: 5.0.0

---

## Hard Bounds

| Bound | Value | Enforcement |
|-------|-------|-------------|
| Floor | $5.00 | HARD - never below |
| Ceiling | $50.00 | HARD - never above |
| Default | Creator base price OR $15.00 | When no override |

---

## Adjustment Stack

Final price is calculated multiplicatively:

```python
final_price = base_price * (1 + sum(adjustments))
final_price = clamp($5.00, round(final_price), $50.00)
```

### Adjustment Types

| Type | Range | Trigger |
|------|-------|---------|
| Prediction Bonus | +10-25% | predicted_rps > median_rps |
| Time Premium | +15% | Weekend evening (Fri-Sun, 6-10 PM) |
| Time Discount | -10% | Weekday morning (Mon-Fri, 6-10 AM) |
| Scarcity Premium | +20% | Content type unused 14+ days |
| Performance Premium | +15% | TOP tier content type |
| Freshness Premium | +10% | Caption never used before |
| Bundle Discount | -15% | Part of multi-PPV bundle |

---

## Prediction Bonus Thresholds

```python
IF confidence_score < 0.6:
    skip prediction adjustment

IF predicted_rps > median * 1.5:
    adjustment = +25%
ELIF predicted_rps > median * 1.2:
    adjustment = +15%
ELIF predicted_rps > median:
    adjustment = +10%
ELIF predicted_rps < median * 0.7:
    adjustment = -10%
```

---

## Skip Optimization Conditions

Do NOT apply pricing optimization when:

| Condition | Reason |
|-----------|--------|
| `fan_count < 1000` | Insufficient data for prediction |
| Active A/B price experiments | Avoid confounding experiment |
| Content type in AVOID tier | Already excluded from selection |

---

## Price by Send Type

| Send Type | Typical Range | Notes |
|-----------|---------------|-------|
| ppv_unlock | $8-$25 | Primary revenue driver |
| ppv_wall | $5-$15 | FREE page entry point |
| tip_goal | $10-$50 | PAID page goal amount |
| bundle | $15-$40 | Multi-content discount |
| flash_bundle | $12-$35 | Time-limited urgency |

---

## Example Calculation

```
Base Price: $15.00 (creator default)
+ Weekend Evening Premium: +15% = $17.25
+ TOP Tier Content: +15% = $19.84
+ Scarcity Premium (unused 14d): +20% = $23.81
= Final Price: $24.00 (rounded)
```

---

*End of Pricing Rules Reference*
