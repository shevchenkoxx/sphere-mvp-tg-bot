-- Migration: Add matching_scope and meeting_preference to users
-- matching_scope: 'city' (default) or 'global'
-- meeting_preference: 'online', 'offline', or 'both' (default)

ALTER TABLE users ADD COLUMN IF NOT EXISTS matching_scope TEXT DEFAULT 'city';
ALTER TABLE users ADD COLUMN IF NOT EXISTS meeting_preference TEXT DEFAULT 'both';
