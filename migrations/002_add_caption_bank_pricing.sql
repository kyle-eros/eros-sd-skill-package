-- Migration: 002_add_caption_bank_pricing
-- Purpose: Add pricing columns for PPV optimization
-- Date: 2026-01-12
-- Version: get_batch_captions_by_content_types v2.0.0

-- Add pricing columns to caption_bank
ALTER TABLE caption_bank ADD COLUMN suggested_price REAL;
ALTER TABLE caption_bank ADD COLUMN price_range_min REAL DEFAULT 5.00;
ALTER TABLE caption_bank ADD COLUMN price_range_max REAL DEFAULT 50.00;
ALTER TABLE caption_bank ADD COLUMN avg_purchase_rate REAL;
ALTER TABLE caption_bank ADD COLUMN schedulable_type TEXT;

-- Index for filtering by schedulable_type
CREATE INDEX IF NOT EXISTS idx_caption_bank_schedulable
    ON caption_bank(schedulable_type, is_active);

-- Backfill schedulable_type based on caption_type
UPDATE caption_bank
SET schedulable_type = CASE
    WHEN caption_type IN ('ppv', 'ppv_unlock', 'ppv_wall', 'ppv_message') THEN 'ppv'
    WHEN caption_type IN ('bump', 'bump_normal', 'bump_descriptive') THEN 'ppv_bump'
    WHEN caption_type IN ('wall', 'wall_post') THEN 'wall'
    ELSE NULL
END
WHERE schedulable_type IS NULL;
