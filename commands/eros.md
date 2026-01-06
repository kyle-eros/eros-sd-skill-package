---
name: eros
description: EROS schedule generation commands
---

# /eros Commands

## Usage

| Command | Description |
|---------|-------------|
| `/eros generate {creator} {week}` | Generate schedule for creator |
| `/eros validate {schedule_id}` | Re-validate existing schedule |
| `/eros status` | Show pipeline status and recent activity |
| `/eros learnings` | Show learning statistics |

## Examples

```
/eros generate grace_bennett 2026-01-06
/eros validate 12345
/eros status
/eros learnings
```

## Arguments

### generate
- `creator` - Creator ID or page name (required)
- `week` - Week start date in YYYY-MM-DD format (optional, defaults to next Monday)

### validate
- `schedule_id` - Numeric schedule ID from database (required)

## Related Commands

- `/reflect` - Manage auto-reflection settings
- `/eros:analyze` - Deep performance analysis
- `/eros:creators` - List active creators
