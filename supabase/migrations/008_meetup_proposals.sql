-- Meetup Proposals: structured meeting coordination between matches
-- Users can propose meetups with time slots + location, AI generates why_meet + topics

CREATE TABLE IF NOT EXISTS meetup_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    short_id VARCHAR(8) NOT NULL UNIQUE,
    match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    proposer_id UUID NOT NULL REFERENCES users(id),
    receiver_id UUID NOT NULL REFERENCES users(id),
    event_id UUID REFERENCES events(id),
    time_slots INTEGER[] NOT NULL,
    location TEXT NOT NULL,
    ai_why_meet TEXT,
    ai_topics TEXT[],
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    accepted_time_slot INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL
);

-- Only one active (pending) proposal per direction per match
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_proposal
    ON meetup_proposals (match_id, proposer_id) WHERE status = 'pending';

-- Fast lookup for receiver's pending proposals
CREATE INDEX IF NOT EXISTS idx_meetup_receiver
    ON meetup_proposals(receiver_id, status);

-- Fast lookup by short_id (used in callback_data)
CREATE INDEX IF NOT EXISTS idx_meetup_short_id
    ON meetup_proposals(short_id);
