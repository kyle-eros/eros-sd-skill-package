# EROS Schedule Generator Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-06

### Added
- Initial release of EROS Schedule Generator skill package
- 3-phase pipeline: Preflight → Generate → Validate
- Self-improving skills protocol with LEARNINGS.md
- 22 send type support with hard gate validation
- Automatic feedback capture from validation results
- Performance tracking for delayed feedback
- /reflect command for learning consolidation
- Complete test suite (42 tests, 89% coverage)
- Production infrastructure (routing, monitoring, rollback)

### Architecture
- Deterministic preflight engine (Python)
- LLM agents: Sonnet (generator), Opus (validator)
- 8 MCP calls per pipeline run
- Target execution: 60-90 seconds

### Documentation
- DOMAIN_KNOWLEDGE.md - Complete business rules
- SKILL.md with progressive disclosure
- REFERENCE/ files for detailed rules
- RUNBOOK.md for operations
