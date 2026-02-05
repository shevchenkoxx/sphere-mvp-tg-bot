-- Migration: Add event_info JSONB field for rich event data
-- Run: psql connection -f supabase/migrations/007_event_info.sql

-- Add event_info column to events table
ALTER TABLE events ADD COLUMN IF NOT EXISTS event_info JSONB DEFAULT '{}';

-- Structure of event_info:
-- {
--   "full_description": "Detailed event description",
--   "schedule": [
--     {"time": "10:00", "title": "Opening", "speaker": "John Doe", "description": "..."}
--   ],
--   "speakers": [
--     {"name": "John Doe", "bio": "CEO of X", "social": "@johndoe", "topics": ["AI"]}
--   ],
--   "topics": ["AI", "Startups", "Web3"],
--   "organizer": {
--     "name": "TechHub",
--     "social": "@techhub",
--     "website": "https://techhub.com",
--     "telegram": "@techhub_channel"
--   },
--   "venue_details": "Floor 3, Room A",
--   "source_url": "https://lu.ma/event123",
--   "imported_at": "2026-02-05T12:00:00Z"
-- }

-- Index for faster JSONB queries
CREATE INDEX IF NOT EXISTS idx_events_event_info ON events USING GIN (event_info);

COMMENT ON COLUMN events.event_info IS 'Rich event data: schedule, speakers, topics, organizer info';
