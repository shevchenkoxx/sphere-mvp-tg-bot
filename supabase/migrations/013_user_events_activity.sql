-- 013_user_events_activity.sql
-- Add activity intent fields to users table

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS activity_categories TEXT[] DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS activity_details JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS custom_activity_text TEXT;

CREATE INDEX IF NOT EXISTS idx_users_activity_categories ON users USING GIN (activity_categories);
