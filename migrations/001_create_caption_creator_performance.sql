-- Migration: 001_create_caption_creator_performance
-- Purpose: Enable per-creator caption usage tracking
-- Date: 2026-01-12
-- Version: get_batch_captions_by_content_types v2.0.0

CREATE TABLE IF NOT EXISTS caption_creator_performance (
    ccp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    caption_id INTEGER NOT NULL,
    creator_id TEXT NOT NULL,
    times_used INTEGER DEFAULT 0,
    last_used_date TEXT,
    first_used_date TEXT,
    avg_rps REAL,
    avg_conversion_rate REAL,
    total_revenue REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (caption_id) REFERENCES caption_bank(caption_id) ON DELETE CASCADE,
    FOREIGN KEY (creator_id) REFERENCES creators(creator_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ccp_natural_key
    ON caption_creator_performance(caption_id, creator_id);

CREATE INDEX IF NOT EXISTS idx_ccp_creator_last_used
    ON caption_creator_performance(creator_id, last_used_date);

CREATE INDEX IF NOT EXISTS idx_ccp_caption
    ON caption_creator_performance(caption_id);

CREATE INDEX IF NOT EXISTS idx_ccp_freshness
    ON caption_creator_performance(creator_id, times_used, last_used_date);

CREATE TRIGGER IF NOT EXISTS trg_ccp_updated_at
AFTER UPDATE ON caption_creator_performance
FOR EACH ROW
BEGIN
    UPDATE caption_creator_performance
    SET updated_at = datetime('now')
    WHERE ccp_id = NEW.ccp_id;
END;
