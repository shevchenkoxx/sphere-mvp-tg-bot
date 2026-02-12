-- Voice feedback columns for match_feedback table
-- Allows users to leave voice/text feedback after rating a match

ALTER TABLE match_feedback ADD COLUMN IF NOT EXISTS voice_file_id TEXT;
ALTER TABLE match_feedback ADD COLUMN IF NOT EXISTS voice_transcription TEXT;
ALTER TABLE match_feedback ADD COLUMN IF NOT EXISTS feedback_text TEXT;
