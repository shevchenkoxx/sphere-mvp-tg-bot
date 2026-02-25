# Community Mode V1 — Design Document

**Date:** 2026-02-25
**Branch:** `community-v1` (from `global-mode-v1`)
**Bot:** @Matchd_bot
**Status:** Approved — ready for implementation

---

## 1. Vision

One bot, multiple modes: **Community** (TG groups), **Events** (offline), **Global** (social/ads). Community mode is the primary development focus. Bot is added to existing TG groups, passively observes, runs games, and drives members to DM for personalized onboarding and matching.

**Core principle:** Group = discovery & engagement. DM = depth & matching.

---

## 2. System Overview

```
TG Group ("Devs Kyiv")              TG Group ("Founders Warsaw")
  │ Bot observes passively             │ Bot observes passively
  │ Posts games, reminders             │ Posts games, reminders
  │ [Join Sphere →] button             │ [Join Sphere →] button
  │                                    │
  └──── deep link ─────┐    ┌─────── deep link ────┘
                        ▼    ▼
               Bot DM (@Matchd_bot)
               ├── Agent onboarding (personalized)
               ├── Daily questions (profile depth)
               ├── Matching within community (free)
               ├── 1 free cross-community match (teaser)
               ├── Personality card + share
               └── Paywall: $3/match or $10/mo for weekly curated matches
                        │
                        ▼
              Sphere Global Community (TG group)
              ├── Cross-community hub
              ├── Games, vibes, intros
              └── Viral growth loop
```

---

## 3. User Journey & Monetization

### Free Tier (community members)
- Onboarding via DM (agent-driven)
- Unlimited matches within your community
- In-group games participation
- Daily questions & profile enrichment
- Personality card
- 1 free cross-community match (teaser)

### Paywall (later phase — DB-ready from day 1)
- $3 per cross-community match (impulse buy)
- $10/month Sphere Pro:
  - Weekly personalized match by intent (cofounder, relationship, activity partner)
  - Priority matching (profile shown first)
  - Intent-based search ("find me a CTO in Kyiv")
- Future: full access in Sphere App (PWA)

### Tier tracking
- `users.tier` = 'free' | 'pro'
- `users.tier_expires_at` = TIMESTAMPTZ
- Actual payment integration = later phase

---

## 4. Deep Linking & User Attribution

### Format
```
t.me/Matchd_bot?start={type}_{id}[_ref_{tg_id}]

community_abc123              → joined from group
community_abc123_ref_44420    → joined from group via referral
event_CORAD                   → joined from event QR
event_CORAD_community_abc123  → event inside community
ref_44420                     → pure referral
game_mystery_abc123           → clicked from game in group
(no args)                     → organic / direct /start
```

### Membership verification
Even without deep link, bot calls `getChatMember(group_id, user_id)` to check if user is in any connected group. If yes, auto-associate with that community.

### Attribution table (append-only — one user can have multiple sources)
```sql
user_sources (
  id UUID PK,
  user_id UUID FK users,
  source_type TEXT NOT NULL,       -- community/event/referral/game/organic
  source_id TEXT,                  -- community UUID, event code, game session ID
  referrer_tg_id TEXT,
  deep_link_raw TEXT,
  created_at TIMESTAMPTZ
)
```

---

## 5. Database Schema

### New Tables

```sql
-- Communities (TG groups with bot)
communities (
  id UUID PK DEFAULT gen_random_uuid(),
  telegram_group_id BIGINT UNIQUE NOT NULL,
  name TEXT,
  description TEXT,
  invite_link TEXT,
  settings JSONB DEFAULT '{}',
  owner_user_id UUID FK users,
  is_active BOOLEAN DEFAULT true,
  member_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
)

-- Community membership
community_members (
  id UUID PK DEFAULT gen_random_uuid(),
  community_id UUID FK communities ON DELETE CASCADE,
  user_id UUID FK users ON DELETE CASCADE,
  role TEXT DEFAULT 'member',          -- admin/member
  joined_via TEXT,                     -- deep_link/detected/invite
  is_onboarded BOOLEAN DEFAULT false,
  joined_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(community_id, user_id)
)

-- User attribution (append-only)
user_sources (
  id UUID PK DEFAULT gen_random_uuid(),
  user_id UUID FK users ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_id TEXT,
  referrer_tg_id TEXT,
  deep_link_raw TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
)

-- Passive message observations
message_observations (
  id UUID PK DEFAULT gen_random_uuid(),
  community_id UUID FK communities ON DELETE CASCADE,
  user_id UUID FK users ON DELETE CASCADE,
  topics TEXT[],
  sentiment TEXT,                       -- positive/neutral/negative
  snippet TEXT,                         -- first 200 chars only
  message_type TEXT DEFAULT 'text',
  created_at TIMESTAMPTZ DEFAULT now()
)

-- Game sessions
game_sessions (
  id UUID PK DEFAULT gen_random_uuid(),
  community_id UUID FK communities ON DELETE CASCADE,
  game_type TEXT NOT NULL,              -- mystery_profile/this_or_that/vibe_check/
                                        -- hot_take/common_ground/bingo
  status TEXT DEFAULT 'active',         -- active/voting/revealed/ended
  game_data JSONB DEFAULT '{}',
  telegram_message_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT now(),
  ends_at TIMESTAMPTZ
)

-- Game responses
game_responses (
  id UUID PK DEFAULT gen_random_uuid(),
  game_session_id UUID FK game_sessions ON DELETE CASCADE,
  user_id UUID FK users ON DELETE CASCADE,
  response JSONB,
  is_correct BOOLEAN,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(game_session_id, user_id)
)
```

