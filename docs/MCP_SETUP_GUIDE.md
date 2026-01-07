# EROS MCP Setup Guide

**Version**: 1.0.0
**Last Updated**: 2026-01-06
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
| `./mcp_server/main.py` | Server implementation (14 tools) |
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
**Expected**: All 14 tools listed

### 3. Test Tool Call
```
/mcp call eros-db get_active_creators --limit 5
```

## Available Tools (14 total)

### Creator Tools (5)

| Tool | Description | GATE |
|------|-------------|------|
| `get_creator_profile` | Profile with optional 30-day analytics | |
| `get_active_creators` | List active creators with filters | |
| `get_vault_availability` | Content types in creator's vault | HARD |
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

### Config Tools (1)

| Tool | Description |
|------|-------------|
| `get_send_types` | 22-type taxonomy with constraints |

## Tool Usage by Phase

### Phase 1 - Preflight (5 tools)
```
get_creator_profile     → Creator metadata
get_volume_config       → Volume tier configuration
get_vault_availability  → HARD GATE data
get_content_type_rankings → HARD GATE data
get_persona_profile     → Caption styling
```

### Phase 2 - Generate (3 tools)
```
get_batch_captions_by_content_types → PPV captions
get_send_type_captions              → Engagement captions
validate_caption_structure          → Quality check
```

### Phase 3 - Validate (3 tools)
```
get_vault_availability      → Re-verify HARD GATE
get_content_type_rankings   → Re-verify HARD GATE
save_schedule               → Persist with certificate
```

## MCP Tool Naming Convention

All tools follow the format: `mcp__eros-db__<tool-name>`

Example:
```
mcp__eros-db__get_creator_profile
mcp__eros-db__get_vault_availability
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
   # Should return 14
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

---

*EROS Schedule Generator MCP Documentation*
*Server: eros-db | Tools: 14 | MCP Spec: 2025-11-25*
