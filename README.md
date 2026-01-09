# EROS Schedule Generator

A self-improving Claude Code skill package for generating optimized OnlyFans creator schedules.

## Features

- **3-Phase Pipeline**: Preflight (deterministic) → Generate (Sonnet) → Validate (Opus)
- **Self-Improving**: Learns from every schedule via LEARNINGS.md
- **22 Send Types**: Revenue, Engagement, and Retention categories
- **Hard Gate Validation**: Zero-tolerance for vault/AVOID violations
- **Production Ready**: Monitoring, rollback, feature flags

## Quick Start

```bash
# Clone the repository
git clone https://github.com/kyle-eros/eros-sd-skill-package.git
cd eros-sd-skill-package

# The skill auto-activates in Claude Code when you mention:
# - "generate schedule"
# - "weekly schedule for [creator]"
# - "PPV optimization"
```

## Usage

```
# Generate a schedule
/eros generate grace_bennett 2026-01-13

# Validate an existing schedule
/eros validate 12345

# View learning statistics
/eros learnings

# Reflect on session (capture learnings)
/reflect
```

## Architecture

```
User Request
     │
     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  PREFLIGHT  │────▶│  GENERATE   │────▶│  VALIDATE   │
│   (Python)  │     │  (Sonnet)   │     │   (Opus)    │
└─────────────┘     └─────────────┘     └─────────────┘
     │                                        │
     │              CreatorContext            │
     └────────────────────────────────────────┘
                         │
                         ▼
                  ValidationCertificate
                         │
                         ▼
                   save_schedule()
```

## Self-Improving Skills

Every schedule generation captures feedback:

| Signal | Confidence | Source |
|--------|------------|--------|
| Hard gate violations | HIGH | Validation |
| User corrections | HIGH | Session |
| Quality score ≥85 | MEDIUM | Validation |
| Performance data | MEDIUM | 7-14 day delay |

Run `/reflect` to consolidate learnings into SKILL.md.

## MCP Server

The skill uses an MCP server (`eros-db`) for database access.

### Quick Start

1. Ensure database exists at `./data/eros_sd_main.db`
2. Restart Claude Code
3. Verify connection: `/mcp status`

### Available Tools (14)

| Category | Tools | Purpose |
|----------|-------|---------|
| Creator | 5 | **Bundled profiles** (analytics + volume + rankings + vault + **persona**) |
| Schedule | 5 | Volume config, triggers, persistence |
| Caption | 3 | Batch retrieval, validation |
| Config | 1 | 22-type send taxonomy |

> **v1.5.0 Optimization**: `get_creator_profile` now returns bundled response including analytics, volume assignment, content rankings, vault, and **persona**. Preflight MCP calls reduced from 7 to 3 (57% reduction).

### Verifying Setup

```bash
# Check MCP status
/mcp status

# List tools
/mcp tools eros-db

# Test tool (now with pagination)
/mcp call eros-db get_active_creators --limit 5 --sort_by fan_count
```

See [MCP Setup Guide](docs/MCP_SETUP_GUIDE.md) for troubleshooting and detailed configuration.

## Documentation

- [MCP Setup Guide](docs/MCP_SETUP_GUIDE.md) - MCP server configuration
- [Domain Knowledge](docs/DOMAIN_KNOWLEDGE.md) - Business rules
- [Architecture](docs/ARCHITECTURE_DECISION_RECORD.md) - System design
- [Self-Improving Skills](docs/SELF_IMPROVING_SKILLS.md) - Learning protocol
- [Runbook](docs/RUNBOOK.md) - Operations guide

## License

MIT License - See [LICENSE](LICENSE) for details.
