# EROS MCP Setup Guide

**Version**: 2.0.0
**Last Updated**: 2026-01-10
**Server**: eros-db

## Overview

The EROS Schedule Generator uses an MCP server (`eros-db`) to access the SQLite database containing creator profiles, captions, and scheduling data.

## Prerequisites

- Python 3.10+
- MCP SDK: `pip install mcp`
- Database: `./data/eros_sd_main.db`

## Configuration Files

| File | Purpose |
|------|---------|
| `.mcp.json` | MCP server configuration |
| `./mcp_server/main.py` | Server implementation (15 tools) |
| `./mcp_server/__init__.py` | Package initialization |
| `./data/eros_sd_main.db` | SQLite database |
| `./data/db-config.json` | Database configuration |

## Verifying Setup

### 1. Check MCP Status
```
/mcp status
```
**Expected**: `eros-db` listed as "connected"

### 2. List Available Tools
```
/mcp tools eros-db
```
**Expected**: All 15 tools listed

### 3. Test Tool Call
```
/mcp call eros-db get_active_creators --limit 5
```

## Available Tools (15 total)

### Creator Tools (5)

| Tool | Description | GATE |
|------|-------------|------|
| `get_creator_profile` | Profile + analytics + volume + rankings (bundled) | (partial) |
| `get_active_creators` | **Paginated** list with filters (tier/page_type/revenue) | |
| `get_allowed_content_types` | Content types creator allows for sends | HARD |
| `get_content_type_rankings` | Performance tiers (TOP/MID/LOW/AVOID) | HARD |
| `get_persona_profile` | Tone, archetype, voice settings | |

### Schedule Tools (5)

| Tool | Description |
|------|-------------|
| `get_volume_config` | Volume tier and daily distribution |
| `get_active_volume_triggers` | Performance-based triggers |
| `get_performance_trends` | Health and saturation metrics |
| `save_schedule` | Persist schedule with validation certificate |
| `save_volume_triggers` | Persist detected triggers |

### Caption Tools (3)

| Tool | Description |
|------|-------------|
| `get_batch_captions_by_content_types` | Batch retrieval for PPV selection |
| `get_send_type_captions` | Captions by send type category |
| `validate_caption_structure` | Anti-patterization validation |

### Config Tools (2)

| Tool | Description |
|------|-------------|
| `get_send_types` | 22-type taxonomy with 48 business columns (v2.0.0) |
| `get_send_types_constraints` | Lightweight constraints for schedule generation (**preferred**, v2.0.0) |

### get_creator_profile Optimization

**Optimization Note**: `get_creator_profile` now returns bundled data by default:
- `include_analytics=True` - 30-day metrics with 3-level MM revenue fallback
- `include_volume=True` - Volume tier assignment with daily ranges
- `include_content_rankings=True` - TOP/MID/LOW/AVOID content types
- `include_vault=True` - Allowed content types from vault_matrix
- `include_persona=True` - Tone, emoji frequency, slang level for voice matching (NEW in v1.5.0)

**This reduces preflight from 7 MCP calls to 3.**

| Parameter | Default | Data Included |
|-----------|---------|---------------|
| `include_analytics` | `True` | 30-day MM revenue, conversion metrics |
| `include_volume` | `True` | Volume tier and daily distribution |
| `include_content_rankings` | `True` | TOP/MID/LOW/AVOID performance tiers |
| `include_vault` | `True` | Allowed content types from vault_matrix |
| `include_persona` | `True` | Tone, emoji frequency, slang level |

**Return Structure**:
```json
{
  "found": true,
  "creator": { "creator_id", "page_name", "page_type", ... },
  "analytics_summary": {
    "mm_revenue_30d", "mm_revenue_confidence", "mm_revenue_source",
    "mm_data_age_days", "avg_rps", "avg_open_rate", ...
  },
  "volume_assignment": {
    "volume_level", "revenue_per_day", "engagement_per_day", ...
  },
  "top_content_types": [ { "type_name", "performance_tier", "rps", ... } ],
  "avoid_types": [ ... ],
  "top_types": [ ... ],
  "allowed_content_types": {
    "allowed_types": [...],
    "allowed_type_names": [...],
    "type_count": int
  },
  "persona": {
    "primary_tone": "playful",
    "secondary_tone": "bratty",
    "emoji_frequency": "moderate",
    "slang_level": "light",
    "_default": false
  },
  "metadata": { "fetched_at", "data_sources_used", "mcp_calls_saved" }
}
```

### get_active_creators Optimization (v1.2.0)

