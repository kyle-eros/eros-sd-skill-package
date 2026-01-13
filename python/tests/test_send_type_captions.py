"""Tests for get_send_type_captions MCP tool v2.0.0.

Tests cover:
- Four-layer validation (Layer 1-4)
- Per-creator freshness filtering
- Pool statistics accuracy
- Error handling and response schemas
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

# Import the MCP server module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "mcp_server"))


class TestGetSendTypeCaptionsValidation:
    """Test four-layer validation for get_send_type_captions."""

    @pytest.fixture
    def mock_db_path(self, tmp_path):
        """Create a temporary database with test fixtures."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Create required tables
        cursor.execute("""
            CREATE TABLE creators (
                creator_id TEXT PRIMARY KEY,
                page_name TEXT,
                display_name TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        cursor.execute("""
            CREATE TABLE send_types (
                send_type_id INTEGER PRIMARY KEY,
                send_type_key TEXT UNIQUE NOT NULL,
                category TEXT,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 100
            )
        """)
        cursor.execute("""
            CREATE TABLE caption_bank (
                caption_id INTEGER PRIMARY KEY AUTOINCREMENT,
                caption_text TEXT NOT NULL,
                caption_type TEXT NOT NULL,
                content_type_id INTEGER,
                is_active INTEGER DEFAULT 1,
                performance_tier INTEGER DEFAULT 3,
                global_last_used_date TEXT,
                caption_hash TEXT DEFAULT ''
            )
        """)
        cursor.execute("""
            CREATE TABLE caption_creator_performance (
                caption_id INTEGER,
                creator_id TEXT,
                times_used INTEGER DEFAULT 0,
                last_used_date TEXT,
                PRIMARY KEY (caption_id, creator_id)
            )
        """)

        # Insert test data
        cursor.execute("INSERT INTO creators VALUES ('alexia', 'alexia', 'Alexia', 1)")
        cursor.execute("INSERT INTO creators VALUES ('luna', 'luna', 'Luna', 1)")
        cursor.execute("INSERT INTO send_types (send_type_key, category, is_active, sort_order) VALUES ('bump_normal', 'engagement', 1, 1)")
        cursor.execute("INSERT INTO send_types (send_type_key, category, is_active, sort_order) VALUES ('ppv_unlock', 'revenue', 1, 2)")
        cursor.execute("INSERT INTO send_types (send_type_key, category, is_active, sort_order) VALUES ('dm_farm', 'engagement', 1, 3)")

        # Insert bump_normal captions
        for i in range(15):
            cursor.execute(
                "INSERT INTO caption_bank (caption_text, caption_type, content_type_id, performance_tier) VALUES (?, 'bump_normal', ?, ?)",
                (f"Bump caption {i}", i % 5, (i % 3) + 1)
            )

        # Insert ppv_unlock captions
        for i in range(10):
            cursor.execute(
                "INSERT INTO caption_bank (caption_text, caption_type, content_type_id, performance_tier) VALUES (?, 'ppv_unlock', ?, ?)",
                (f"PPV caption {i}", i % 3, (i % 3) + 1)
            )

        # Insert creator performance data (some fresh, some stale)
        today = date.today().isoformat()
        old_date = (date.today() - timedelta(days=100)).isoformat()
        recent_date = (date.today() - timedelta(days=30)).isoformat()

        # Caption 1 used recently by alexia (stale)
        cursor.execute("INSERT INTO caption_creator_performance VALUES (1, 'alexia', 3, ?)", (recent_date,))
        # Caption 2 used long ago by alexia (effectively fresh)
        cursor.execute("INSERT INTO caption_creator_performance VALUES (2, 'alexia', 2, ?)", (old_date,))
        # Caption 3 never used by alexia (fresh - no entry)

        conn.commit()
        conn.close()

        return str(db_path)

    def test_layer1_invalid_creator_id_empty(self, mock_db_path):
        """Layer 1: Empty creator_id returns structured error."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_path}):
            # Re-import to pick up patched DB path
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("", "bump_normal", 5)

            assert "error" in result
            assert result["error_code"] == "INVALID_CREATOR_ID"
            assert result["captions"] == []
            assert result["pool_stats"]["total_available"] == 0
            assert result["metadata"]["error"] is True

    def test_layer1_invalid_creator_id_none(self, mock_db_path):
        """Layer 1: None creator_id returns structured error."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_path}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions(None, "bump_normal", 5)

            assert result["error_code"] == "INVALID_CREATOR_ID"

    def test_layer1_invalid_send_type_empty(self, mock_db_path):
        """Layer 1: Empty send_type returns structured error."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_path}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("alexia", "", 5)

            assert result["error_code"] == "INVALID_SEND_TYPE"

    def test_layer2_invalid_send_type_format(self, mock_db_path):
        """Layer 2: Invalid send_type format (special chars) returns error."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_path}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("alexia", "bump@normal!", 5)

            assert result["error_code"] == "INVALID_SEND_TYPE_FORMAT"

    def test_layer3_creator_not_found(self, mock_db_path):
        """Layer 3: Non-existent creator returns CREATOR_NOT_FOUND error."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_path}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("nonexistent_creator", "bump_normal", 5)

            assert result["error_code"] == "CREATOR_NOT_FOUND"

    def test_layer3_send_type_not_in_table(self, mock_db_path):
        """Layer 3: Non-existent send_type returns SEND_TYPE_NOT_FOUND error."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_path}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("alexia", "nonexistent_type", 5)

            assert result["error_code"] == "SEND_TYPE_NOT_FOUND"
            assert "Valid types:" in result["error"]


class TestGetSendTypeCaptionsFreshness:
    """Test per-creator freshness filtering."""

    @pytest.fixture
    def mock_db_with_freshness(self, tmp_path):
        """Create database with specific freshness test scenarios."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Create tables
        cursor.execute("""
            CREATE TABLE creators (
                creator_id TEXT PRIMARY KEY,
                page_name TEXT,
                display_name TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        cursor.execute("""
            CREATE TABLE send_types (
                send_type_id INTEGER PRIMARY KEY,
                send_type_key TEXT UNIQUE NOT NULL,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 100
            )
        """)
        cursor.execute("""
            CREATE TABLE caption_bank (
                caption_id INTEGER PRIMARY KEY AUTOINCREMENT,
                caption_text TEXT NOT NULL,
                caption_type TEXT NOT NULL,
                content_type_id INTEGER,
                is_active INTEGER DEFAULT 1,
                performance_tier INTEGER DEFAULT 3,
                global_last_used_date TEXT,
                caption_hash TEXT DEFAULT ''
            )
        """)
        cursor.execute("""
            CREATE TABLE caption_creator_performance (
                caption_id INTEGER,
                creator_id TEXT,
                times_used INTEGER DEFAULT 0,
                last_used_date TEXT,
                PRIMARY KEY (caption_id, creator_id)
            )
        """)

        # Insert test data
        cursor.execute("INSERT INTO creators VALUES ('alexia', 'alexia', 'Alexia', 1)")
        cursor.execute("INSERT INTO send_types VALUES (1, 'bump_normal', 1, 1)")

        # Caption 1: Never used (fresh, top tier)
        cursor.execute("INSERT INTO caption_bank VALUES (1, 'Never used caption', 'bump_normal', 1, 1, 1, NULL, '')")

        # Caption 2: Used 100 days ago (effectively fresh, tier 2)
        cursor.execute("INSERT INTO caption_bank VALUES (2, 'Old used caption', 'bump_normal', 1, 1, 2, NULL, '')")
        old_date = (date.today() - timedelta(days=100)).isoformat()
        cursor.execute("INSERT INTO caption_creator_performance VALUES (2, 'alexia', 2, ?)", (old_date,))

        # Caption 3: Used 30 days ago (stale, tier 1 - best performance)
        cursor.execute("INSERT INTO caption_bank VALUES (3, 'Recently used caption', 'bump_normal', 1, 1, 1, NULL, '')")
        recent_date = (date.today() - timedelta(days=30)).isoformat()
        cursor.execute("INSERT INTO caption_creator_performance VALUES (3, 'alexia', 5, ?)", (recent_date,))

        conn.commit()
        conn.close()

        return str(db_path)

    def test_fresh_captions_ordered_first(self, mock_db_with_freshness):
        """Fresh captions (never used or >90 days) should appear before stale ones."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_with_freshness}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("alexia", "bump_normal", 10)

            assert "error" not in result
            assert len(result["captions"]) == 3

            # Fresh captions should be first
            caption_ids = [c["caption_id"] for c in result["captions"]]

            # Caption 3 (stale, tier 1) should be LAST despite best performance tier
            # Caption 1 (fresh, never used) and 2 (fresh, old) should be first
            assert result["captions"][0]["effectively_fresh"] == 1
            assert result["captions"][1]["effectively_fresh"] == 1
            assert result["captions"][2]["effectively_fresh"] == 0

    def test_pool_stats_accuracy(self, mock_db_with_freshness):
        """Pool stats should accurately reflect total and fresh caption counts."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_with_freshness}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("alexia", "bump_normal", 10)

            assert result["pool_stats"]["total_available"] == 3
            assert result["pool_stats"]["fresh_for_creator"] == 2  # 1 never used, 1 >90 days old
            assert result["pool_stats"]["returned_count"] == 3
            assert result["pool_stats"]["has_more"] is False
            assert result["pool_stats"]["freshness_ratio"] == pytest.approx(0.667, rel=0.01)


class TestGetSendTypeCaptionsSuccessPath:
    """Test successful response schema and metadata."""

    @pytest.fixture
    def mock_db_simple(self, tmp_path):
        """Create simple database for success path tests."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE creators (creator_id TEXT PRIMARY KEY, page_name TEXT, display_name TEXT, is_active INTEGER DEFAULT 1)
        """)
        cursor.execute("""
            CREATE TABLE send_types (send_type_id INTEGER PRIMARY KEY, send_type_key TEXT UNIQUE, is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 100)
        """)
        cursor.execute("""
            CREATE TABLE caption_bank (caption_id INTEGER PRIMARY KEY, caption_text TEXT, caption_type TEXT, content_type_id INTEGER, is_active INTEGER DEFAULT 1, performance_tier INTEGER DEFAULT 3, global_last_used_date TEXT, caption_hash TEXT DEFAULT '')
        """)
        cursor.execute("""
            CREATE TABLE caption_creator_performance (caption_id INTEGER, creator_id TEXT, times_used INTEGER, last_used_date TEXT, PRIMARY KEY (caption_id, creator_id))
        """)

        cursor.execute("INSERT INTO creators VALUES ('alexia', 'alexia', 'Alexia', 1)")
        cursor.execute("INSERT INTO send_types VALUES (1, 'bump_normal', 1, 1)")

        for i in range(5):
            cursor.execute(
                "INSERT INTO caption_bank VALUES (?, ?, 'bump_normal', ?, 1, ?, NULL, '')",
                (i + 1, f"Caption {i}", i, i + 1)
            )

        conn.commit()
        conn.close()
        return str(db_path)

    def test_success_response_has_all_fields(self, mock_db_simple):
        """Success response should include all required fields."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_simple}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("alexia", "bump_normal", 5)

            # Top-level fields
            assert result["creator_id"] == "alexia"
            assert result["resolved_creator_id"] == "alexia"
            assert result["send_type"] == "bump_normal"
            assert isinstance(result["captions"], list)
            assert result["count"] == 5

            # Pool stats
            assert "total_available" in result["pool_stats"]
            assert "fresh_for_creator" in result["pool_stats"]
            assert "returned_count" in result["pool_stats"]
            assert "has_more" in result["pool_stats"]
            assert "freshness_ratio" in result["pool_stats"]

            # Metadata
            assert "fetched_at" in result["metadata"]
            assert "query_ms" in result["metadata"]
            assert result["metadata"]["tool_version"] == "2.0.0"
            assert result["metadata"]["freshness_threshold_days"] == 90

    def test_caption_fields_include_freshness(self, mock_db_simple):
        """Each caption should include freshness-related fields."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_simple}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("alexia", "bump_normal", 1)

            caption = result["captions"][0]
            assert "caption_id" in caption
            assert "caption_text" in caption
            assert "category" in caption
            assert "performance_tier" in caption
            assert "creator_use_count" in caption
            assert "effectively_fresh" in caption

    def test_empty_result_valid_schema(self, mock_db_simple):
        """Empty result (no matching captions) should return valid schema, not error."""
        with patch.dict(os.environ, {"EROS_DB_PATH": mock_db_simple}):
            import importlib
            import mcp_server.main as main_module
            importlib.reload(main_module)

            # Add dm_farm to send_types but no captions for it
            conn = sqlite3.connect(mock_db_simple)
            conn.execute("INSERT INTO send_types VALUES (2, 'dm_farm', 1, 2)")
            conn.commit()
            conn.close()

            # Re-import after DB change
            importlib.reload(main_module)

            result = main_module.get_send_type_captions("alexia", "dm_farm", 5)

            # Should NOT be an error
            assert "error" not in result
            assert result["captions"] == []
            assert result["count"] == 0
            assert result["pool_stats"]["total_available"] == 0
            assert result["pool_stats"]["has_more"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
