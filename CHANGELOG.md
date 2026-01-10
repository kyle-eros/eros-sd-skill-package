# EROS Schedule Generator Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-01-10

### Changed
- **BREAKING (internal)**: `save_volume_triggers` now uses correct column names
  - `adjustment_value` → `adjustment_multiplier`
  - `created_at` → `detected_at`
- Trigger thresholds now scale-aware (conversion-first, not RPS-first)
- Preflight passes DB triggers via `trigger_overrides` (eliminates duplicate query)

### Added
- `get_active_volume_triggers` enhanced response v2.0:
  - `compound_multiplier` - pre-calculated compound value
  - `compound_calculation` - per-content-type breakdown
  - `has_conflicting_signals` - flags BOOST+REDUCE on same content
  - `zero_triggers_context` - diagnostics when no triggers
  - `metadata` block with hash and timestamps
  - `creator_context` with fan_count and tier
- `volume_utils.py` trigger constants:
  - `TRIGGER_THRESHOLDS` - canonical threshold definitions
  - `validate_trigger()` - input validation function
  - `calculate_compound_multiplier()` - compound calculation
  - `TRIGGER_MULT_MIN/MAX` - compound bounds [0.50, 2.00]
- Database migration script for indexes on `volume_triggers` table
- Three-tier test suite (unit, integration, preflight)
- `adapters.py` support for `trigger_overrides` parameter

### Fixed
- `save_volume_triggers` column name bugs (CRITICAL)
- Trigger deduplication in preflight (DB + runtime merge)
- Missing `metrics_json` in SELECT and INSERT
- `FeedbackCapture` now accepts string paths (was only Path objects)

### Deprecated
- RPS-only trigger detection (conversion rate now primary signal)

---

## [1.6.0] - 2026-01-08

### Added
- `mcp_server/volume_utils.py` - Single source of truth for tier calculations
- Enhanced `get_volume_config` with week-specific weekly_distribution
- Simulation parameters: trigger_overrides, tier_override, health_override
- Audit hash: volume_config_hash for traceability
- Calendar awareness: holiday and payday boosts in response
- Prime hours by day of week in weekly_distribution
- `python/tests/test_volume_utils.py` - 80 tests with 100% coverage
- `python/tests/test_mcp_volume.py` - 25 integration tests for enhanced tool

### Fixed
- **BUG 1**: Eliminated duplicate tier thresholds (was in 3 places, now 1)
- **BUG 2**: week_start parameter now used for calendar calculations
- **BUG 3**: get_volume_config is now differentiated from bundled response

### Changed
- `get_creator_profile` volume_assignment uses volume_utils
- `preflight.py` imports tier constants from volume_utils
- Prime hours moved to volume_utils.PRIME_HOURS (string keys)
- Health calculation volume_adjustment: -1 for DEATH_SPIRAL (was 0)

### Technical
- 5 atomic commits for safe rollback
- 100% test coverage on volume_utils.py
- Property-based tests for tier boundary verification

---

## [1.5.0] - 2026-01-08

### Added
- Persona data bundled into `get_creator_profile` via `include_persona=True` (default)
- `get_persona_profile` standalone tool for management/debug access
- Persona fields: primary_tone, secondary_tone, emoji_frequency, slang_level

### Changed
- `get_creator_profile` now returns persona data by default
- Preflight MCP calls reduced from 4 to 3

---

## [1.4.0] - 2026-01-08

### Fixed
- **CRITICAL**: `get_content_type_rankings` now filters by latest `analysis_date` to prevent stale data mixing
- Applied same `analysis_date` filter to bundled query in `get_creator_profile`

### Changed
- `get_content_type_rankings` response structure: `content_types` → `rankings`
- Preflight method renamed: `_top_types` → `_all_content_rankings` (accuracy)
- Preflight now uses pre-computed `avoid_types` from bundled response

### Added
- `include_metrics` parameter for lightweight validation-only calls
- `metadata.rankings_hash` for ValidationCertificate integrity
- `metadata.avoid_types_hash` for HARD GATE verification
- `metadata.analysis_date`, `data_age_days`, `is_stale` for observability
- 7 new tests for `get_content_type_rankings`

### Backward Compatibility
- Legacy keys (`top_content_types`, `avoid_types`, `top_types`) preserved at root in bundled response
- Preflight has fallbacks for old response structures

---

## [1.3.0] - 2026-01-08

### Changed
- **RENAMED**: `get_vault_availability` → `get_allowed_content_types`
  - Clearer semantic: returns content types a creator "allows" for scheduling
  - Simplified response structure (removed quantity_available, quality_rating, notes)
  - Response now uses `allowed_types` and `allowed_type_names` instead of `available_types` and `type_names`
- **SIMPLIFIED**: Response structure reduced from ~15 fields to 4 core fields
  - `allowed_types` - list with type_name, type_category, is_explicit
  - `allowed_type_names` - simple string list for validation
  - `type_count` - number of allowed types
  - `vault_hash` - deterministic hash for ValidationCertificate
- **UPDATED**: `get_creator_profile` bundled response now uses `allowed_content_types` key instead of `vault_availability`

### Removed
- `include_quality`, `include_notes`, `min_quantity` parameters (no longer needed)
- `content_count`, `quality_rating`, `updated_at`, `notes` fields from response
- `total_available` field (was redundant with type_count)

---

## [1.2.0] - 2026-01-08

### Changed
- **ENHANCED**: `get_active_creators` now supports pagination and advanced filtering
  - New params: `offset`, `page_type`, `min_revenue`, `max_revenue`, `min_fan_count`
  - New params: `sort_by` (revenue/fan_count/name/tier), `sort_order` (asc/desc)
  - New param: `include_volume_details` for daily volume breakdown
- Response now includes `total_count`, `metadata.has_more`, `metadata.page_info`
- Added comprehensive creator fields: display_name, timezone, metrics_snapshot_date
- Invalid tier/page_type values now return validation error (was silently ignored)

### Added
- Pagination metadata: `page_info.current_page`, `page_info.total_pages`
- Flexible sorting with NULL handling (NULLS LAST)
- Volume details optional inclusion to reduce payload size

---

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
