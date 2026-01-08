# EROS Schedule Generator Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-01-08

### Changed
- **BREAKING**: `get_creator_profile` now returns bundled response by default
  - `include_analytics=True` - 30-day metrics with 3-level MM revenue fallback
  - `include_volume=True` - Volume tier assignment with daily ranges
  - `include_content_rankings=True` - TOP/MID/LOW/AVOID content types
- Preflight MCP calls reduced from 7 to 4 (43% reduction)

### Added
- 3-level MM revenue fallback chain (high/medium/low confidence)
- Data freshness tracking: `mm_data_age_days`, `mm_revenue_confidence`, `mm_revenue_source`
- Helper functions: `validate_creator_id()`, `resolve_creator_id()`, `get_mm_revenue_with_fallback()`
- 23 new unit tests for bundled `get_creator_profile`

### Response Structure
New fields in `get_creator_profile` response:
- `analytics_summary` - 30-day metrics with fallback chain
- `volume_assignment` - Volume tier with daily ranges
- `top_content_types` - Full content type rankings
- `avoid_types` - AVOID tier content types
- `top_types` - TOP tier content types
- `metadata` - Data sources and MCP calls saved

---

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
