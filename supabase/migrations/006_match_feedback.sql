-- Migration: Add match feedback table
-- Created: 2026-02-04
-- Purpose: Store user feedback on match quality (good/bad)

-- Create match_feedback table
CREATE TABLE IF NOT EXISTS match_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feedback_type VARCHAR(10) NOT NULL CHECK (feedback_type IN ('good', 'bad')),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- One feedback per user per match
    CONSTRAINT unique_feedback_per_user_match UNIQUE (match_id, user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_match_feedback_match ON match_feedback(match_id);
CREATE INDEX IF NOT EXISTS idx_match_feedback_user ON match_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_match_feedback_type ON match_feedback(feedback_type);

-- Comment
COMMENT ON TABLE match_feedback IS 'Stores user feedback on match quality for improving matching algorithm';
