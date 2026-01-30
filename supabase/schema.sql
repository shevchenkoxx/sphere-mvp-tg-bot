-- Sphere Bot Database Schema
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- USERS TABLE
-- Platform-agnostic user storage
-- ============================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Platform identification (supports multiple platforms)
    platform VARCHAR(20) NOT NULL DEFAULT 'telegram',  -- telegram, whatsapp, web
    platform_user_id VARCHAR(255) NOT NULL,  -- telegram_id, whatsapp_id, etc.

    -- Basic info
    username VARCHAR(255),
    first_name VARCHAR(255),
    display_name VARCHAR(255),

    -- Location
    city_born VARCHAR(255),
    city_current VARCHAR(255),

    -- Profile data
    interests TEXT[] DEFAULT '{}',
    goals TEXT[] DEFAULT '{}',
    bio TEXT,

    -- Media
    photo_url TEXT,
    voice_intro_url TEXT,
    social_links JSONB DEFAULT '{}',

    -- AI-generated
    ai_summary TEXT,

    -- Status
    onboarding_completed BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint for platform + platform_user_id
    UNIQUE(platform, platform_user_id)
);

-- ============================================
-- EVENTS TABLE
-- ============================================
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Event identification
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    location VARCHAR(255),
    event_date TIMESTAMPTZ,

    -- Organizer
    organizer_id UUID REFERENCES users(id),

    -- Media
    image_url TEXT,

    -- Settings
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{"auto_match": true, "match_threshold": 0.6}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- EVENT PARTICIPANTS
-- Many-to-many relationship
-- ============================================
CREATE TABLE event_participants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(event_id, user_id)
);

-- ============================================
-- MATCHES TABLE
-- AI-powered matching results
-- ============================================
CREATE TABLE matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Related event (optional - for global matches in future)
    event_id UUID REFERENCES events(id),

    -- Users
    user_a_id UUID REFERENCES users(id) NOT NULL,
    user_b_id UUID REFERENCES users(id) NOT NULL,

    -- Match data
    compatibility_score FLOAT NOT NULL,
    match_type VARCHAR(50) NOT NULL,  -- friendship, professional, romantic, creative
    ai_explanation TEXT NOT NULL,
    icebreaker TEXT NOT NULL,

    -- Status
    status VARCHAR(20) DEFAULT 'pending',  -- pending, accepted, declined, expired

    -- Notification tracking
    user_a_notified BOOLEAN DEFAULT FALSE,
    user_b_notified BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate matches
    UNIQUE(event_id, user_a_id, user_b_id)
);

-- ============================================
-- MESSAGES TABLE
-- Chat between matched users
-- ============================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    match_id UUID REFERENCES matches(id) ON DELETE CASCADE,
    sender_id UUID REFERENCES users(id),
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================
CREATE INDEX idx_users_platform ON users(platform, platform_user_id);
CREATE INDEX idx_events_code ON events(code);
CREATE INDEX idx_events_active ON events(is_active);
CREATE INDEX idx_event_participants_event ON event_participants(event_id);
CREATE INDEX idx_event_participants_user ON event_participants(user_id);
CREATE INDEX idx_matches_users ON matches(user_a_id, user_b_id);
CREATE INDEX idx_matches_event ON matches(event_id);
CREATE INDEX idx_matches_status ON matches(status);
CREATE INDEX idx_messages_match ON messages(match_id);

-- ============================================
-- TRIGGERS
-- ============================================

-- Update updated_at on users table
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================
-- ROW LEVEL SECURITY (optional, for future API)
-- ============================================

-- Enable RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- For now, allow service role full access
-- (We're using service key in the bot)
CREATE POLICY "Service role has full access to users"
    ON users FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to events"
    ON events FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to event_participants"
    ON event_participants FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to matches"
    ON matches FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to messages"
    ON messages FOR ALL
    USING (true)
    WITH CHECK (true);
