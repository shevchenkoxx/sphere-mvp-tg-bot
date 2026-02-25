-- 016_community_tables.sql
-- Community mode: groups, members, attribution, observations, games

-- Communities (TG groups with bot)
CREATE TABLE IF NOT EXISTS communities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_group_id BIGINT UNIQUE NOT NULL,
    name TEXT,
    description TEXT,
    invite_link TEXT,
    settings JSONB DEFAULT '{
        "reminder_enabled": true,
        "reminder_hours": 48,
        "games_enabled": ["mystery_profile", "this_or_that", "vibe_check"],
        "games_frequency_hours": 24,
        "auto_admin_from_tg": true,
        "cross_community_matching": true,
        "max_free_cross_matches": 1,
        "welcome_message": null
    }',
    owner_user_id UUID REFERENCES users(id),
    is_active BOOLEAN DEFAULT true,
    member_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Community membership
CREATE TABLE IF NOT EXISTS community_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member',
    joined_via TEXT,
    is_onboarded BOOLEAN DEFAULT false,
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(community_id, user_id)
);

-- User attribution (append-only)
CREATE TABLE IF NOT EXISTS user_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id TEXT,
    referrer_tg_id TEXT,
    deep_link_raw TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Passive message observations
CREATE TABLE IF NOT EXISTS message_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    topics TEXT[],
    sentiment TEXT,
    snippet TEXT,
    message_type TEXT DEFAULT 'text',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Game sessions
CREATE TABLE IF NOT EXISTS game_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
    game_type TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    game_data JSONB DEFAULT '{}',
    telegram_message_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT now(),
    ends_at TIMESTAMPTZ
);

-- Game responses
CREATE TABLE IF NOT EXISTS game_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_session_id UUID REFERENCES game_sessions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    response JSONB,
    is_correct BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(game_session_id, user_id)
);

-- Extend users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS community_profile_summary TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_observed_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'free';
ALTER TABLE users ADD COLUMN IF NOT EXISTS tier_expires_at TIMESTAMPTZ;

-- Extend matches table
ALTER TABLE matches ADD COLUMN IF NOT EXISTS community_id UUID REFERENCES communities(id);

-- Extend events table
ALTER TABLE events ADD COLUMN IF NOT EXISTS community_id UUID REFERENCES communities(id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_community_members_community ON community_members(community_id);
CREATE INDEX IF NOT EXISTS idx_community_members_user ON community_members(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sources_user ON user_sources(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sources_type ON user_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_message_observations_community ON message_observations(community_id);
CREATE INDEX IF NOT EXISTS idx_message_observations_user ON message_observations(user_id);
CREATE INDEX IF NOT EXISTS idx_game_sessions_community ON game_sessions(community_id);
CREATE INDEX IF NOT EXISTS idx_game_responses_session ON game_responses(game_session_id);

-- RLS
ALTER TABLE communities ENABLE ROW LEVEL SECURITY;
ALTER TABLE community_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_responses ENABLE ROW LEVEL SECURITY;
