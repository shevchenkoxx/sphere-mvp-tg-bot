-- Migration 009: Security Hardening
-- Fixes all Supabase security advisor warnings:
-- 1. Enable RLS on all public tables
-- 2. Fix mutable search_path on functions
-- 3. Move vector extension to separate schema
--
-- IMPORTANT: Bot uses service_role key which bypasses RLS.
-- These policies are defense-in-depth for anon/authenticated roles.

-- ============================================
-- 1. ENABLE RLS ON ALL TABLES
-- ============================================

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.event_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.match_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.speed_dating_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meetup_proposals ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 2. RLS POLICIES
-- service_role bypasses RLS automatically.
-- Block all access for anon and authenticated roles
-- (bot is the only client, uses service_role).
-- ============================================

-- Users
CREATE POLICY "Deny all for anon" ON public.users FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for authenticated" ON public.users FOR ALL TO authenticated USING (false);

-- Matches
CREATE POLICY "Deny all for anon" ON public.matches FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for authenticated" ON public.matches FOR ALL TO authenticated USING (false);

-- Events
CREATE POLICY "Deny all for anon" ON public.events FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for authenticated" ON public.events FOR ALL TO authenticated USING (false);

-- Event participants
CREATE POLICY "Deny all for anon" ON public.event_participants FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for authenticated" ON public.event_participants FOR ALL TO authenticated USING (false);

-- Messages
CREATE POLICY "Deny all for anon" ON public.messages FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for authenticated" ON public.messages FOR ALL TO authenticated USING (false);

-- Match feedback
CREATE POLICY "Deny all for anon" ON public.match_feedback FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for authenticated" ON public.match_feedback FOR ALL TO authenticated USING (false);

-- Speed dating conversations
CREATE POLICY "Deny all for anon" ON public.speed_dating_conversations FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for authenticated" ON public.speed_dating_conversations FOR ALL TO authenticated USING (false);

-- Meetup proposals
CREATE POLICY "Deny all for anon" ON public.meetup_proposals FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for authenticated" ON public.meetup_proposals FOR ALL TO authenticated USING (false);

-- ============================================
-- 3. FIX FUNCTION SEARCH_PATH
-- Set immutable search_path to prevent
-- search_path hijacking attacks.
-- ============================================

-- Fix update_updated_at function
ALTER FUNCTION public.update_updated_at() SET search_path = public, extensions;

-- Fix match_candidates function
-- Recreate with SET search_path
CREATE OR REPLACE FUNCTION public.match_candidates(
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
            (1 - (u.profile_embedding <=> query_profile)) >= similarity_threshold OR
            (query_interests IS NOT NULL AND u.interests_embedding IS NOT NULL AND
             (1 - (u.interests_embedding <=> query_interests)) >= similarity_threshold)
        )
    ORDER BY similarity_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql SET search_path = public, extensions;

-- ============================================
-- 4. MOVE VECTOR EXTENSION TO EXTENSIONS SCHEMA
-- Supabase recommends keeping extensions
-- out of public schema.
-- ============================================

CREATE SCHEMA IF NOT EXISTS extensions;
ALTER EXTENSION vector SET SCHEMA extensions;

-- Grant usage so public functions can still use vector types
GRANT USAGE ON SCHEMA extensions TO public;
GRANT USAGE ON SCHEMA extensions TO anon;
GRANT USAGE ON SCHEMA extensions TO authenticated;
GRANT USAGE ON SCHEMA extensions TO service_role;
