# Ralph Wiggum Loop: Implement get_schedules MCP Tool

## COMPLETION PROMISE
When ALL of the following are true, output: `<promise>GET_SCHEDULES_COMPLETE</promise>`
1. `get_schedules` function exists in `/Users/kylemerriman/Developer/eros-sd-skill-package/mcp_server/main.py`
2. Function has `@mcp.tool()` decorator
3. All tests pass: `python3 -m pytest python/tests/test_get_schedules.py -v`
4. Tool is documented with proper docstring following existing patterns

---

## TASK OVERVIEW

Implement a new MCP tool `get_schedules` that retrieves saved schedules from the `schedule_templates` table. This is the READ counterpart to the existing `save_schedule` tool.

---

## DATABASE SCHEMA (schedule_templates)

```sql
CREATE TABLE schedule_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id TEXT NOT NULL,
    week_start TEXT NOT NULL,
    week_end TEXT NOT NULL,
    generated_at TEXT DEFAULT (datetime('now')),
    generated_by TEXT,
    algorithm_version TEXT,
    total_items INTEGER DEFAULT 0,
    total_ppvs INTEGER DEFAULT 0,
    total_bumps INTEGER DEFAULT 0,
    projected_earnings REAL,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'queued', 'completed')),
    scheduler_id INTEGER,
    actual_earnings REAL,
    completion_rate REAL,
    notes TEXT,
    algorithm_params TEXT,
    agent_execution_log TEXT,
    quality_validation_score REAL,
    health_status TEXT DEFAULT 'HEALTHY',
    creator_tier TEXT,
    generation_metadata JSON,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id),
    UNIQUE(creator_id, week_start)
);
```

---

## REQUIRED FUNCTION SIGNATURE

```python
@mcp.tool()
def get_schedules(
    creator_id: str = None,           # Optional: filter by creator (page_name or creator_id)
    week_start: str = None,           # Optional: filter by specific week (YYYY-MM-DD)
    status: str = None,               # Optional: filter by status (draft/approved/queued/completed)
    limit: int = 50,                  # Max results (clamped 1-500, default 50)
    offset: int = 0,                  # Pagination offset
    include_items: bool = False,      # Include full schedule items from generation_metadata
    sort_by: str = "generated_at",    # Sort field: generated_at, week_start, status
    sort_order: str = "desc"          # Sort direction: asc, desc
) -> dict:
```

---

## REQUIRED RESPONSE SCHEMA

### Success Response
```python
{
    "schedules": [
        {
            "schedule_id": int,           # template_id
            "creator_id": str,            # creator UUID
            "creator_page_name": str,     # resolved page_name for convenience
            "week_start": str,            # YYYY-MM-DD
            "week_end": str,              # YYYY-MM-DD
            "status": str,                # draft/approved/queued/completed
            "total_items": int,
            "total_ppvs": int,
            "total_bumps": int,
            "projected_earnings": float | None,
            "actual_earnings": float | None,
            "completion_rate": float | None,
            "quality_validation_score": float | None,
            "health_status": str,
            "generated_at": str,          # ISO timestamp
            "items": list | None          # Only if include_items=True
        }
    ],
    "count": int,                     # Number returned in this response
    "total_count": int,               # Total matching (for pagination)
    "limit": int,
    "offset": int,
    "has_more": bool,
    "metadata": {
        "fetched_at": str,            # ISO timestamp
        "tool_version": str,          # "2.0.0"
        "filters_applied": {
            "creator_id": str | None,
            "week_start": str | None,
            "status": str | None
        },
        "sort": {
            "by": str,
            "order": str
        }
    }
}
```

### Error Response
```python
{
    "error": str,
    "error_code": str,                # INVALID_CREATOR, INVALID_DATE, INVALID_STATUS, etc.
    "schedules": [],
    "count": 0,
    "total_count": 0,
    "metadata": {
        "fetched_at": str,
        "error": True
    }
}
```

---

## IMPLEMENTATION REQUIREMENTS

### 1. Input Validation
- `creator_id`: If provided, resolve using `resolve_creator_id()` helper
- `week_start`: If provided, validate YYYY-MM-DD format
- `status`: If provided, must be one of: draft, approved, queued, completed
- `limit`: Clamp to range [1, 500]
- `sort_by`: Must be one of: generated_at, week_start, status
- `sort_order`: Must be: asc or desc

