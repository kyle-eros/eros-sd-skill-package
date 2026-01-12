# EROS Schedule Generator

## Project Overview

Multi-agent skill package for generating optimized OnlyFans creator schedules. Uses a 3-phase pipeline architecture with MCP database integration.

## Pipeline Architecture
```
Preflight (Python) → Generator (Sonnet) → Validator (Opus) → Save
```

- **Preflight**: Deterministic Python engine, builds immutable CreatorContext
- **Generator**: Sonnet agent, produces schedule items from context
- **Validator**: Opus agent, independent verification against hard gates
- **Save**: Persist schedule with ValidationCertificate

## MCP Server

| Attribute | Value |
|-----------|-------|
| Name | eros-db |
| Status | REQUIRED - All database access must use MCP tools |

### Connection Validation (Run at session start)

```bash
# Verify MCP connection before any pipeline work
mcp__eros-db__get_active_creators --limit 1
```

If this fails, do NOT proceed. Check `.mcp.json` configuration.

### Key Tools

| Tool | Phase | Purpose |
|------|-------|---------|
| `get_creator_profile` | Preflight | Bundled creator data (57% call reduction) |
| `get_volume_config` | Preflight | Volume tier + daily ranges |
| `get_active_volume_triggers` | Preflight | Performance-based adjustments |
| `get_batch_captions_by_content_types` | Generator | PPV caption retrieval |
| `get_allowed_content_types` | Validator | Vault validation |
| `save_schedule` | Save | Persist with certificate |

## Hard Gates (Zero Tolerance)

These violations cause immediate schedule rejection:

| Gate | Rule |
|------|------|
| VAULT | Only schedule content types in creator's vault |
| AVOID | Never schedule AVOID-tier content types |
| TIMING | Respect creator timezone and prime hours |
| DIVERSITY | No same send type back-to-back |

## Commands

- `/eros generate <creator> <date>` - Generate weekly schedule
- `/eros validate <schedule_id>` - Validate existing schedule
- `/reflect` - Capture session learnings

## Key Files

| File | Purpose |
|------|---------|
| `skills/eros-schedule-generator/SKILL.md` | Main skill definition |
| `skills/eros-schedule-generator/REFERENCE/` | Domain knowledge (load on demand) |
| `.claude/agents/schedule-generator.md` | Generator agent config |
| `.claude/agents/schedule-validator.md` | Validator agent config |
| `LEARNINGS.md` | Self-improving feedback accumulation |
| `docs/DOMAIN_KNOWLEDGE.md` | Business rules reference |

## Development Guidelines

1. **MCP-first**: Never use raw SQL, always use MCP tools
2. **Fail fast**: Validation errors should halt pipeline immediately
3. **Log everything**: All MCP calls and errors must be traceable
4. **Test coverage**: Maintain >85% coverage on Python modules
