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

## Documentation

- [Domain Knowledge](docs/DOMAIN_KNOWLEDGE.md) - Business rules
- [Architecture](docs/ARCHITECTURE_DECISION_RECORD.md) - System design
- [Self-Improving Skills](docs/SELF_IMPROVING_SKILLS.md) - Learning protocol
- [Runbook](docs/RUNBOOK.md) - Operations guide

## License

MIT License - See [LICENSE](LICENSE) for details.
