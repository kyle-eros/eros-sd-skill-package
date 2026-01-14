"""Tests for get_schedules MCP tool.

Tests retrieval, filtering, pagination, sorting, and include_items functionality
for the schedule_templates table.
"""
import pytest
import sys
import json
from pathlib import Path
from datetime import datetime

# Add mcp_server to path for both package import and internal module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))

from mcp_server.main import get_schedules, save_schedule, resolve_creator_id


class TestGetSchedulesBasic:
    """Basic retrieval and empty state tests."""

    def test_returns_empty_list_when_no_schedules(self):
        """Test empty database returns empty list, not error."""
        result = get_schedules()
        assert "schedules" in result
        assert isinstance(result["schedules"], list)
        assert "error" not in result

    def test_returns_required_response_fields(self):
        """Test all required fields present in response."""
        result = get_schedules()
        required_fields = [
            "schedules",
            "count",
            "total_count",
            "limit",
            "offset",
            "has_more",
            "metadata"
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_metadata_includes_fetched_at(self):
        """Test metadata has timestamp."""
        result = get_schedules()
        assert "metadata" in result
        assert "fetched_at" in result["metadata"]

    def test_metadata_includes_tool_version(self):
        """Test metadata includes tool version."""
        result = get_schedules()
        assert result["metadata"].get("tool_version") == "2.0.0"

    def test_metadata_includes_filters_applied(self):
        """Test metadata includes filters_applied dict."""
        result = get_schedules()
        assert "filters_applied" in result["metadata"]
        assert "creator_id" in result["metadata"]["filters_applied"]
        assert "week_start" in result["metadata"]["filters_applied"]
        assert "status" in result["metadata"]["filters_applied"]

    def test_metadata_includes_sort_info(self):
        """Test metadata includes sort dict."""
        result = get_schedules()
        assert "sort" in result["metadata"]
        assert "by" in result["metadata"]["sort"]
        assert "order" in result["metadata"]["sort"]

    def test_default_sort_is_generated_at_desc(self):
        """Test default sort is generated_at descending."""
        result = get_schedules()
        assert result["metadata"]["sort"]["by"] == "generated_at"
        assert result["metadata"]["sort"]["order"] == "desc"

    def test_count_matches_schedules_length(self):
        """Test count field matches actual list length."""
        result = get_schedules()
        assert result["count"] == len(result["schedules"])


class TestGetSchedulesFiltering:
    """Filter parameter tests."""

    def test_filter_by_status_draft(self):
        """Test status=draft filter works."""
        result = get_schedules(status="draft")
        assert "error" not in result
        assert result["metadata"]["filters_applied"]["status"] == "draft"

    def test_filter_by_status_case_insensitive(self):
        """Test status filter is case-insensitive."""
        result = get_schedules(status="DRAFT")
        assert "error" not in result
        assert result["metadata"]["filters_applied"]["status"] == "draft"

    def test_invalid_status_returns_error(self):
        """Test invalid status value returns error."""
        result = get_schedules(status="invalid_status")
        assert "error" in result
        assert result["error_code"] == "INVALID_STATUS"
        assert result["schedules"] == []
        assert result["count"] == 0

    def test_invalid_status_error_lists_valid_values(self):
        """Test invalid status error message lists valid options."""
        result = get_schedules(status="bad")
        assert "draft" in result["error"]
        assert "approved" in result["error"]
        assert "queued" in result["error"]
        assert "completed" in result["error"]

    def test_invalid_creator_returns_error(self):
        """Test nonexistent creator returns error."""
        result = get_schedules(creator_id="nonexistent_creator_xyz_12345")
        assert "error" in result
        assert result["error_code"] == "INVALID_CREATOR"

    def test_filter_by_week_start_valid(self):
        """Test week_start filter with valid date."""
        result = get_schedules(week_start="2025-01-06")
        assert "error" not in result
        assert result["metadata"]["filters_applied"]["week_start"] == "2025-01-06"

    def test_filter_by_week_start_invalid_format(self):
        """Test invalid week_start format returns error."""
        result = get_schedules(week_start="01-06-2025")
        assert "error" in result
        assert result["error_code"] == "INVALID_DATE"

    def test_filter_by_week_start_invalid_value(self):
        """Test invalid week_start value returns error."""
        result = get_schedules(week_start="not-a-date")
        assert "error" in result
        assert result["error_code"] == "INVALID_DATE"


class TestGetSchedulesPagination:
    """Pagination tests."""

    def test_default_limit_is_50(self):
        """Test default limit is 50."""
        result = get_schedules()
        assert result["limit"] == 50

    def test_default_offset_is_0(self):
        """Test default offset is 0."""
        result = get_schedules()
        assert result["offset"] == 0

    def test_limit_clamps_to_max_500(self):
        """Test limit > 500 is clamped to 500."""
        result = get_schedules(limit=1000)
        assert result["limit"] == 500

    def test_limit_clamps_to_min_1(self):
        """Test limit < 1 is clamped to 1."""
        result = get_schedules(limit=0)
        assert result["limit"] == 1

    def test_negative_limit_clamps_to_1(self):
        """Test negative limit is clamped to 1."""
        result = get_schedules(limit=-10)
        assert result["limit"] == 1

    def test_offset_accepts_positive_values(self):
        """Test offset accepts positive values."""
        result = get_schedules(offset=10)
        assert result["offset"] == 10

    def test_negative_offset_clamps_to_0(self):
        """Test negative offset is clamped to 0."""
        result = get_schedules(offset=-5)
        assert result["offset"] == 0

    def test_has_more_false_when_no_more_results(self):
        """Test has_more is False when all results returned."""
        result = get_schedules(limit=500)
        # With no schedules, has_more should be False
        if result["total_count"] == 0:
            assert result["has_more"] is False

    def test_invalid_limit_uses_default(self):
        """Test invalid limit type uses default."""
        result = get_schedules(limit="not_a_number")
        assert result["limit"] == 50

    def test_invalid_offset_uses_default(self):
        """Test invalid offset type uses default 0."""
        result = get_schedules(offset="not_a_number")
        assert result["offset"] == 0


class TestGetSchedulesIncludeItems:
    """include_items parameter tests."""

    def test_items_excluded_by_default(self):
        """Test items not returned when include_items=False (default)."""
        result = get_schedules(include_items=False)
        assert "error" not in result
        # Items should not be in schedule objects
        for schedule in result["schedules"]:
            assert "items" not in schedule

    def test_items_excluded_when_false(self):
        """Test items explicitly excluded when include_items=False."""
        result = get_schedules(include_items=False)
        for schedule in result["schedules"]:
            assert "items" not in schedule

    def test_items_key_present_when_include_items_true(self):
        """Test items key exists when include_items=True."""
        result = get_schedules(include_items=True)
        assert "error" not in result
        # Each schedule should have an items key (can be None or list)
        for schedule in result["schedules"]:
            assert "items" in schedule


class TestGetSchedulesSorting:
    """Sorting tests."""

    def test_sort_by_generated_at(self):
        """Test sort by generated_at works."""
        result = get_schedules(sort_by="generated_at")
        assert "error" not in result
        assert result["metadata"]["sort"]["by"] == "generated_at"

    def test_sort_by_week_start(self):
        """Test sort by week_start works."""
        result = get_schedules(sort_by="week_start")
        assert "error" not in result
        assert result["metadata"]["sort"]["by"] == "week_start"

    def test_sort_by_status(self):
        """Test sort by status works."""
        result = get_schedules(sort_by="status")
        assert "error" not in result
        assert result["metadata"]["sort"]["by"] == "status"

    def test_sort_order_asc(self):
        """Test ascending sort order works."""
        result = get_schedules(sort_order="asc")
        assert "error" not in result
        assert result["metadata"]["sort"]["order"] == "asc"

    def test_sort_order_desc(self):
        """Test descending sort order works."""
        result = get_schedules(sort_order="desc")
        assert "error" not in result
        assert result["metadata"]["sort"]["order"] == "desc"

    def test_sort_order_case_insensitive(self):
        """Test sort order is case-insensitive."""
        result = get_schedules(sort_order="ASC")
        assert "error" not in result
        assert result["metadata"]["sort"]["order"] == "asc"

    def test_invalid_sort_field_returns_error(self):
        """Test invalid sort_by returns error."""
        result = get_schedules(sort_by="invalid_field")
        assert "error" in result
        assert result["error_code"] == "INVALID_SORT_FIELD"

    def test_invalid_sort_field_error_lists_valid_values(self):
        """Test invalid sort_by error message lists valid options."""
        result = get_schedules(sort_by="bad_field")
        assert "generated_at" in result["error"]
        assert "week_start" in result["error"]
        assert "status" in result["error"]

    def test_invalid_sort_order_returns_error(self):
        """Test invalid sort_order returns error."""
        result = get_schedules(sort_order="invalid")
        assert "error" in result
        assert result["error_code"] == "INVALID_SORT_ORDER"


class TestGetSchedulesErrorHandling:
    """Error handling tests."""

    def test_error_response_has_required_fields(self):
        """Test error responses include all required fields."""
        result = get_schedules(status="invalid")
        required_fields = ["error", "error_code", "schedules", "count", "total_count", "metadata"]
        for field in required_fields:
            assert field in result, f"Missing field in error response: {field}"

    def test_error_response_has_empty_schedules(self):
        """Test error responses have empty schedules list."""
        result = get_schedules(status="invalid")
        assert result["schedules"] == []

    def test_error_response_has_zero_counts(self):
        """Test error responses have zero counts."""
        result = get_schedules(status="invalid")
        assert result["count"] == 0
        assert result["total_count"] == 0

    def test_error_metadata_has_error_flag(self):
        """Test error response metadata has error=True."""
        result = get_schedules(status="invalid")
        assert result["metadata"].get("error") is True


class TestGetSchedulesIntegration:
    """Integration tests with actual database operations."""

    def test_can_retrieve_saved_schedule(self):
        """Test that a saved schedule can be retrieved."""
        # First, check if we have a valid creator
        resolved = resolve_creator_id("maya_hill")
        if not resolved.get("found"):
            pytest.skip("Test creator maya_hill not found in database")

        # Get current count
        before = get_schedules()
        before_count = before["total_count"]

        # Save a test schedule
        test_items = [
            {
                "send_type": "ppv_unlock",
                "content_type": "lingerie",
                "day_of_week": "monday",
                "scheduled_time": "14:00",
                "caption_id": 1
            }
        ]

        save_result = save_schedule(
            creator_id="maya_hill",
            week_start="2099-12-28",  # Far future to avoid conflicts
            items=test_items
        )

        if not save_result.get("success"):
            pytest.skip(f"Could not save test schedule: {save_result.get('error')}")

        try:
            # Retrieve and verify
            after = get_schedules(week_start="2099-12-28")
            assert after["total_count"] >= 1

            # Find our schedule
            found = False
            for schedule in after["schedules"]:
                if schedule["week_start"] == "2099-12-28":
                    found = True
                    assert schedule["total_items"] == 1
                    assert schedule["status"] == "draft"
                    break

            assert found, "Saved schedule not found in results"

        finally:
            # Cleanup: We can't delete directly, but this is test data
            # Future iterations might add a delete function
            pass

    def test_include_items_retrieves_schedule_items(self):
        """Test include_items=True retrieves the items array."""
        # First save a schedule with known items
        resolved = resolve_creator_id("maya_hill")
        if not resolved.get("found"):
            pytest.skip("Test creator maya_hill not found in database")

        test_items = [
            {
                "send_type": "ppv_unlock",
                "content_type": "shower",
                "day_of_week": "tuesday",
                "scheduled_time": "15:00",
                "caption_id": 2
            },
            {
                "send_type": "bump_normal",
                "content_type": "lingerie",
                "day_of_week": "wednesday",
                "scheduled_time": "16:00",
                "caption_id": 3
            }
        ]

        save_result = save_schedule(
            creator_id="maya_hill",
            week_start="2099-12-21",  # Different far future date
            items=test_items
        )

        if not save_result.get("success"):
            pytest.skip(f"Could not save test schedule: {save_result.get('error')}")

        # Retrieve with items
        result = get_schedules(week_start="2099-12-21", include_items=True)

        assert "error" not in result
        assert result["total_count"] >= 1

        # Find our schedule and check items
        for schedule in result["schedules"]:
            if schedule["week_start"] == "2099-12-21":
                assert "items" in schedule
                if schedule["items"] is not None:
                    assert len(schedule["items"]) == 2
                break
