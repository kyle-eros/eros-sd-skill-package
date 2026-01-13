# python/tests/test_mcp_triggers_integration.py (NEW FILE)

"""
Integration tests for volume triggers MCP tools.
Uses real SQLite database to catch SQL column name bugs.
"""

import pytest
import sqlite3
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
import sys
import os
import time

# Add project root to path for mcp_server package imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def test_db():
    """Create real SQLite database with production schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)

    # Create tables with correct schema
    conn.execute("""
        CREATE TABLE creators (
            creator_id TEXT PRIMARY KEY,
            page_name TEXT,
            is_active INTEGER DEFAULT 1,
            current_fan_count INTEGER,
            page_type TEXT DEFAULT 'paid'
        )
    """)

    conn.execute("""
        CREATE TABLE volume_assignments (
            creator_id TEXT,
            volume_level TEXT,
            is_active INTEGER DEFAULT 1,
            assigned_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE volume_triggers (
            trigger_id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id TEXT NOT NULL,
            content_type TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            adjustment_multiplier REAL NOT NULL,
            reason TEXT NOT NULL,
            confidence TEXT NOT NULL DEFAULT 'moderate',
            metrics_json TEXT,
            detected_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            applied_count INTEGER DEFAULT 0,
            last_applied_at TEXT,
            detection_count INTEGER NOT NULL DEFAULT 1,
            first_detected_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Create indexes
    conn.execute("""
        CREATE INDEX idx_volume_triggers_active_creator
        ON volume_triggers(creator_id, expires_at)
        WHERE is_active = 1
    """)

    # Full unique index (not partial) required for ON CONFLICT to work
    conn.execute("""
        CREATE UNIQUE INDEX idx_volume_triggers_natural_key
        ON volume_triggers(creator_id, content_type, trigger_type)
    """)

    # Seed test data
    conn.execute("""
        INSERT INTO creators (creator_id, page_name, is_active, current_fan_count, page_type)
        VALUES ('test_creator', 'testpage', 1, 10000, 'paid')
    """)

    conn.execute("""
        INSERT INTO volume_assignments (creator_id, volume_level, is_active)
        VALUES ('test_creator', 'STANDARD', 1)
    """)

    expires = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("""
        INSERT INTO volume_triggers (
            creator_id, content_type, trigger_type,
            adjustment_multiplier, confidence, reason,
            expires_at, detected_at, is_active, metrics_json
        ) VALUES (
            'test_creator', 'lingerie', 'HIGH_PERFORMER',
            1.20, 'high', 'Conversion 7.2%',
            ?, datetime('now'), 1, '{"v":2,"detected":{"conversion_rate":7.2}}'
        )
    """, (expires,))

    conn.commit()
    conn.close()

    yield db_path

    Path(db_path).unlink()


class TestRealDatabaseQueries:
    """Integration tests that catch SQL column name bugs."""

    def test_get_active_volume_triggers_sql_executes(self, test_db, monkeypatch):
        """This test would FAIL if column names are wrong."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        # Force module reload to pick up test DB
        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.get_active_volume_triggers("test_creator")

        assert "error" not in result
        assert result["count"] == 1
        assert result["triggers"][0]["trigger_type"] == "HIGH_PERFORMER"
        assert result["triggers"][0]["adjustment_multiplier"] == 1.20

    def test_response_has_new_fields(self, test_db, monkeypatch):
        """Verify new response schema fields are present."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.get_active_volume_triggers("test_creator")

        # New fields
        assert "creator_id_resolved" in result
        assert "compound_multiplier" in result
        assert "compound_calculation" in result
        assert "has_conflicting_signals" in result
        assert "creator_context" in result
        assert "metadata" in result

        # Metadata fields
        assert "triggers_hash" in result["metadata"]
        assert "thresholds_version" in result["metadata"]

    def test_creator_context_populated(self, test_db, monkeypatch):
        """Verify creator context is correct."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.get_active_volume_triggers("test_creator")

        assert result["creator_context"]["fan_count"] == 10000
        assert result["creator_context"]["tier"] == "STANDARD"

    def test_zero_triggers_context(self, test_db, monkeypatch):
        """Test zero_triggers_context when no active triggers."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        # Create creator with no triggers
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO creators (creator_id, page_name, is_active, current_fan_count)
            VALUES ('no_triggers', 'notriggers', 1, 5000)
        """)
        conn.commit()
        conn.close()

        result = main_module.get_active_volume_triggers("no_triggers")

        assert result["count"] == 0
        assert result["zero_triggers_context"] is not None
        assert result["zero_triggers_context"]["reason"] == "never_had_triggers"

    def test_metrics_json_parsed(self, test_db, monkeypatch):
        """Verify metrics_json is parsed correctly."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.get_active_volume_triggers("test_creator")

        trigger = result["triggers"][0]
        assert "metrics_json" in trigger
        assert trigger["metrics_json"]["v"] == 2
        assert trigger["metrics_json"]["detected"]["conversion_rate"] == 7.2


class TestSaveVolumeTriggers:
    """Test save_volume_triggers with real database."""

    def test_save_uses_correct_column_names(self, test_db, monkeypatch):
        """This test catches the adjustment_value/created_at bugs."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "TRENDING_UP",
            "content_type": "bikini",
            "adjustment_multiplier": 1.10,
            "confidence": "moderate",
            "reason": "WoW revenue +18%"
        }])

        # With buggy column names, this would throw:
        # sqlite3.OperationalError: table volume_triggers has no column named adjustment_value
        assert result["success"] == True
        assert result["triggers_saved"] == 1

    def test_save_validation_rejects_invalid_batch(self, test_db, monkeypatch):
        """Entire batch rejected if any trigger invalid."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.save_volume_triggers("test_creator", [
            {"trigger_type": "HIGH_PERFORMER", "content_type": "x", "adjustment_multiplier": 1.2},
            {"trigger_type": "INVALID", "content_type": "y", "adjustment_multiplier": 1.1}  # Bad
        ])

        assert result["success"] == False
        assert "validation_errors" in result
        assert result.get("triggers_saved", 0) == 0

    def test_save_with_metrics_json(self, test_db, monkeypatch):
        """Verify metrics_json is persisted correctly."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        metrics = {
            "v": 2,
            "detected": {"conversion_rate": 8.5, "weekly_revenue": 15000}
        }

        result = main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "HIGH_PERFORMER",
            "content_type": "cosplay",
            "adjustment_multiplier": 1.20,
            "metrics_json": metrics
        }])

        assert result["success"] == True

        # Verify metrics_json was stored
        conn = sqlite3.connect(test_db)
        row = conn.execute("""
            SELECT metrics_json FROM volume_triggers
            WHERE content_type = 'cosplay'
        """).fetchone()
        conn.close()

        stored_metrics = json.loads(row[0])
        assert stored_metrics["v"] == 2
        assert stored_metrics["detected"]["conversion_rate"] == 8.5

    def test_save_empty_list_succeeds(self, test_db, monkeypatch):
        """Empty trigger list should succeed with 0 saved."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.save_volume_triggers("test_creator", [])

        assert result["success"] == True
        assert result["triggers_saved"] == 0

    def test_save_unknown_creator_fails(self, test_db, monkeypatch):
        """Unknown creator should fail."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.save_volume_triggers("unknown_creator", [{
            "trigger_type": "HIGH_PERFORMER",
            "content_type": "x",
            "adjustment_multiplier": 1.2
        }])

        assert result["success"] == False
        assert result["error_code"] == "CREATOR_NOT_FOUND"


class TestOnConflictBehavior:
    """Tests for UPSERT behavior with ON CONFLICT."""

    def test_redetection_updates_existing_trigger(self, test_db, monkeypatch):
        """Re-detection updates existing row instead of creating new."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        # First save - creates new trigger
        result1 = main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "TRENDING_UP",
            "content_type": "bikini",
            "adjustment_multiplier": 1.10
        }])
        assert result1["success"]
        assert len(result1["created_ids"]) == 1
        assert len(result1["updated_ids"]) == 0

        # Second save - should update, not create
        result2 = main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "TRENDING_UP",
            "content_type": "bikini",
            "adjustment_multiplier": 1.15
        }])
        assert result2["success"]
        assert len(result2["created_ids"]) == 0
        assert len(result2["updated_ids"]) == 1

        # Verify same trigger_id
        assert result1["created_ids"][0] == result2["updated_ids"][0]

    def test_detection_count_increments(self, test_db, monkeypatch):
        """detection_count increments from 1 to 2 on re-detection."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        # First save
        main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "EMERGING_WINNER",
            "content_type": "cosplay",
            "adjustment_multiplier": 1.05
        }])

        # Check detection_count = 1
        conn = sqlite3.connect(test_db)
        row = conn.execute("""
            SELECT detection_count FROM volume_triggers
            WHERE content_type = 'cosplay' AND trigger_type = 'EMERGING_WINNER'
        """).fetchone()
        conn.close()
        assert row[0] == 1

        # Re-save
        main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "EMERGING_WINNER",
            "content_type": "cosplay",
            "adjustment_multiplier": 1.08
        }])

        # Check detection_count = 2
        conn = sqlite3.connect(test_db)
        row = conn.execute("""
            SELECT detection_count FROM volume_triggers
            WHERE content_type = 'cosplay' AND trigger_type = 'EMERGING_WINNER'
        """).fetchone()
        conn.close()
        assert row[0] == 2

    def test_first_detected_at_preserved(self, test_db, monkeypatch):
        """first_detected_at unchanged on re-detection."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        # First save
        main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "SATURATING",
            "content_type": "gym",
            "adjustment_multiplier": 0.85
        }])

        # Get original first_detected_at
        conn = sqlite3.connect(test_db)
        row1 = conn.execute("""
            SELECT first_detected_at, detected_at FROM volume_triggers
            WHERE content_type = 'gym' AND trigger_type = 'SATURATING'
        """).fetchone()
        conn.close()
        original_first = row1[0]

        # Wait >1 second to ensure datetime('now') produces different value
        # (SQLite datetime has second precision)
        time.sleep(1.1)
        main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "SATURATING",
            "content_type": "gym",
            "adjustment_multiplier": 0.80
        }])

        # Verify first_detected_at unchanged but detected_at updated
        conn = sqlite3.connect(test_db)
        row2 = conn.execute("""
            SELECT first_detected_at, detected_at FROM volume_triggers
            WHERE content_type = 'gym' AND trigger_type = 'SATURATING'
        """).fetchone()
        conn.close()

        assert row2[0] == original_first  # first_detected_at preserved
        assert row2[1] != row1[1]  # detected_at updated