**New Parameters**:
- `offset` - Pagination support (default: 0)
- `page_type` - Filter by "paid" or "free"
- `min_revenue`, `max_revenue` - Revenue range filters
- `min_fan_count` - Minimum fan count filter
- `sort_by` - Sort by "revenue", "fan_count", "name", or "tier"
- `sort_order` - "asc" or "desc"
- `include_volume_details` - Include ppv_per_day, bump_per_day, etc.

**Response Enhancements**:
- `total_count` - Total matching records for pagination
- `metadata.has_more` - Boolean for pagination UI
- `metadata.page_info` - Current page and total pages
- Comprehensive creator fields (display_name, timezone, metrics_snapshot_date)

**Example: Paginated tier filter**
```bash
/mcp call eros-db get_active_creators --tier PREMIUM --limit 50 --offset 0
```

### get_content_type_rankings Optimization (v1.4.0)

**New Parameters**:
- `include_metrics` - Include detailed RPS/conversion metrics (default: True)

**Response Enhancements**:
- `rankings` - List of content types with tiers (replaces `content_types`)
- `metadata.rankings_hash` - Hash for ValidationCertificate integrity
- `metadata.avoid_types_hash` - Hash for HARD GATE verification
- `metadata.analysis_date` - When performance analysis was run
- `metadata.data_age_days` - Days since analysis
- `metadata.is_stale` - True if data > 14 days old

**CRITICAL FIX**: Now filters by latest `analysis_date` to prevent stale data mixing.

### get_volume_config Enhancement (v1.6.0)

The `get_volume_config` tool has been enhanced from a simple tier lookup to a
comprehensive **Volume Service** that returns pre-calculated weekly configurations.

**Key Differentiator from bundled response:**
- `get_creator_profile` -> Returns raw tier + ranges
- `get_volume_config` -> Returns CALCULATED weekly plan with all adjustments applied

#### New Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_trigger_breakdown` | bool | False | Include trigger_details array for auditing |
| `trigger_overrides` | list[dict] | None | Simulate triggers without DB lookup |
| `tier_override` | str | None | Force specific tier for simulation |
| `health_override` | dict | None | Override health status for simulation |

#### Response Schema

```json
{
  "creator_id": "alexia",
  "week_start": "2026-01-06",
  "tier": "STANDARD",
  "tier_source": "mm_revenue",
  "tier_confidence": "high",
  "base_ranges": {
    "revenue": [4, 6],
    "engagement": [4, 6],
    "retention": [2, 3]
  },
  "trigger_multiplier": 1.2,
  "triggers_applied": 1,
  "health": {
    "status": "HEALTHY",
    "saturation_score": 45,
    "volume_adjustment": 0
  },
  "weekly_distribution": {
    "monday": {
      "date": "2026-01-06",
      "revenue": 5,
      "engagement": 5,
      "retention": 2,
      "calendar_boost": 1.0,
      "weekend_boost": 1.0,
      "day_multiplier": 1.2
    }
  },
  "calendar_boosts": [
    {"date": "2026-01-15", "boost": 1.2, "reason": "payday"}
  ],
  "temporal_context": {
    "week_type": "current",
    "data_accuracy": {...}
  },
  "metadata": {
    "volume_config_hash": "sha256:abc123...",
    "hash_inputs": ["tier:STANDARD", "week:2026-01-06", ...]
  }
}
```

#### Usage Examples

```python
# Standard usage for schedule generation
get_volume_config("alexia", "2026-01-06")

# Simulation mode - test trigger scenarios
get_volume_config("alexia", "2026-01-06",
    trigger_overrides=[{"trigger_type": "HIGH_PERFORMER", "adjustment_multiplier": 1.2}],
    tier_override="PREMIUM")

# Debug mode with full breakdown
get_volume_config("alexia", "2026-01-06", include_trigger_breakdown=True)

# Historical reconstruction
get_volume_config("alexia", "2025-12-01")  # Past week, calendar exact
```

#### Implementation Note

Canonical tier thresholds are defined in `mcp_server/volume_utils.py`. All consumers
(`get_volume_config`, `get_creator_profile`, `preflight.py`) import from this single
source of truth, eliminating the risk of threshold drift between components.

### get_performance_trends Enhancement (v2.0.0)

**Purpose:** Returns performance trends for health and saturation detection.

**MCP Name:** `mcp__eros-db__get_performance_trends`

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| creator_id | string | Yes | - | Creator identifier or page_name |
| period | string | No | "14d" | Analysis period: "7d", "14d", or "30d" |

#### Response Schema

