# Volume Triggers Reference

**Version**: 6.0.0
**MCP Tool Version**: 2.0.0
**Updated**: 2026-01-10

---

## Trigger Types

Detection uses **scale-aware thresholds** (conversion-first, not RPS-first):

| Type | Detection Criteria | Multiplier |
|------|-------------------|------------|
| `HIGH_PERFORMER` | Conversion >= 6.0% (primary) | 1.20x |
| `TRENDING_UP` | Week-over-week revenue +15% | 1.10x |
| `EMERGING_WINNER` | Conversion >= 5.0% AND <3 uses in 30 days | 1.30x |
| `SATURATING` | Declining conversion for 3+ consecutive days | 0.85x |
| `AUDIENCE_FATIGUE` | Open rate dropped -10% over 7 days | 0.75x |

**Why Conversion-First?** RPS-only detection is biased toward small creators. Conversion rate is scale-independent.

---

## Trigger Schema (v2.0)

```json
{
    "trigger_id": 42,
    "content_type": "lingerie",
    "trigger_type": "HIGH_PERFORMER",
    "adjustment_multiplier": 1.20,
    "confidence": "high",
    "reason": "Conversion 7.2%",
    "expires_at": "2026-01-17T14:19:18Z",
    "detected_at": "2026-01-10T14:19:18Z",
    "metrics_json": {"detected": {"conversion_rate": 7.2, "sends": 15}},
    "source": "database",
    "applied_count": 0,
    "last_applied_at": null,
    "days_until_expiry": 7,
    "days_since_detected": 0
}
```

---

## Confidence Levels

| Level | Criteria | Threshold |
|-------|----------|-----------|
| `high` | Strong signal | >10 sends analyzed |
| `moderate` | Moderate signal | 5-10 sends analyzed |
| `low` | Weak signal | <5 sends analyzed |

---

## MCP Response Schema (v2.0)

### `get_active_volume_triggers` Response

```json
{
    "creator_id": "maya_hill",
    "creator_id_resolved": "abc123-uuid",
    "triggers": [...],
    "count": 2,

    "compound_multiplier": 1.02,
    "compound_calculation": [
        {
            "content_type": "lingerie",
            "triggers": ["HIGH_PERFORMER:1.2", "SATURATING:0.85"],
            "compound": 1.02,
            "clamped": false
        }
    ],
    "has_conflicting_signals": true,

    "creator_context": {
        "fan_count": 45000,
        "tier": "PREMIUM",
        "page_type": "paid"
    },

    "zero_triggers_context": null,

    "metadata": {
        "fetched_at": "2026-01-10T14:30:00Z",
        "triggers_hash": "sha256:a1b2c3d4e5f6",
        "query_ms": 12.5,
        "thresholds_version": "2.0",
        "scale_aware": true
    }
}
```

### New Fields (v2.0)

| Field | Type | Description |
|-------|------|-------------|
| `compound_multiplier` | float | Pre-calculated compound, clamped to [0.50, 2.00] |
| `compound_calculation` | array | Per-content-type breakdown with clamping info |
| `has_conflicting_signals` | bool | True if BOOST and REDUCE triggers on same content |
| `creator_context` | object | Fan count, tier, page_type for scale interpretation |
| `zero_triggers_context` | object/null | Diagnostics when count=0 |
| `metadata` | object | Hash, timing, version info |

---

## Zero Triggers Diagnostics

When `count=0`, `zero_triggers_context` provides:

```json
{
    "reason": "all_expired",
    "reason_description": "All triggers have passed their expires_at",
    "last_trigger_expired_at": "2026-01-08T12:00:00Z",
    "last_trigger_type": "HIGH_PERFORMER",
    "last_trigger_content_type": "lingerie",
    "historical_trigger_count": 5,
    "triggers_expired_last_7d": 2
}
```

| Reason Code | Description |
|-------------|-------------|
| `never_had_triggers` | No trigger history for this creator |
| `all_expired` | All triggers have passed their expires_at |
| `all_inactive` | Triggers exist but all marked is_active=0 |
| `creator_new` | Creator has <7 days of performance data |
| `no_qualifying_performance` | Historical triggers but none currently active |

---

## Compound Multiplier Calculation

Triggers compound **multiplicatively** per content_type, clamped to bounds:

```python
# Per content_type compound
compound = 1.0
for trigger in triggers_for_content_type:
    compound *= trigger.adjustment_multiplier

# Clamp to bounds
compound = max(0.50, min(2.00, compound))
```

**Conflict Detection**: If a content_type has both BOOST (>1.0) and REDUCE (<1.0) triggers, `has_conflicting_signals=true`.

---

## Application

Triggers apply at Phase 2 (allocation) via `get_active_volume_triggers()`.

### Using Pre-Calculated Compound

```python
# v2.0 pattern - use pre-calculated compound
result = get_active_volume_triggers(creator_id)
compound = result["compound_multiplier"]  # Already clamped

adjusted_volume = base_volume * compound
```

### Legacy Pattern (Still Supported)

```python
# v1.0 pattern - manual calculation
triggers = result.get("triggers", [])
for trigger in triggers:
    if trigger["content_type"] == selected_type:
        volume *= trigger["adjustment_multiplier"]
```

---

## MCP Tools

| Tool | Purpose | Version |
|------|---------|---------|
| `get_active_volume_triggers` | Retrieve active triggers with compound calculation | 2.0.0 |
| `save_volume_triggers` | Persist new trigger detections with validation | 2.0.0 |

### save_volume_triggers Validation

Required fields: `trigger_type`, `content_type`, `adjustment_multiplier`

```json
{
    "success": true,
    "triggers_saved": 2,
    "creator_id_resolved": "abc123-uuid",
    "warnings": ["trigger[0]: extreme multiplier 0.55 - verify intentional"]
}
```

---

## Expiration

Default trigger TTL: **7 days** from detection.

```python
IF trigger.expires_at < current_datetime:
    trigger is ignored (not returned by get_active_volume_triggers)
```

---

## Multiplier Bounds

| Constant | Value | Purpose |
|----------|-------|---------|
| `TRIGGER_MULT_MIN` | 0.50 | Minimum compound multiplier |
| `TRIGGER_MULT_MAX` | 2.00 | Maximum compound multiplier |
| `TRIGGER_DEFAULT_TTL_DAYS` | 7 | Default expiration |

---

## Trigger Sources

| Source | Description |
|--------|-------------|
| `database` | Persisted trigger from `save_volume_triggers` |
| `runtime` | Detected at runtime during preflight |

Preflight merges DB + runtime triggers, with DB taking precedence for duplicates.

---

*End of Volume Triggers Reference*