class TestReturnSchema:
    """Tests for v3.0.0 response schema."""

    def test_created_ids_on_new_triggers(self, test_db, monkeypatch):
        """New triggers appear in created_ids list."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "TRENDING_UP",
            "content_type": "outdoor",
            "adjustment_multiplier": 1.12
        }])

        assert result["success"]
        assert "created_ids" in result
        assert "updated_ids" in result
        assert len(result["created_ids"]) == 1
        assert len(result["updated_ids"]) == 0
        assert isinstance(result["created_ids"][0], int)

    def test_metadata_block_complete(self, test_db, monkeypatch):
        """metadata contains persisted_at, execution_ms, triggers_hash."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "HIGH_PERFORMER",
            "content_type": "athletic",
            "adjustment_multiplier": 1.20
        }])

        assert "metadata" in result
        assert "persisted_at" in result["metadata"]
        assert "execution_ms" in result["metadata"]
        assert "triggers_hash" in result["metadata"]

        # Verify types
        assert isinstance(result["metadata"]["execution_ms"], float)
        assert result["metadata"]["triggers_hash"].startswith("sha256:")

    def test_triggers_hash_is_deterministic(self, test_db, monkeypatch):
        """Same triggers produce same hash (verified via re-save)."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        triggers = [{
            "trigger_type": "HIGH_PERFORMER",
            "content_type": "hashtest",
            "adjustment_multiplier": 1.25,
            "confidence": "high"
        }]

        result1 = main_module.save_volume_triggers("test_creator", triggers)
        result2 = main_module.save_volume_triggers("test_creator", triggers)

        assert result1["metadata"]["triggers_hash"] == result2["metadata"]["triggers_hash"]


class TestOverwriteWarnings:
    """Tests for direction flip and large delta warnings."""

    def test_direction_flip_warning_boost_to_reduce(self, test_db, monkeypatch):
        """Warning when multiplier goes from >1.0 to <1.0."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        # First: boost (>1.0)
        main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "HIGH_PERFORMER",
            "content_type": "flip_test",
            "adjustment_multiplier": 1.20
        }])

        # Second: reduce (<1.0) - direction flip
        result = main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "HIGH_PERFORMER",
            "content_type": "flip_test",
            "adjustment_multiplier": 0.85
        }])

        assert result["overwrite_warnings"] is not None
        assert len(result["overwrite_warnings"]) == 1
        assert result["overwrite_warnings"][0]["direction_flip"] == True
        assert result["overwrite_warnings"][0]["old_multiplier"] == 1.20
        assert result["overwrite_warnings"][0]["new_multiplier"] == 0.85

    def test_large_delta_warning_over_50_percent(self, test_db, monkeypatch):
        """Warning when multiplier changes by more than 50%."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        # First: 1.0
        main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "TRENDING_UP",
            "content_type": "delta_test",
            "adjustment_multiplier": 1.00
        }])

        # Second: 1.60 (60% increase)
        result = main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "TRENDING_UP",
            "content_type": "delta_test",
            "adjustment_multiplier": 1.60
        }])

        assert result["overwrite_warnings"] is not None
        assert len(result["overwrite_warnings"]) == 1
        assert abs(result["overwrite_warnings"][0]["delta_percent"]) > 50

    def test_no_warning_for_small_delta(self, test_db, monkeypatch):
        """No warning when multiplier changes by less than 50%."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        # First: 1.10
        main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "EMERGING_WINNER",
            "content_type": "small_delta",
            "adjustment_multiplier": 1.10
        }])

        # Second: 1.15 (4.5% increase)
        result = main_module.save_volume_triggers("test_creator", [{
            "trigger_type": "EMERGING_WINNER",
            "content_type": "small_delta",
            "adjustment_multiplier": 1.15
        }])

        # Should have no overwrite warnings (small change, no direction flip)
        assert result["overwrite_warnings"] is None or len(result["overwrite_warnings"]) == 0


