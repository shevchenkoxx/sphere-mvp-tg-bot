-- Migration: 005_speed_dating
-- Description: Add speed_dating_conversations table for AI Speed Dating feature
-- This table caches generated AI conversations between matched users

CREATE TABLE speed_dating_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    viewer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_text TEXT NOT NULL,
    language VARCHAR(5) DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_speed_dating_per_viewer UNIQUE (match_id, viewer_user_id)
);

-- Index for fast lookup by match_id and viewer_user_id
CREATE INDEX idx_speed_dating_lookup ON speed_dating_conversations(match_id, viewer_user_id);

-- Comment on table
COMMENT ON TABLE speed_dating_conversations IS 'Cached AI-generated speed dating conversations between matched users';
