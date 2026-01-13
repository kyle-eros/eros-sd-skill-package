# python/tests/test_mcp_triggers.py (NEW FILE)

"""
Unit tests for volume triggers MCP tools.
Uses mocked database for fast logic validation.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

# Add mcp_server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))


class TestGetActiveVolumeTriggers:
    """Unit tests for get_active_volume_triggers."""

    @pytest.fixture
    def mock_db_connection(self):
        """Create mock database connection."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        return mock_conn

    def test_returns_error_for_empty_creator_id(self):
        """Empty creator_id should return error."""
        from main import get_active_volume_triggers

        result = get_active_volume_triggers("")
        assert "error" in result
        assert result["error_code"] == "INVALID_INPUT"
        assert result["triggers"] == []
        assert result["count"] == 0

    def test_returns_error_for_unknown_creator(self, mock_db_connection):
        """Unknown creator should return error."""
        from main import get_active_volume_triggers

        mock_db_connection.execute.return_value.fetchone.return_value = None

        with patch("main.get_db_connection", return_value=mock_db_connection):
            result = get_active_volume_triggers("unknown_creator")

        assert "error" in result
        assert result["error_code"] == "CREATOR_NOT_FOUND"

    def test_response_has_required_fields(self, mock_db_connection):
        """Response should have all required fields."""
        from main import get_active_volume_triggers

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            ("cr_123", "testpage", 10000, "paid", "STANDARD"),  # Creator row
        ]
        # Columns: trigger_id, content_type, trigger_type, adjustment_multiplier, confidence,
        #          reason, expires_at, detected_at, metrics_json, applied_count, last_applied_at,
        #          detection_count, first_detected_at, days_until_expiry, days_since_detected,
        #          days_since_first_detected
        mock_db_connection.execute.return_value.fetchall.return_value = [
            (1, "lingerie", "HIGH_PERFORMER", 1.20, "high", "Test",
             "2026-01-20", "2026-01-10", '{}', 0, None, 1, "2026-01-10", 10, 0, 0)
        ]

        with patch("main.get_db_connection", return_value=mock_db_connection):
            result = get_active_volume_triggers("test_creator")

        # Core fields
        assert "creator_id" in result
        assert "creator_id_resolved" in result
        assert "triggers" in result
        assert "count" in result

        # New fields
        assert "compound_multiplier" in result
        assert "compound_calculation" in result
        assert "has_conflicting_signals" in result
        assert "creator_context" in result
        assert "metadata" in result

    def test_compound_multiplier_calculated(self, mock_db_connection):
        """Compound multiplier should be calculated from triggers."""
        from main import get_active_volume_triggers

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            ("cr_123", "testpage", 10000, "paid", "STANDARD"),
        ]
        # Columns: trigger_id, content_type, trigger_type, adjustment_multiplier, confidence,
        #          reason, expires_at, detected_at, metrics_json, applied_count, last_applied_at,
        #          detection_count, first_detected_at, days_until_expiry, days_since_detected,
        #          days_since_first_detected
        mock_db_connection.execute.return_value.fetchall.return_value = [
            (1, "lingerie", "HIGH_PERFORMER", 1.20, "high", "Test",
             "2026-01-20", "2026-01-10", '{}', 0, None, 1, "2026-01-10", 10, 0, 0),
            (2, "lingerie", "SATURATING", 0.85, "moderate", "Test",
             "2026-01-20", "2026-01-10", '{}', 0, None, 1, "2026-01-10", 10, 0, 0)
        ]

        with patch("main.get_db_connection", return_value=mock_db_connection):
            result = get_active_volume_triggers("test_creator")

        assert result["compound_multiplier"] == pytest.approx(1.02, rel=1e-2)
        assert result["has_conflicting_signals"] == True

    def test_creator_context_populated(self, mock_db_connection):
        """Creator context should have fan_count and tier."""
        from main import get_active_volume_triggers

        # Create separate mock for each execute call
        mock_creator_result = MagicMock()
        mock_creator_result.fetchone.return_value = ("cr_123", "testpage", 40000, "paid", "PREMIUM")

        mock_triggers_result = MagicMock()
        mock_triggers_result.fetchall.return_value = []

        # Zero triggers diagnostics query
        mock_diag_result = MagicMock()
        mock_diag_result.fetchone.return_value = (None, None, None, 0, 0)

        mock_db_connection.execute.side_effect = [
            mock_creator_result,  # Creator lookup
            mock_triggers_result,  # Triggers query
            mock_diag_result,  # Zero triggers diagnostics
        ]

        with patch("main.get_db_connection", return_value=mock_db_connection):
            result = get_active_volume_triggers("test_creator")

        # Check we got a valid response (not an error)
        assert "error" not in result or result.get("error") is None, f"Got error: {result.get('error')}"
        assert result["creator_context"]["fan_count"] == 40000
        assert result["creator_context"]["tier"] == "PREMIUM"


class TestBackwardCompatibility:
    """Ensure old consumer code still works."""

    @pytest.fixture
    def mock_db_connection(self):
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        return mock_conn

    def test_old_consumer_pattern_works(self, mock_db_connection):
        """Old code pattern: triggers = response.get('triggers', [])"""
        from main import get_active_volume_triggers

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            ("cr_123", "testpage", 10000, "paid", "STANDARD"),
        ]
        # Columns: trigger_id, content_type, trigger_type, adjustment_multiplier, confidence,
        #          reason, expires_at, detected_at, metrics_json, applied_count, last_applied_at,
        #          detection_count, first_detected_at, days_until_expiry, days_since_detected,
        #          days_since_first_detected
        mock_db_connection.execute.return_value.fetchall.return_value = [
            (1, "lingerie", "HIGH_PERFORMER", 1.20, "high", "Test",
             "2026-01-20", "2026-01-10", '{}', 0, None, 1, "2026-01-10", 10, 0, 0)
        ]

        with patch("main.get_db_connection", return_value=mock_db_connection):
            response = get_active_volume_triggers("test_creator")

        # OLD consumer code pattern
        triggers = response.get("triggers", [])
        assert isinstance(triggers, list)

        total_mult = 1.0
        for tr in triggers:
            mult = tr.get("adjustment_multiplier", 1.0)
            assert isinstance(mult, (int, float))
            total_mult *= mult

        assert total_mult > 0

    def test_count_at_root_level(self, mock_db_connection):
        """count field must be at root level."""
        from main import get_active_volume_triggers

        mock_db_connection.execute.return_value.fetchone.side_effect = [
            ("cr_123", "testpage", 10000, "paid", "STANDARD"),
        ]
        mock_db_connection.execute.return_value.fetchall.return_value = []

        with patch("main.get_db_connection", return_value=mock_db_connection):
            response = get_active_volume_triggers("test_creator")

        assert "count" in response
        assert response["count"] == len(response.get("triggers", []))