class TestBatchWarnings:
    """Tests for large batch warning."""

    def test_large_batch_warning_over_20(self, test_db, monkeypatch):
        """Warning when batch contains more than 20 triggers."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        # Create 21 triggers (exceeds threshold of 20)
        triggers = [
            {
                "trigger_type": "TRENDING_UP",
                "content_type": f"type_{i}",
                "adjustment_multiplier": 1.10
            }
            for i in range(21)
        ]

        result = main_module.save_volume_triggers("test_creator", triggers)

        assert result["success"]
        assert result["warnings"] is not None
        assert any("Large batch" in w for w in result["warnings"])

    def test_no_warning_for_normal_batch(self, test_db, monkeypatch):
        """No warning when batch contains 20 or fewer triggers."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        # Create 3 triggers (under threshold)
        triggers = [
            {"trigger_type": "HIGH_PERFORMER", "content_type": "a", "adjustment_multiplier": 1.20},
            {"trigger_type": "TRENDING_UP", "content_type": "b", "adjustment_multiplier": 1.10},
            {"trigger_type": "EMERGING_WINNER", "content_type": "c", "adjustment_multiplier": 1.05}
        ]

        result = main_module.save_volume_triggers("test_creator", triggers)

        assert result["success"]
        # warnings might be None or empty, but no "Large batch" warning
        if result["warnings"]:
            assert not any("Large batch" in w for w in result["warnings"])