```json
{
  "creator_id": "string - input creator identifier",
  "creator_id_resolved": "string - canonical creator_id from database",
  "period": "string - analysis period used",
  "health_status": "string - HEALTHY | WARNING | DEATH_SPIRAL",
  "saturation_score": "int - 0-100, send density percentage",
  "opportunity_score": "int - 0-100, volume increase headroom",
  "consecutive_decline_weeks": "int - weeks of declining revenue",
  "volume_adjustment": "int - -1, 0, or +1 recommended adjustment",
  "avg_rps": "float - average revenue per send",
  "avg_conversion": "float - conversion rate percentage",
  "avg_open_rate": "float - open rate percentage",
  "total_earnings": "float - total earnings in period",
  "total_sends": "int - count of sends in period",
  "revenue_trend_pct": "float|null - week-over-week revenue change",
  "engagement_trend_pct": "float|null - week-over-week engagement change",
  "trend_period": "string - comparison type (wow = week-over-week)",
  "data_confidence": "string - high | moderate | low",
  "insufficient_data": "bool - true if <10 sends in period",
  "date_range": {
    "start": "string - period start timestamp",
    "end": "string - period end timestamp"
  },
  "metadata": {
    "fetched_at": "string - ISO timestamp",
    "trends_hash": "string - cache invalidation hash",
    "hash_inputs": "array - values used in hash calculation",
    "query_ms": "float - query execution time",
    "data_age_days": "int|null - days since last data",
    "is_stale": "bool - true if >14 days old",
    "has_period_data": "bool - data exists in requested period",
    "sends_in_period": "int - actual send count",
    "period_days": "int - period length in days",
    "expected_sends": "int - baseline expected sends",
    "staleness_threshold_days": "int - staleness cutoff (14)"
  }
}
```

#### Health Status Logic

- `HEALTHY`: 0-1 consecutive decline weeks
- `WARNING`: 2-3 consecutive decline weeks
- `DEATH_SPIRAL`: 4+ consecutive decline weeks

#### Data Confidence Thresholds

- `high`: sends >= 20 AND data_age_days <= 7
- `moderate`: sends >= 10 OR data_age_days <= 14
- `low`: sends < 10 AND data_age_days > 14

#### Example

```python
result = get_performance_trends("alexia", "14d")
# Returns performance metrics with health status and saturation analysis
```

### save_schedule Enhancement (v2.0.0)

**Version:** 2.0.0
**MCP Name:** `mcp__eros-db__save_schedule`

Persists generated schedule with validation certificate. Final step of 3-phase pipeline.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| creator_id | string | Yes | Creator identifier (creator_id or page_name) |
| week_start | string | Yes | Week start date (YYYY-MM-DD) |
| items | list | Yes | Schedule items from Generator phase |
| validation_certificate | dict | No | ValidationCertificate from Validator phase |

#### Response (Success)

```json
{
  "success": true,
  "schedule_id": 12345,
  "template_id": 12345,
  "items_saved": 54,
  "creator_id": "grace_bennett",
  "creator_id_resolved": "abc123-uuid",
  "week_start": "2026-01-06",
  "week_end": "2026-01-12",
  "status": "approved",
  "has_certificate": true,
  "metadata": {
    "saved_at": "2026-01-12T14:30:00Z",
    "query_ms": 45.2,
    "schedule_hash": "sha256:a1b2c3d4..."
  },
  "certificate_summary": {
    "validation_status": "APPROVED",
    "quality_score": 87,
    "items_validated": 54,
    "is_fresh": true,
    "age_seconds": 142
  },
  "replaced": false,
  "warnings": []
}
```

#### Error Codes

| Code | Cause |
|------|-------|
| CREATOR_NOT_FOUND | creator_id/page_name not in database |
| VALIDATION_ERROR | Items failed structural validation |
| INVALID_DATE | week_start not YYYY-MM-DD format |
| SCHEDULE_LOCKED | Cannot replace schedule with status 'queued' |
| SCHEDULE_COMPLETED | Cannot replace schedule with status 'completed' |
| DATABASE_ERROR | SQLite operation failed |

#### Duplicate Handling (UPSERT)

| Existing Status | Action |
|-----------------|--------|
| (none) | INSERT new |
| draft | UPDATE (replace) |
| approved | UPDATE (replace) |
| queued | REJECT with SCHEDULE_LOCKED |
| completed | REJECT with SCHEDULE_COMPLETED |

---

## Tool Usage by Phase

### Phase 1 - Preflight (3 tools - optimized)
```
get_creator_profile        → Creator + Analytics + Volume + Rankings + Vault + Persona (BUNDLED)
get_active_volume_triggers → Performance triggers
get_performance_trends     → Health and saturation metrics
```
**Note**: `get_creator_profile` now replaces separate calls to `get_volume_config`, `get_allowed_content_types`, `get_content_type_rankings`, AND `get_persona_profile`. Persona data is bundled via `include_persona=True` (default).

