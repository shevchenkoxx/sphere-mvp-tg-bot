-- Migration: Add personalization fields for post-onboarding flow
-- These fields capture user's current focus and connection preferences

-- Add personalization columns to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS passion_text TEXT,
ADD COLUMN IF NOT EXISTS passion_themes TEXT[],
ADD COLUMN IF NOT EXISTS connection_mode VARCHAR(50),
ADD COLUMN IF NOT EXISTS personalization_preference TEXT,
ADD COLUMN IF NOT EXISTS ideal_connection TEXT;

-- Add comments for documentation
COMMENT ON COLUMN users.passion_text IS 'What the user is passionate about right now (free-form text)';
COMMENT ON COLUMN users.passion_themes IS 'Extracted themes from passion_text (array of strings)';
COMMENT ON COLUMN users.connection_mode IS 'Connection preference: receive_help, give_help, or exchange';
COMMENT ON COLUMN users.personalization_preference IS 'Selected option from LLM-generated adaptive buttons';
COMMENT ON COLUMN users.ideal_connection IS 'Free-form description of ideal person to meet';

-- Create index for connection_mode to enable complementary matching queries
CREATE INDEX IF NOT EXISTS idx_users_connection_mode ON users(connection_mode) WHERE connection_mode IS NOT NULL;
