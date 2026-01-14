# Validation Rules Reference

**Version**: 5.0.0

---

## Hard Gates (Zero Tolerance)

All hard gates result in immediate REJECT. No fallback, no degradation.

### Gate 1: Vault Compliance

```python
FOR item in schedule:
    IF item.content_type NOT IN vault_matrix.available_types:
        REJECT("VAULT_VIOLATION")
```

**Source**: `get_allowed_content_types(creator_id)`

### Gate 2: AVOID Tier Exclusion

```python
FOR item in schedule:
    IF item.content_type IN content_type_rankings.avoid_types:
        REJECT("AVOID_TIER_VIOLATION")
```

**Source**: `get_content_type_rankings(creator_id)` → `performance_tier = 'AVOID'`

### Gate 3: Page Type Restrictions

```python
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

```python
FLYER_REQUIRED = [
    'ppv_unlock', 'ppv_wall', 'bundle', 'flash_bundle',
    'vip_program', 'snapchat_bundle', 'first_to_tip',
    'bump_flyer', 'live_promo'
]

IF send_type IN FLYER_REQUIRED AND flyer_required != 1:
    REJECT("FLYER_REQUIREMENT_VIOLATION")
```

---

## ValidationCertificate v3.0

### Required Fields

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

Certificate must be < 5 minutes old at `save_schedule` time.

---

## Quality Score Thresholds

| Score | Status | Action |
|-------|--------|--------|
| 85-100 | APPROVED | Save and deploy |
| 75-84 | APPROVED | Proceed with recommendations |
| 60-74 | NEEDS_REVIEW | Flag for human review |
| < 60 | REJECTED | Return to generator phase |

---

## Error Codes

| Code | Stage | Action |
|------|-------|--------|
| `VAULT_VIOLATION` | Hard Gate | REJECT - reselect caption |
| `AVOID_TIER_VIOLATION` | Hard Gate | REJECT - exclude content type |
| `PAGE_TYPE_VIOLATION` | Hard Gate | REJECT - remove incompatible send |
| `INSUFFICIENT_DIVERSITY` | Structural | REJECT - add more send types |
| `FLYER_REQUIREMENT_VIOLATION` | Hard Gate | REJECT - set flyer_required=1 |
| `LOW_QUALITY_SCORE` | Quality | NEEDS_REVIEW or REJECT |
| `PRICE_OUTLIER` | Anomaly | REJECT - adjust to $5-$50 |
| `TIME_CONFLICT` | Anomaly | REJECT - resolve collision |

---

## Validation Sequence

1. **Vault Gate** - Check all content types against vault_matrix
2. **AVOID Gate** - Check all content types against rankings
3. **Page Type Gate** - Verify send type compatibility
4. **Diversity Gate** - Count unique types per category
5. **Flyer Gate** - Verify flyer_required flags
6. **Timing Gate** - Check gaps and collisions
7. **Quality Scoring** - Calculate overall score

---

*End of Validation Rules Reference*
