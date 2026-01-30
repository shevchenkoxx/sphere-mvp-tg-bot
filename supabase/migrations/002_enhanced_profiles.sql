-- Migration: Enhanced Profiles
-- Run this in Supabase SQL Editor after 001 (initial schema)

-- ============================================
-- ADD CURRENT EVENT TRACKING (CRITICAL)
-- ============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS current_event_id UUID REFERENCES events(id);

-- ============================================
-- ENHANCED PROFILE FIELDS
-- ============================================

-- Professional info
ALTER TABLE users ADD COLUMN IF NOT EXISTS profession VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS company VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT '{}';

-- What they want/offer
ALTER TABLE users ADD COLUMN IF NOT EXISTS looking_for TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS can_help_with TEXT;

-- Language
ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'ru';

-- ============================================
-- DEEP PROFILE (LLM-generated analysis)
-- ============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS deep_profile JSONB DEFAULT '{}';

-- ============================================
-- AUDIO DATA
-- ============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS audio_transcription TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS raw_highlights TEXT[] DEFAULT '{}';

-- ============================================
-- SOCIAL/LINKEDIN
-- ============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_url TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_data JSONB DEFAULT '{}';

-- ============================================
-- NEW INDEX FOR CURRENT EVENT
-- ============================================
CREATE INDEX IF NOT EXISTS idx_users_current_event ON users(current_event_id);

-- ============================================
-- UPDATE MATCHES TABLE FOR BETTER TOP-N
-- ============================================
ALTER TABLE matches ADD COLUMN IF NOT EXISTS rank_for_user_a INT;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS rank_for_user_b INT;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS mutual_score FLOAT;

-- Index for fast top-N queries
CREATE INDEX IF NOT EXISTS idx_matches_ranking ON matches(event_id, user_a_id, compatibility_score DESC);

-- ============================================
-- VERIFICATION
-- ============================================
-- Run this to verify columns were added:
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users';
