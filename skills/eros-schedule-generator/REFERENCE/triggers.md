# Volume Triggers Reference

**Version**: 5.0.0

---

## Trigger Types

| Type | Detection Criteria | Adjustment |
|------|-------------------|------------|
| `HIGH_PERFORMER` | RPS > $200 AND conversion > 6% | +20% |
| `TRENDING_UP` | Week-over-week RPS increase +15% | +10% |
| `EMERGING_WINNER` | RPS > $150 AND <3 uses in 30 days | +30% |
| `SATURATING` | Declining RPS for 3+ consecutive days | -15% |
| `AUDIENCE_FATIGUE` | Open rate dropped -10% over 7 days | -25% |

---

## Trigger Schema

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

---

## Confidence Levels

| Level | Criteria |
|-------|----------|
| `high` | Strong signal, >10 sends analyzed |
| `moderate` | Moderate signal, 5-10 sends analyzed |
| `low` | Weak signal, <5 sends analyzed |

---

## Application

Triggers apply at Phase 2 (allocation) via `get_active_volume_triggers()`.

### Multiplier Application

```python
base_volume = volume_config.revenue_per_day[1]  # Max of range

FOR trigger IN active_triggers:
    IF trigger.content_type == selected_content_type:
        adjusted_volume = base_volume * trigger.adjustment_multiplier
```

---

## MCP Tools

| Tool | Purpose |
|------|---------|
| `get_active_volume_triggers` | Retrieve non-expired triggers for creator |
| `save_volume_triggers` | Persist new trigger detections |

---

## Expiration

Default trigger TTL: 7 days from detection.

```python
IF trigger.expires_at < current_date:
    trigger is ignored
```

---

*End of Volume Triggers Reference*
