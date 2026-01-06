# Schedule Validator Agent

**Model**: Opus | **Phase**: 3 (Validate) | **Version**: 5.0.0

## Purpose

Independently verify schedule against hard gates. Generate ValidationCertificate for save_schedule.

## Input: ScheduleOutput

```json
{
  "creator_id": "grace_bennett",
  "week_start": "2026-01-06",
  "items": [...],
  "followups": [...]
}
```

## Output: ValidationCertificate

```json
{
  "certificate_version": "3.0",
  "creator_id": "grace_bennett",
  "validation_timestamp": "2026-01-05T14:30:00Z",
  "schedule_hash": "sha256:abc123...",
  "avoid_types_hash": "sha256:...",
  "vault_types_hash": "sha256:...",
  "items_validated": 54,
  "quality_score": 87,
  "validation_status": "APPROVED",
  "checks_performed": {
    "vault_compliance": true,
    "avoid_tier_exclusion": true,
    "send_type_diversity": true,
    "timing_validation": true
  },
  "violations_found": { "vault": 0, "avoid_tier": 0, "critical": 0 },
  "certificate_signature": "vg-{hash8}-{timestamp}"
}
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `get_vault_availability` | Re-verify vault compliance |
| `get_content_type_rankings` | Re-verify AVOID exclusion |
| `save_schedule` | Persist with ValidationCertificate |

## Hard Gates (Zero Tolerance)

### Gate 1: Vault Compliance
```python
vault_types = get_vault_availability(creator_id).types
FOR item IN schedule.items:
    IF item.content_type NOT IN vault_types: REJECT("VAULT_VIOLATION")
```

### Gate 2: AVOID Tier Exclusion
```python
rankings = get_content_type_rankings(creator_id)
avoid_types = [r.type for r in rankings if r.tier == "AVOID"]
FOR item IN schedule.items:
    IF item.content_type IN avoid_types: REJECT("AVOID_TIER_VIOLATION")
```

### Gate 3: Page Type Restrictions
```python
IF page_type == "free": forbidden = ["tip_goal", "renew_on_post", "renew_on_message", "expired_winback"]
IF page_type == "paid": forbidden = ["ppv_wall"]
FOR item IN schedule.items:
    IF item.send_type_key IN forbidden: REJECT("PAGE_TYPE_VIOLATION")
```

### Gate 4: Send Type Diversity
```python
IF unique_send_types < 10: REJECT("INSUFFICIENT_DIVERSITY")
IF revenue_types < 4: REJECT("INSUFFICIENT_DIVERSITY")
IF engagement_types < 4: REJECT("INSUFFICIENT_DIVERSITY")
IF page_type == "paid" AND retention_types < 2: REJECT("INSUFFICIENT_DIVERSITY")
```

### Gate 5: Flyer Requirement
```python
FLYER_REQUIRED = ["ppv_unlock", "ppv_wall", "bundle", "flash_bundle",
                  "vip_program", "snapchat_bundle", "first_to_tip",
                  "bump_flyer", "live_promo"]
FOR item IN schedule.items:
    IF item.send_type_key IN FLYER_REQUIRED AND item.flyer_required != 1:
        REJECT("FLYER_REQUIREMENT_VIOLATION")
```

## Quality Scoring

| Component | Weight |
|-----------|--------|
| Vault compliance | 25% |
| AVOID exclusion | 25% |
| Diversity | 20% |
| Timing | 15% |
| Pricing | 15% |

| Score | Status |
|-------|--------|
| 85-100 | APPROVED |
| 75-84 | APPROVED (notes) |
| 60-74 | NEEDS_REVIEW |
| < 60 | REJECTED |

## Certificate Requirements

- **Freshness**: < 5 minutes old at save_schedule
- **Hashes**: Include schedule, vault, and avoid type hashes
- **Signature**: Format `vg-{hash8}-{timestamp}`

See `REFERENCE/validation.md` for complete gate logic.
