-- V1.1 Intent-Based Onboarding Schema
-- New columns for intent onboarding + daily questions

-- === NEW COLUMNS ON users TABLE ===
ALTER TABLE users ADD COLUMN IF NOT EXISTS connection_intents TEXT[] DEFAULT '{}';
ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS looking_for_gender TEXT[];
ALTER TABLE users ADD COLUMN IF NOT EXISTS age_range TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS partner_values TEXT[] DEFAULT '{}';
ALTER TABLE users ADD COLUMN IF NOT EXISTS personality_vibe TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS hookup_preference TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'en';

-- === DAILY QUESTION TRACKING ===
CREATE TABLE IF NOT EXISTS user_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    question_id TEXT NOT NULL,
    asked_at TIMESTAMPTZ DEFAULT now(),
    answer_text TEXT,
    extracted_data JSONB DEFAULT '{}',
    conversation_messages INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_user_questions_user ON user_questions(user_id);
