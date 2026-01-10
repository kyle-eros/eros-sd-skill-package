-- migrations/add_trigger_indexes.sql
-- Run: sqlite3 data/eros_sd_main.db < migrations/add_trigger_indexes.sql

-- ============================================================
-- STEP 1: Add last_applied_at column (outside transaction)
-- ============================================================
-- Check if column exists first. If this fails, column already exists - that's OK.
-- SQLite will error on duplicate column, so we handle gracefully.

-- Run this manually first to check:
-- SELECT COUNT(*) FROM pragma_table_info('volume_triggers') WHERE name='last_applied_at';
-- If result is 0, run the ALTER. If result is 1, skip it.

ALTER TABLE volume_triggers ADD COLUMN last_applied_at TEXT;

-- ============================================================
-- STEP 2: Create indexes (idempotent with IF NOT EXISTS)
-- ============================================================

-- INDEX 1: Primary query path (get_active_volume_triggers, get_volume_config)
-- Partial index excludes inactive triggers
CREATE INDEX IF NOT EXISTS idx_volume_triggers_active_creator
ON volume_triggers(creator_id, expires_at)
WHERE is_active = 1;

-- INDEX 2: Expiration cleanup job
CREATE INDEX IF NOT EXISTS idx_volume_triggers_expiration
ON volume_triggers(expires_at)
WHERE is_active = 1 AND expires_at IS NOT NULL;

-- INDEX 3: Upsert deduplication (save_volume_triggers uses INSERT OR REPLACE)
-- Natural key for proper REPLACE behavior
CREATE UNIQUE INDEX IF NOT EXISTS idx_volume_triggers_natural_key
ON volume_triggers(creator_id, content_type, trigger_type)
WHERE is_active = 1;

-- ============================================================
-- STEP 3: Update query planner statistics
-- ============================================================
ANALYZE volume_triggers;

-- ============================================================
-- STEP 4: Verify indexes created
-- ============================================================
SELECT name, sql FROM sqlite_master
WHERE type='index' AND tbl_name='volume_triggers';
