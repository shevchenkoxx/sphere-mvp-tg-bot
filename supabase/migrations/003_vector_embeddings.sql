-- Migration: Vector Embeddings for AI-powered matching
-- Run this in Supabase SQL Editor after 002 (enhanced profiles)
-- Requires pgvector extension to be enabled in Supabase Dashboard

-- ============================================
-- ENABLE PGVECTOR EXTENSION
-- ============================================
-- Note: Enable via Supabase Dashboard → Database → Extensions → vector
-- Or run this (requires superuser):
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- ADD EMBEDDING COLUMNS
-- OpenAI text-embedding-3-small = 1536 dimensions
-- ============================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_embedding vector(1536);
ALTER TABLE users ADD COLUMN IF NOT EXISTS interests_embedding vector(1536);
ALTER TABLE users ADD COLUMN IF NOT EXISTS expertise_embedding vector(1536);

-- ============================================
-- CREATE INDEXES FOR FAST SIMILARITY SEARCH
-- Using IVFFlat index with cosine similarity
-- lists = 100 is good for up to ~1M rows
-- ============================================
CREATE INDEX IF NOT EXISTS idx_users_profile_embedding
  ON users USING ivfflat (profile_embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_users_interests_embedding
  ON users USING ivfflat (interests_embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_users_expertise_embedding
  ON users USING ivfflat (expertise_embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================
-- FUNCTION: FIND SIMILAR USERS WITHIN AN EVENT
-- Returns candidates ranked by weighted similarity
-- ============================================
CREATE OR REPLACE FUNCTION match_candidates(
    query_user_id uuid,
    query_event_id uuid,
    similarity_threshold float8 DEFAULT 0.65,
    limit_count int DEFAULT 10
)
RETURNS TABLE (
    user_id uuid,
    similarity_score float8,
    profile_sim float8,
    interests_sim float8,
    expertise_sim float8
) AS $$
DECLARE
    query_profile vector(1536);
    query_interests vector(1536);
    query_expertise vector(1536);
BEGIN
    -- Get embeddings for query user
    SELECT u.profile_embedding, u.interests_embedding, u.expertise_embedding
    INTO query_profile, query_interests, query_expertise
    FROM users u WHERE u.id = query_user_id;

    -- If query user has no embeddings, return empty
    IF query_profile IS NULL THEN
        RETURN;
    END IF;

    -- Return matching candidates
    RETURN QUERY
    SELECT
        u.id as user_id,
        -- Weighted similarity score
        -- Profile: 40%, Interests: 35%, Expertise: 25%
        (
            0.40 * (1 - (u.profile_embedding <=> query_profile)) +
            0.35 * COALESCE((1 - (u.interests_embedding <=> query_interests)), 0.5) +
            0.25 * COALESCE((1 - (u.expertise_embedding <=> query_expertise)), 0.5)
        )::float8 as similarity_score,
        (1 - (u.profile_embedding <=> query_profile))::float8 as profile_sim,
        COALESCE((1 - (u.interests_embedding <=> query_interests)), 0.5)::float8 as interests_sim,
        COALESCE((1 - (u.expertise_embedding <=> query_expertise)), 0.5)::float8 as expertise_sim
    FROM users u
    INNER JOIN event_participants ep ON u.id = ep.user_id
    WHERE ep.event_id = query_event_id
        AND u.id != query_user_id
        AND u.profile_embedding IS NOT NULL
        AND (
            -- At least one embedding should meet threshold
            (1 - (u.profile_embedding <=> query_profile)) >= similarity_threshold OR
            (query_interests IS NOT NULL AND u.interests_embedding IS NOT NULL AND
             (1 - (u.interests_embedding <=> query_interests)) >= similarity_threshold)
        )
    ORDER BY similarity_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VERIFICATION QUERY
-- ============================================
-- Run this to verify columns and function were created:
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'users' AND column_name LIKE '%embedding%';
--
-- Test the function:
-- SELECT * FROM match_candidates('user-uuid-here', 'event-uuid-here', 0.65, 10);
