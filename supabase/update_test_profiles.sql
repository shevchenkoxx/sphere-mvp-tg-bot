-- Update test profiles with looking_for and can_help_with
-- Run in Supabase SQL Editor

-- Alex Chen - Tech Founder
UPDATE users SET
    looking_for = 'Technical co-founder for AI startup, experienced ML engineers, angel investors',
    can_help_with = 'Startup strategy, fundraising, product-market fit, business development'
WHERE platform_user_id = 'test_001';

-- Maria Ivanova - ML Engineer
UPDATE users SET
    looking_for = 'Early-stage startup as technical co-founder, AI/ML projects, mentorship from experienced founders',
    can_help_with = 'Machine learning, NLP, computer vision, building ML pipelines'
WHERE platform_user_id = 'test_002';

-- Anna Petrova - Product Designer
UPDATE users SET
    looking_for = 'Creative collaborations, AI-powered design tools projects, design-minded founders',
    can_help_with = 'Product design, UX research, design systems, brand identity'
WHERE platform_user_id = 'test_003';

-- Dmitry Volkov - VC Investor
UPDATE users SET
    looking_for = 'Promising AI/ML startups for Series A-B investment, exceptional founders',
    can_help_with = 'Fundraising advice, investor introductions, scaling strategy, board experience'
WHERE platform_user_id = 'test_004';

-- Kate Smirnova - Marketing Expert
UPDATE users SET
    looking_for = 'Interesting startups to advise, growth challenges, marketing co-founders',
    can_help_with = 'Growth marketing, viral campaigns, community building, go-to-market strategy'
WHERE platform_user_id = 'test_005';

-- Max Kuznetsov - Web3 Developer
UPDATE users SET
    looking_for = 'DeFi co-founders, crypto-native teams, blockchain projects',
    can_help_with = 'Solidity development, smart contracts, DeFi protocols, Web3 architecture'
WHERE platform_user_id = 'test_006';

-- Lisa Orlova - Content Creator
UPDATE users SET
    looking_for = 'Interesting stories and people for content, brand collaborations, tech products to review',
    can_help_with = 'Content creation, audience building, brand awareness, tech product promotion'
WHERE platform_user_id = 'test_007';

-- Nina Fedorova - HR Recruiter
UPDATE users SET
    looking_for = 'Startups building teams, talented engineers looking for opportunities',
    can_help_with = 'Hiring strategy, talent acquisition, team building, HR processes for startups'
WHERE platform_user_id = 'test_008';

-- Ivan Sokolov - Data Scientist
UPDATE users SET
    looking_for = 'Interesting research collaborations, junior data scientists to mentor, applied ML projects',
    can_help_with = 'NLP research, ML architecture, academic guidance, paper reviews'
WHERE platform_user_id = 'test_009';

-- Elena Morozova - Startup Lawyer
UPDATE users SET
    looking_for = 'Founders needing legal help, interesting startups to advise',
    can_help_with = 'Startup incorporation, fundraising docs, SAFE/convertible notes, M&A, IP protection'
WHERE platform_user_id = 'test_010';

-- Verify updates
SELECT display_name, looking_for, can_help_with FROM users WHERE platform_user_id LIKE 'test_%' ORDER BY platform_user_id;