### Modified existing tables

```sql
-- users: add columns
ALTER TABLE users ADD COLUMN community_profile_summary TEXT;
ALTER TABLE users ADD COLUMN last_observed_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN tier TEXT DEFAULT 'free';
ALTER TABLE users ADD COLUMN tier_expires_at TIMESTAMPTZ;

-- matches: add community scope
ALTER TABLE matches ADD COLUMN community_id UUID REFERENCES communities(id);

-- events: link to community
ALTER TABLE events ADD COLUMN community_id UUID REFERENCES communities(id);
```

### Community settings (JSONB in communities.settings)

```json
{
  "reminder_enabled": true,
  "reminder_hours": 48,
  "games_enabled": ["mystery_profile", "this_or_that", "vibe_check"],
  "games_frequency_hours": 24,
  "auto_admin_from_tg": true,
  "cross_community_matching": true,
  "max_free_cross_matches": 1,
  "welcome_message": null
}
```

---

## 6. In-Group Games

| Game | Trigger | Group UX | DM Hook |
|------|---------|----------|---------|
| **Mystery Profile** | Bot has rich profile for member | Puzzle clues + poll with 4-5 names | "Want YOUR mystery card?" button |
| **This or That** | Scheduled (daily/2-day) | Inline buttons, shows compatibility clusters | "Full compatibility →" button |
| **Group Vibe Check** | Scheduled / admin-triggered | Fun question + multiple choice, shows who matched | "Deep vibe analysis →" button |
| **Hot Take Roulette** | Scheduled | Spicy statement + agree/disagree, groups by stance | "Meet someone who thinks different →" button |
| **Common Ground** | Bot detects overlap | "Two members share something surprising..." + reveal | Both get "Connect? →" button |
| **Community Bingo** | Weekly | Bingo card image with traits, members tag matches | "Claim badge →" button |
| **Personality Card** | After DM onboarding | Shareable card image | Card has QR for vibe matching |

Every game button opens `t.me/Matchd_bot?start=game_{type}_{session_id}` — drives DM traffic without bot initiating DMs.

---

## 7. Admin System

### Roles
- **Super-admin** (you): sees all communities, all stats, global config
- **Community admin**: TG group admins auto-detected + manually assigned by super-admin
- **Member**: regular community participant

### Admin detection
On `ChatMemberUpdated` / `my_chat_member`:
- When bot added to group → get group admins via `getChatAdministrators()`
- Map TG admin IDs to existing users (or store for later mapping)
- `community_members.role = 'admin'` for detected admins

### Web dashboard (per community)
Extends existing `web/stats.py` with multi-tenant support:
- Community selector dropdown
- Members tab: onboarded/pending, activity, sources
- Games tab: engagement rates, popular games
- Matching tab: matches created, accepted, cross-community
- Settings tab: reminder frequency, games toggle, welcome message
- Super-admin: global overview across all communities

---

## 8. Bot Group Behavior

### When added to a group
1. Detect via `my_chat_member` (status: member → administrator)
2. Create `communities` record with `telegram_group_id`
3. Fetch group info: name, member count, admin list
4. Send welcome message:
   ```
   Hey everyone! I'm Sphere — I help communities discover
   meaningful connections.

   Here's how I work:
   - I'll post fun games and questions here
   - You can get personalized matching in DM
   - Your admins can configure me

   Tap below to set up your profile and find your people.
   [Join Sphere →]
   ```
5. Auto-assign TG admins as community admins

