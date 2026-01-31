-- Test Data for Sphere Bot Matching
-- Run this in Supabase SQL Editor
-- Creates 1 event + 10 diverse profiles for testing

-- ============================================
-- STEP 1: CREATE TEST EVENT
-- ============================================

INSERT INTO events (code, name, description, location, is_active, settings)
VALUES (
    'TEST2024',
    'Sphere Test Meetup',
    'Test event for matching algorithm development',
    'Moscow, Online',
    true,
    '{"auto_match": true, "match_threshold": 0.5}'
)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    is_active = true;

-- Get event ID for later use
DO $$
DECLARE
    test_event_id UUID;
BEGIN
    SELECT id INTO test_event_id FROM events WHERE code = 'TEST2024';
    RAISE NOTICE 'Test event ID: %', test_event_id;
END $$;

-- ============================================
-- STEP 2: CREATE 10 TEST USERS
-- ============================================

-- User 1: Tech Founder looking for co-founder
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_001', 'alex_founder', 'Alex', 'Alex Chen',
    ARRAY['tech', 'startups', 'crypto', 'business'],
    ARRAY['cofounders', 'networking', 'investing'],
    'Serial entrepreneur, 2 exits. Building AI startup. Looking for technical co-founder.',
    'Tech entrepreneur with startup experience, seeking technical co-founder for AI venture. Strong business background.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- User 2: ML Engineer looking for startup
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_002', 'maria_ml', 'Maria', 'Maria Ivanova',
    ARRAY['tech', 'science', 'startups', 'education'],
    ARRAY['cofounders', 'learning', 'networking'],
    'ML Engineer at Yandex, 5 years experience. Want to join early-stage startup as technical co-founder.',
    'Experienced ML engineer seeking startup opportunities. Technical expertise in AI/ML, looking for founding role.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- User 3: Product Designer
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_003', 'anna_design', 'Anna', 'Anna Petrova',
    ARRAY['design', 'art', 'tech', 'psychology'],
    ARRAY['creative', 'friends', 'networking'],
    'Senior Product Designer. Love creating beautiful and useful things. Interested in AI-powered design tools.',
    'Creative product designer with interest in AI tools. Looking for creative collaborations and friendships.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- User 4: VC Investor
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_004', 'dmitry_vc', 'Dmitry', 'Dmitry Volkov',
    ARRAY['business', 'finance', 'startups', 'tech'],
    ARRAY['investing', 'networking', 'mentorship'],
    'Partner at Sequoia Capital. Investing in AI/ML startups, Series A-B. Always looking for great founders.',
    'VC investor focused on AI startups. Looking to meet promising founders and provide mentorship.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- User 5: Marketing Expert
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_005', 'kate_marketing', 'Kate', 'Kate Smirnova',
    ARRAY['marketing', 'business', 'psychology', 'travel'],
    ARRAY['networking', 'business', 'friends'],
    'Head of Growth at fintech startup. Expert in viral marketing and community building. Love meeting new people.',
    'Growth marketing expert in fintech. Strong in community building, seeking business connections and friendships.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- User 6: Crypto/Web3 Developer
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_006', 'max_web3', 'Max', 'Max Kuznetsov',
    ARRAY['crypto', 'tech', 'finance', 'gaming'],
    ARRAY['cofounders', 'networking', 'learning'],
    'Solidity developer, building DeFi protocols. Looking for like-minded people to build the future of finance.',
    'Web3 developer specializing in DeFi. Seeking co-founders and collaborators in crypto space.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- User 7: Content Creator / Blogger
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_007', 'lisa_content', 'Lisa', 'Lisa Orlova',
    ARRAY['marketing', 'art', 'travel', 'wellness'],
    ARRAY['creative', 'friends', 'business'],
    'YouTube blogger 500K subs, talking about tech and lifestyle. Looking for collabs and interesting stories.',
    'Popular content creator interested in tech lifestyle. Seeking creative collaborations and interesting people.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- User 8: HR / Recruiter
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_008', 'nina_hr', 'Nina', 'Nina Fedorova',
    ARRAY['psychology', 'business', 'education', 'wellness'],
    ARRAY['hiring', 'networking', 'mentorship'],
    'Tech recruiter, building engineering teams for startups. Can help you find your dream job or dream team.',
    'Tech recruiter helping startups build teams. Can connect talent with opportunities.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- User 9: Data Scientist / Researcher
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_009', 'ivan_data', 'Ivan', 'Ivan Sokolov',
    ARRAY['science', 'tech', 'education', 'books'],
    ARRAY['learning', 'mentorship', 'networking'],
    'PhD in ML, researcher at Skoltech. Publishing papers on NLP. Happy to mentor junior data scientists.',
    'Academic ML researcher with mentoring interest. Expert in NLP, willing to share knowledge.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- User 10: Startup Lawyer
INSERT INTO users (platform, platform_user_id, username, first_name, display_name, interests, goals, bio, ai_summary, onboarding_completed, current_event_id)
VALUES (
    'telegram', 'test_user_010', 'elena_legal', 'Elena', 'Elena Morozova',
    ARRAY['business', 'finance', 'startups', 'books'],
    ARRAY['networking', 'business', 'mentorship'],
    'Corporate lawyer specializing in startups: incorporation, fundraising, M&A. Free first consultation for founders.',
    'Startup-focused corporate lawyer. Expert in fundraising and M&A, offers mentorship to founders.',
    true,
    (SELECT id FROM events WHERE code = 'TEST2024')
)
ON CONFLICT (platform, platform_user_id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    interests = EXCLUDED.interests,
    goals = EXCLUDED.goals,
    bio = EXCLUDED.bio,
    ai_summary = EXCLUDED.ai_summary,
    current_event_id = EXCLUDED.current_event_id;

-- ============================================
-- STEP 3: ADD ALL USERS TO EVENT
-- ============================================

INSERT INTO event_participants (event_id, user_id)
SELECT
    (SELECT id FROM events WHERE code = 'TEST2024'),
    id
FROM users
WHERE platform_user_id LIKE 'test_user_%'
ON CONFLICT (event_id, user_id) DO NOTHING;

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- Check event
SELECT code, name, is_active FROM events WHERE code = 'TEST2024';

-- Check users
SELECT
    platform_user_id,
    display_name,
    interests,
    goals,
    LEFT(bio, 50) as bio_preview
FROM users
WHERE platform_user_id LIKE 'test_user_%'
ORDER BY platform_user_id;

-- Check participants
SELECT
    e.name as event_name,
    u.display_name,
    ep.joined_at
FROM event_participants ep
JOIN events e ON e.id = ep.event_id
JOIN users u ON u.id = ep.user_id
WHERE e.code = 'TEST2024'
ORDER BY ep.joined_at;

-- Summary
SELECT
    (SELECT COUNT(*) FROM events WHERE code = 'TEST2024') as events_count,
    (SELECT COUNT(*) FROM users WHERE platform_user_id LIKE 'test_user_%') as test_users_count,
    (SELECT COUNT(*) FROM event_participants ep JOIN events e ON e.id = ep.event_id WHERE e.code = 'TEST2024') as participants_count;