### 2. Query Construction
- Build dynamic WHERE clause based on provided filters
- Use parameterized queries (NO SQL injection)
- JOIN with creators table to get page_name
- Count total matching records separately for pagination

### 3. Items Extraction
- When `include_items=True`, parse `generation_metadata` JSON
- Extract `items` array from metadata
- Handle malformed JSON gracefully (return null, don't fail)

### 4. Pattern Compliance
- Follow existing tool patterns in main.py
- Use `logger.info()` for operation logging
- Use `get_db_connection()` context manager
- Include execution time in metadata

---

## TEST FILE REQUIREMENTS

Create `/Users/kylemerriman/Developer/eros-sd-skill-package/python/tests/test_get_schedules.py`:

### Required Test Classes

```python
class TestGetSchedulesBasic:
    """Basic retrieval and empty state tests."""

    def test_returns_empty_list_when_no_schedules(self):
        """Test empty database returns empty list, not error."""

    def test_returns_required_response_fields(self):
        """Test all required fields present in response."""

    def test_metadata_includes_fetched_at(self):
        """Test metadata has timestamp."""

class TestGetSchedulesFiltering:
    """Filter parameter tests."""

    def test_filter_by_creator_id(self):
        """Test creator_id filter works."""

    def test_filter_by_status(self):
        """Test status filter works."""

    def test_filter_by_week_start(self):
        """Test week_start filter works."""

    def test_invalid_status_returns_error(self):
        """Test invalid status value returns error."""

    def test_invalid_creator_returns_error(self):
        """Test nonexistent creator returns error (if strict) or empty."""

class TestGetSchedulesPagination:
    """Pagination tests."""

    def test_limit_clamps_to_max(self):
        """Test limit > 500 is clamped."""

    def test_offset_works(self):
        """Test offset skips records."""

    def test_has_more_flag(self):
        """Test has_more is accurate."""

class TestGetSchedulesIncludeItems:
    """include_items parameter tests."""

    def test_items_excluded_by_default(self):
        """Test items not returned when include_items=False."""

    def test_items_included_when_requested(self):
        """Test items returned when include_items=True."""

    def test_handles_malformed_metadata(self):
        """Test graceful handling of bad JSON."""

class TestGetSchedulesSorting:
    """Sorting tests."""

    def test_default_sort_desc(self):
        """Test default sort is generated_at desc."""

    def test_sort_asc(self):
        """Test ascending sort works."""

    def test_invalid_sort_field_returns_error(self):
        """Test invalid sort_by returns error."""
```

---

## LOCATION IN main.py

Insert the new function AFTER `save_schedule` (around line 2560) and BEFORE `save_volume_triggers`.

---

## ITERATION CHECKLIST

Each iteration, check:

1. [ ] Does `get_schedules` function exist with `@mcp.tool()` decorator?
2. [ ] Does docstring follow MCP tool pattern (MCP Name, Version, Args, Returns)?
3. [ ] Does function handle all parameters correctly?
4. [ ] Does response match required schema?
5. [ ] Does test file exist?
6. [ ] Do all tests pass? Run: `python3 -m pytest python/tests/test_get_schedules.py -v`

If ANY check fails, fix it and continue.

---

## COMMANDS TO VERIFY

```bash
# Check function exists
grep -n "def get_schedules" /Users/kylemerriman/Developer/eros-sd-skill-package/mcp_server/main.py

# Check decorator
grep -B1 "def get_schedules" /Users/kylemerriman/Developer/eros-sd-skill-package/mcp_server/main.py

# Run tests
python3 -m pytest /Users/kylemerriman/Developer/eros-sd-skill-package/python/tests/test_get_schedules.py -v

# Quick import check
python3 -c "from mcp_server.main import get_schedules; print('Import OK')"
```

---

## ANTI-PATTERNS TO AVOID

1. **NO raw SQL without parameterization** - Always use `?` placeholders
2. **NO silent failures** - Log errors, return error responses
3. **NO assumptions** - Validate all inputs
4. **NO backwards incompatible changes** - This is a new tool, but follow patterns
5. **NO skipping tests** - All tests must pass

---

## SUCCESS CRITERIA

The task is COMPLETE when:
1. `get_schedules` is implemented in main.py with proper decorator
2. Function signature matches specification
3. Response schema matches specification
4. Test file exists with all test classes
5. **ALL TESTS PASS**

When complete, output: `<promise>GET_SCHEDULES_COMPLETE</promise>`
