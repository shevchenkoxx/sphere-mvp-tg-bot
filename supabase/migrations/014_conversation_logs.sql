-- 014_conversation_logs.sql
-- Full conversation logging for admin dashboard

CREATE TABLE IF NOT EXISTS conversation_logs (
    id BIGSERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    message_type TEXT NOT NULL DEFAULT 'text',
    content TEXT,
    callback_data TEXT,
    api_method TEXT,
    telegram_message_id BIGINT,
    has_media BOOLEAN DEFAULT FALSE,
    fsm_state TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conv_logs_user_time ON conversation_logs(telegram_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_logs_created ON conversation_logs(created_at DESC);

ALTER TABLE conversation_logs ENABLE ROW LEVEL SECURITY;