### Passive observation
- Listen to all group messages (text only, skip media/stickers/short msgs)
- Filter: messages > 10 words only
- Extract: topics, sentiment via gpt-4o-mini (batched every 30 min)
- Store in `message_observations` (snippet, NOT full message — privacy)
- Cap: 20 observations per user per day
- After enough data: generate `community_profile_summary` on user

### Periodic reminders
- Configurable: 24, 48, or 72 hours
- Content varies: game invite, community stats, member spotlight
- Never spammy — one message per reminder window

---

## 9. Branch & Worktree Setup

### Final layout

| Location | Branch | Bot | Purpose |
|----------|--------|-----|---------|
| `sphere-bot/` | `main` | @Spheresocial_bot | Archive — old event-only. GitHub desc: "Legacy" |
| `worktrees/sphere-community/` | `community-v1` | @Matchd_bot | **Active dev** — community + games + matching |
| `worktrees/sphere-global/` | `global-mode-v1` | @Matchd_bot | **Global mode** — social/ads onboarding testing |
| `worktrees/sphere-events/` | `events-v2` | TBD | **Future** — offline event-specific flows |

### Setup steps
1. Update GitHub repo description for main (legacy)
2. Remove v1.1 worktree (cleanup)
3. Switch `sphere-bot/` to main
4. Create `community-v1` branch from `global-mode-v1`
5. Create `worktrees/sphere-community/` on `community-v1`
6. Create `worktrees/sphere-global/` on `global-mode-v1`
7. `events-v2` branch + worktree created later when needed

---

## 10. Cost Estimates

### OpenAI costs per group per month

| Group Size | Msgs/day | LLM (observation) | Embeddings | Games | Total |
|------------|----------|-------------------|------------|-------|-------|
| 50 members | ~200 | ~$0.80 | ~$0.05 | ~$0.15 | ~$1/mo |
| 200 members | ~800 | ~$3.20 | ~$0.20 | ~$0.60 | ~$4/mo |
| 1000 members | ~4000 | ~$16.00 | ~$1.00 | ~$3.00 | ~$20/mo |

### Optimizations
- Skip messages < 10 words
- Batch observations (every 30 min, not real-time)
- Cache embeddings 24h
- Cap observations at 20/user/day
- Only process text messages (skip media, stickers, forwards)

---

## 11. Implementation Phases

### Phase 1 — Foundation (Week 1-2)
- DB migration: communities, community_members, user_sources tables
- Group handler: `ChatMemberUpdated` (bot added/removed)
- Welcome message + deep link generation
- Deep link attribution parser (community_, event_, ref_, game_ prefixes)
- Membership verification via `getChatMember`
- DM onboarding with community context
- Community-scoped matching
- 1 free cross-community match
- Admin auto-detection from TG group
- Basic web dashboard (community selector, members, settings)
- Periodic reminder scheduler (configurable 24-72h)

### Phase 2 — Games (Week 3-4)
- Game engine: sessions, responses, scheduling
- Mystery Profile (passive profile → puzzle → poll → reveal)
- This or That (inline buttons → clusters)
- Group Vibe Check (question → match → analysis)
- Hot Take Roulette (statement → stance → grouping)
- Personality Card (shareable image + QR for vibe matching)
- Common Ground (auto-detect overlap → tease → reveal)
- Daily questions in DM (adapted for community context)

### Phase 3 — Intelligence (Week 5-6)
- Message observation pipeline (passive → extract → store → summarize)
- Community Pulse (weekly AI-generated digest in group)
- Community Bingo (weekly card + tag mechanics)
- Cross-community matching with free tier limit
- Event-within-community support
- Full analytics dashboard per community
- Sphere Global Community (showcase TG group)
- Paywall hooks (DB-ready, UI placeholder, payment = later)

### Future Roadmap
- `events-v2` branch: offline event onboarding (QR, check-in, time-boxed matching)
- Payment integration (Telegram Stars / Stripe)
- Sphere App (PWA) for profile sharing, discovery, creation
- Premium profile card design (shareable, branded)
- App Store / Play Store wrapper

---

## 12. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| DB | Same Supabase, new tables | Shared users + cross-community matching |
| Message storage | Snippets only (200 chars) | Privacy + storage cost |
| Observation processing | Batched every 30 min | Cost optimization |
| Game scheduling | APScheduler / asyncio loop | Already available in stack |
| Admin detection | TG API `getChatAdministrators` | Zero config for admins |
| Monetization tracking | DB columns from day 1 | Ready when payment added |
| Group → DM flow | Deep link buttons (not bot DMs) | TG API limitation |
| Branch strategy | community-v1 from global-mode-v1 | Inherits agent onboarding, matching, all improvements |