class TestGetActiveVolumeTriggersNewFields:
    """Tests for get_active_volume_triggers new v3.0.0 fields."""

    def test_detection_count_in_response(self, test_db, monkeypatch):
        """detection_count field present in trigger objects."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.get_active_volume_triggers("test_creator")

        assert result["count"] >= 1
        trigger = result["triggers"][0]
        assert "detection_count" in trigger
        assert isinstance(trigger["detection_count"], int)
        assert trigger["detection_count"] >= 1

    def test_first_detected_at_in_response(self, test_db, monkeypatch):
        """first_detected_at field present in trigger objects."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.get_active_volume_triggers("test_creator")

        assert result["count"] >= 1
        trigger = result["triggers"][0]
        assert "first_detected_at" in trigger

    def test_days_since_first_detected(self, test_db, monkeypatch):
        """days_since_first_detected calculated correctly."""
        monkeypatch.setenv("EROS_DB_PATH", test_db)

        import importlib
        import mcp_server.main as main_module
        importlib.reload(main_module)

        result = main_module.get_active_volume_triggers("test_creator")

        assert result["count"] >= 1
        trigger = result["triggers"][0]
        assert "days_since_first_detected" in trigger
        # For a newly created trigger, should be 0 or 1
        assert trigger["days_since_first_detected"] >= 0