### Phase 2 - Generate (3 tools)
```
get_batch_captions_by_content_types → PPV captions
get_send_type_captions              → Engagement captions
validate_caption_structure          → Quality check
```

### Phase 3 - Validate (3 tools)
```
get_allowed_content_types   → Re-verify HARD GATE
get_content_type_rankings   → Re-verify HARD GATE
save_schedule               → Persist with certificate
```

## MCP Tool Naming Convention

All tools follow the format: `mcp__eros-db__<tool-name>`

Example:
```
mcp__eros-db__get_creator_profile
mcp__eros-db__get_allowed_content_types
mcp__eros-db__save_schedule
```

## Troubleshooting

### Server Not Connecting

1. **Verify database exists:**
   ```bash
   ls -la ./data/eros_sd_main.db
   ```

2. **Test server import:**
   ```bash
   python -c "from mcp_server.main import mcp; print(mcp.name)"
   ```

3. **Check MCP SDK installed:**
   ```bash
   pip show mcp
   ```

4. **Verify Python version:**
   ```bash
   python --version  # Must be 3.10+
   ```

5. **Restart Claude Code session** (required after .mcp.json changes)

### Database Errors

1. **Check integrity:**
   ```bash
   sqlite3 ./data/eros_sd_main.db "PRAGMA integrity_check;"
   ```

2. **Verify permissions:**
   ```bash
   ls -la ./data/
   ```

3. **Test connectivity:**
   ```bash
   python -c "
   from mcp_server.main import get_db_connection
   with get_db_connection() as conn:
       print('Connected:', conn is not None)
   "
   ```

### Tool Execution Errors

1. **Check server logs** (output to stderr):
   - Enable verbose logging: Set `LOG_LEVEL=debug` in `.mcp.json` env

2. **Verify tool exists:**
   ```bash
   grep "@mcp.tool()" ./mcp_server/main.py | wc -l
   # Should return 15
   ```

3. **Test individual tool:**
   ```bash
   python -c "
   from mcp_server.main import get_active_creators
   result = get_active_creators(limit=5)
   print(result)
   "
   ```

## Configuration Reference

### .mcp.json Structure
```json
{
  "mcpServers": {
    "eros-db": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server.main"],
      "env": {
        "EROS_DB_PATH": "./data/eros_sd_main.db",
        "LOG_LEVEL": "info",
        "PYTHONPATH": "."
      },
      "timeout": 30000
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EROS_DB_PATH` | `./data/eros_sd_main.db` | Database location |
| `LOG_LEVEL` | `info` | Logging verbosity (debug/info/warning/error) |
| `PYTHONPATH` | `.` | Module search path |

## Subagent Configuration

Subagents inherit MCP tools when the `tools` field is omitted from frontmatter.

| Agent | Model | Phase | Location |
|-------|-------|-------|----------|
| schedule-generator | Sonnet | 2 | `.claude/agents/schedule-generator.md` |
| schedule-validator | Opus | 3 | `.claude/agents/schedule-validator.md` |

## Database Schema Reference

Key tables:

| Table | Description |
|-------|-------------|
| `creators` | Creator profiles and settings |
| `captions` | Caption library |
| `content_types` | 30 content type definitions |
| `send_types` | 22 send type taxonomy |
| `vault_content` | Available content inventory |
| `content_type_rankings` | Performance tiers per creator |
| `volume_triggers` | Dynamic volume adjustments |
| `schedule_templates` | Generated schedules |
| `mass_messages` | Historical performance data |
| `personas` | Creator voice/tone settings |

## Tool Optimization Guide

### Send Types Tools Comparison

| Tool | Tokens | Fields | Use Case | Version |
|------|--------|--------|----------|---------|
| `get_send_types` | ~8,000 | 48 | Full details (rare) | v2.0.0 |
| `get_send_types_constraints` | ~2,000 | 9 | **Schedule generation (always use)** | v2.0.0 |

**Token Savings: 75% reduction (~6,000 tokens saved per call)**

> **v2.0.0 Breaking Change**: `get_send_types` no longer returns redundant `send_types` flat array.
> Use `by_category` for grouped access or `all_send_type_keys` for key list.

### When to Use Each Tool

**get_send_types_constraints** (preferred):
- Schedule generation workflows
- Constraint validation
- Volume allocation decisions
- Any context-sensitive operations

**get_send_types** (full version, v2.0.0):
- Debugging send type configurations
- Viewing descriptions, strategies, purposes
- Channel configuration analysis
- Weight/scoring adjustments
- Returns 48 business columns (excludes internal lifecycle fields)

---

*EROS Schedule Generator MCP Documentation*
*Server: eros-db | Tools: 15 | MCP Spec: 2025-11-25 | get_performance_trends v2.0.0 (enhanced)*
