# EROS MCP Setup Guide

**Version**: 1.5.0
**Last Updated**: 2026-01-08
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
| `get_send_types` | 22-type taxonomy with constraints (full details) |
| `get_send_types_constraints` | Lightweight constraints for schedule generation (**preferred**) |

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

| Tool | Tokens | Fields | Use Case |
|------|--------|--------|----------|
| `get_send_types` | ~14,600 | 53 | Full details (rare) |
| `get_send_types_constraints` | ~2,000 | 9 | **Schedule generation (always use)** |

**Token Savings: 86% reduction (~12,500 tokens saved per call)**

### When to Use Each Tool

**get_send_types_constraints** (preferred):
- Schedule generation workflows
- Constraint validation
- Volume allocation decisions
- Any context-sensitive operations

**get_send_types** (full version):
- Debugging send type configurations
- Viewing descriptions, strategies, purposes
- Channel configuration analysis
- Weight/scoring adjustments

---

*EROS Schedule Generator MCP Documentation*
*Server: eros-db | Tools: 15 | MCP Spec: 2025-11-25 | get_creator_profile v3 (bundled with persona)*
