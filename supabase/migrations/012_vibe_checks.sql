-- Migration: Vibe Checks (AI Compatibility Game)

-- ============================================
-- VIBE CHECKS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS vibe_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    short_code TEXT UNIQUE NOT NULL,
    initiator_id UUID REFERENCES users(id),
    target_id UUID REFERENCES users(id),
    initiator_data JSONB DEFAULT '{}',
    target_data JSONB DEFAULT '{}',
    initiator_conversation JSONB DEFAULT '[]',
    target_conversation JSONB DEFAULT '[]',
    initiator_completed BOOLEAN DEFAULT FALSE,
    target_completed BOOLEAN DEFAULT FALSE,
    result JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- ============================================
-- INDEXES
-- ============================================
CREATE INDEX IF NOT EXISTS idx_vibe_checks_short_code ON vibe_checks(short_code);
CREATE INDEX IF NOT EXISTS idx_vibe_checks_initiator ON vibe_checks(initiator_id);
CREATE INDEX IF NOT EXISTS idx_vibe_checks_target ON vibe_checks(target_id);
