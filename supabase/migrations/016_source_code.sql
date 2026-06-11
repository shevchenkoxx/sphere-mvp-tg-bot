-- 016: Add source_code for outreach attribution (AFF-63)
-- Captures the source channel from Telegram deep links: t.me/bot?start=src_<code>
-- First-touch wins — never overwritten once set.

ALTER TABLE users ADD COLUMN IF NOT EXISTS source_code TEXT;

CREATE INDEX IF NOT EXISTS idx_users_source_code ON users (source_code) WHERE source_code IS NOT NULL;
