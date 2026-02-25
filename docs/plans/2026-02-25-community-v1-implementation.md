# Community Mode V1 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Telegram community bot that joins groups, passively observes, runs games, and drives members to DM for personalized onboarding and matching.

**Architecture:** Layered on top of existing global-mode-v1 codebase. New group handler module, community models + repositories, deep link attribution system, game engine, and multi-tenant admin dashboard. Same Supabase DB with new tables.

**Tech Stack:** Python 3.10+, aiogram 3.x, Supabase (PostgreSQL + pgvector), OpenAI (gpt-4o-mini + text-embedding-3-small), qrcode, Pillow, APScheduler

---

## Phase 1 — Foundation (Week 1-2)

### Task 1: DB Migration — Community Tables

**Files:**
- Create: `supabase/migrations/016_community_tables.sql`

**Step 1: Write the migration**

```sql
-- Communities (TG groups with bot)
CREATE TABLE IF NOT EXISTS communities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_group_id BIGINT UNIQUE NOT NULL,
    name TEXT,
    description TEXT,
    invite_link TEXT,
    settings JSONB DEFAULT '{
        "reminder_enabled": true,
        "reminder_hours": 48,
        "games_enabled": ["mystery_profile", "this_or_that", "vibe_check"],
        "games_frequency_hours": 24,
        "auto_admin_from_tg": true,
        "cross_community_matching": true,
        "max_free_cross_matches": 1,
        "welcome_message": null
    }',
    owner_user_id UUID REFERENCES users(id),
    is_active BOOLEAN DEFAULT true,
    member_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Community membership
CREATE TABLE IF NOT EXISTS community_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member',
    joined_via TEXT,
    is_onboarded BOOLEAN DEFAULT false,
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(community_id, user_id)
);

-- User attribution (append-only)
CREATE TABLE IF NOT EXISTS user_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id TEXT,
    referrer_tg_id TEXT,
    deep_link_raw TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Passive message observations
CREATE TABLE IF NOT EXISTS message_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    topics TEXT[],
    sentiment TEXT,
    snippet TEXT,
    message_type TEXT DEFAULT 'text',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Game sessions
CREATE TABLE IF NOT EXISTS game_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID REFERENCES communities(id) ON DELETE CASCADE,
    game_type TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    game_data JSONB DEFAULT '{}',
    telegram_message_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT now(),
    ends_at TIMESTAMPTZ
);

-- Game responses
CREATE TABLE IF NOT EXISTS game_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_session_id UUID REFERENCES game_sessions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    response JSONB,
    is_correct BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(game_session_id, user_id)
);

-- Extend users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS community_profile_summary TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_observed_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'free';
ALTER TABLE users ADD COLUMN IF NOT EXISTS tier_expires_at TIMESTAMPTZ;

-- Extend matches table
ALTER TABLE matches ADD COLUMN IF NOT EXISTS community_id UUID REFERENCES communities(id);

-- Extend events table
ALTER TABLE events ADD COLUMN IF NOT EXISTS community_id UUID REFERENCES communities(id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_community_members_community ON community_members(community_id);
CREATE INDEX IF NOT EXISTS idx_community_members_user ON community_members(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sources_user ON user_sources(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sources_type ON user_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_message_observations_community ON message_observations(community_id);
CREATE INDEX IF NOT EXISTS idx_message_observations_user ON message_observations(user_id);
CREATE INDEX IF NOT EXISTS idx_game_sessions_community ON game_sessions(community_id);
CREATE INDEX IF NOT EXISTS idx_game_responses_session ON game_responses(game_session_id);

-- RLS
ALTER TABLE communities ENABLE ROW LEVEL SECURITY;
ALTER TABLE community_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_responses ENABLE ROW LEVEL SECURITY;
```

**Step 2: Run migration**

```bash
/opt/homebrew/Cellar/libpq/18.1/bin/psql "$DB_CONNECTION_STRING" -f supabase/migrations/016_community_tables.sql
```

**Step 3: Commit**

```bash
git add supabase/migrations/016_community_tables.sql
git commit -m "feat: add community tables — communities, members, sources, observations, games"
```

---

### Task 2: Domain Models — Community, CommunityMember, UserSource

**Files:**
- Modify: `core/domain/models.py` — add Community, CommunityMember, UserSource, GameSession, GameResponse models
- Modify: `core/domain/constants.py` — add GAME_TYPES, SOURCE_TYPES, COMMUNITY_ROLES

**Step 1: Add models to models.py**

Add after existing models:
```python
class Community(BaseModel):
    id: UUID
    telegram_group_id: int
    name: Optional[str] = None
    description: Optional[str] = None
    invite_link: Optional[str] = None
    settings: dict = {}
    owner_user_id: Optional[UUID] = None
    is_active: bool = True
    member_count: int = 0
    created_at: Optional[datetime] = None

class CommunityMember(BaseModel):
    id: UUID
    community_id: UUID
    user_id: UUID
    role: str = "member"
    joined_via: Optional[str] = None
    is_onboarded: bool = False
    joined_at: Optional[datetime] = None

class UserSource(BaseModel):
    id: UUID
    user_id: UUID
    source_type: str
    source_id: Optional[str] = None
    referrer_tg_id: Optional[str] = None
    deep_link_raw: Optional[str] = None
    created_at: Optional[datetime] = None

class GameSession(BaseModel):
    id: UUID
    community_id: UUID
    game_type: str
    status: str = "active"
    game_data: dict = {}
    telegram_message_id: Optional[int] = None
    created_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

class GameResponse(BaseModel):
    id: UUID
    game_session_id: UUID
    user_id: UUID
    response: Optional[dict] = None
    is_correct: Optional[bool] = None
    created_at: Optional[datetime] = None
```

**Step 2: Add constants**

```python
GAME_TYPES = ["mystery_profile", "this_or_that", "vibe_check", "hot_take", "common_ground", "bingo"]
SOURCE_TYPES = ["community", "event", "referral", "game", "organic"]
COMMUNITY_ROLES = ["admin", "member"]
```

**Step 3: Compile and commit**

```bash
python3 -m py_compile core/domain/models.py
python3 -m py_compile core/domain/constants.py
git add core/domain/models.py core/domain/constants.py
git commit -m "feat: add Community, UserSource, GameSession domain models"
```

---

### Task 3: Repositories — CommunityRepo, UserSourceRepo

**Files:**
- Create: `infrastructure/database/community_repository.py`
- Create: `infrastructure/database/user_source_repository.py`

**Step 1: Write CommunityRepository**

Methods needed:
- `create(telegram_group_id, name, owner_user_id)` → Community
- `get_by_telegram_group_id(group_id)` → Optional[Community]
- `get_by_id(id)` → Optional[Community]
- `update_settings(community_id, settings)` → Community
- `add_member(community_id, user_id, role, joined_via)` → CommunityMember
- `get_member(community_id, user_id)` → Optional[CommunityMember]
- `get_members(community_id)` → List[CommunityMember]
- `get_admins(community_id)` → List[CommunityMember]
- `set_member_onboarded(community_id, user_id)` → None
- `get_user_communities(user_id)` → List[Community]
- `update_member_count(community_id)` → None
- `deactivate(community_id)` → None

Follow existing pattern from `event_repository.py`: `@run_sync` for Supabase calls, `_to_model()` converter.

**Step 2: Write UserSourceRepository**

Methods needed:
- `create(user_id, source_type, source_id, referrer_tg_id, deep_link_raw)` → UserSource
- `get_user_sources(user_id)` → List[UserSource]
- `get_by_source(source_type, source_id)` → List[UserSource]

**Step 3: Compile and commit**

```bash
python3 -m py_compile infrastructure/database/community_repository.py
python3 -m py_compile infrastructure/database/user_source_repository.py
git add infrastructure/database/community_repository.py infrastructure/database/user_source_repository.py
git commit -m "feat: add CommunityRepository and UserSourceRepository"
```

---

### Task 4: Community Service — Business Logic

**Files:**
- Create: `core/services/community_service.py`

**Step 1: Write CommunityService**

Methods needed:
- `on_bot_added_to_group(chat_id, chat_title, adder_user_id)` → Community
- `on_bot_removed_from_group(chat_id)` → None
- `sync_group_admins(community, admin_tg_ids)` → None
- `verify_membership(user_tg_id, community)` → bool (calls bot.get_chat_member)
- `auto_associate_user(user_id, user_tg_id)` → List[Community] (check all communities)
- `get_community_for_group(chat_id)` → Optional[Community]
- `generate_deep_link(community_id, bot_username)` → str

**Step 2: Compile and commit**

```bash
python3 -m py_compile core/services/community_service.py
git add core/services/community_service.py
git commit -m "feat: add CommunityService — group lifecycle, admin sync, membership"
```

---

### Task 5: Group Handler — Bot Added/Removed + Passive Observation

**Files:**
- Create: `adapters/telegram/handlers/community_group.py`
- Modify: `adapters/telegram/handlers/__init__.py` — register community_group router

**Step 1: Write group handler**

Handlers needed:
- `on_bot_added(event: ChatMemberUpdated)` — detect `my_chat_member` status change to member/administrator. Create community, fetch admins via `getChatAdministrators`, send welcome message with deep link button.
- `on_bot_removed(event: ChatMemberUpdated)` — deactivate community.
- `on_group_message(message: Message)` — passive observation. Filter: text only, >10 words, not from bot. Extract topics via batch queue (don't process inline — queue for batch).

**Step 2: Register router**

In `__init__.py`, add community_group router BEFORE start router:
```python
from adapters.telegram.handlers import community_group
# In routers list, before start.router:
routers.append(community_group.router)
```

**Step 3: Compile and commit**

```bash
python3 -m py_compile adapters/telegram/handlers/community_group.py
python3 -m py_compile adapters/telegram/handlers/__init__.py
git add adapters/telegram/handlers/community_group.py adapters/telegram/handlers/__init__.py
git commit -m "feat: add group handler — bot join/leave, passive message observation"
```

---

### Task 6: Deep Link Attribution Parser

**Files:**
- Modify: `adapters/telegram/handlers/start.py` — refactor `start_with_deep_link` to parse all link types and log to `user_sources`

**Step 1: Refactor deep link parsing**

Replace the current ad-hoc parsing with a structured parser:
```python
def parse_deep_link(args: str) -> dict:
    """Parse deep link args into structured attribution data.
    Returns: {type, id, referrer, community_id, event_code, game_session_id, raw}
    """
```

Handle all formats:
- `community_{id}` → source_type=community
- `community_{id}_ref_{tg_id}` → source_type=community + referral
- `event_{code}` → source_type=event
- `event_{code}_community_{id}` → event within community
- `game_{type}_{session_id}` → source_type=game
- `ref_{tg_id}` → source_type=referral
- `vibe_{code}` → existing vibe check (keep as-is)

After parsing, call `user_source_repo.create(...)` to log attribution.

Also call `community_service.verify_membership()` for users without deep link to auto-detect community membership.

**Step 2: Compile and commit**

```bash
python3 -m py_compile adapters/telegram/handlers/start.py
git add adapters/telegram/handlers/start.py
git commit -m "feat: structured deep link parser + user attribution logging"
```

---

### Task 7: Community-Scoped Matching

**Files:**
- Modify: `core/services/matching_service.py` — add `find_community_matches(user, community_id, limit)`
- Modify: `infrastructure/database/match_repository.py` — add `get_community_matches()`

**Step 1: Add community matching**

Similar to existing `find_global_matches()` but filtered to community members:
1. Get community member user IDs
2. Filter to those with embeddings
3. Vector similarity search within that set
4. LLM re-ranking
5. Save matches with `community_id` set

**Step 2: Add 1 free cross-community match**

After community matches, if user has < 1 cross-community match:
1. Run global matching excluding current community members
2. Return top 1 result
3. Track in user_sources or a counter

**Step 3: Compile and commit**

```bash
python3 -m py_compile core/services/matching_service.py
python3 -m py_compile infrastructure/database/match_repository.py
git add core/services/matching_service.py infrastructure/database/match_repository.py
git commit -m "feat: community-scoped matching + 1 free cross-community match"
```

---

### Task 8: DM Onboarding with Community Context

**Files:**
- Modify: `adapters/telegram/handlers/onboarding_agent.py` — pass community context to agent
- Modify: `core/services/orchestrator_prompts.py` — community-aware prompt additions

**Step 1: Pass community context**

When user arrives via `community_{id}` deep link:
- Store `community_id` in FSM state data alongside `event_code`
- Pass community name to agent prompt: "This person is from the [Community Name] group"
- After onboarding completes: set `community_members.is_onboarded = true`
- Run community-scoped matching instead of global

**Step 2: Update agent prompt**

Add community context to system prompt:
```
The user joined from the community "[name]".
Mention their community naturally. After onboarding,
they'll get matched with other community members.
```

**Step 3: Compile and commit**

```bash
python3 -m py_compile adapters/telegram/handlers/onboarding_agent.py
python3 -m py_compile core/services/orchestrator_prompts.py
git add adapters/telegram/handlers/onboarding_agent.py core/services/orchestrator_prompts.py
git commit -m "feat: community-aware onboarding — context in agent prompt + scoped matching"
```

---

### Task 9: Periodic Reminder Scheduler

**Files:**
- Create: `core/services/scheduler_service.py`
- Modify: `main.py` — start scheduler on boot

**Step 1: Write scheduler**

Use `asyncio` loop (simpler than APScheduler for our needs):
- Every hour: check all communities where `now - last_reminder > reminder_hours`
- Send reminder message to group (vary content: game invite, community stats, member spotlight)
- Update `communities.settings.last_reminder_at`

**Step 2: Hook into main.py**

Start scheduler task alongside polling:
```python
asyncio.create_task(scheduler_service.run())
```

**Step 3: Compile and commit**

```bash
python3 -m py_compile core/services/scheduler_service.py
python3 -m py_compile main.py
git add core/services/scheduler_service.py main.py
git commit -m "feat: periodic reminder scheduler — configurable 24-72h per community"
```

---

### Task 10: Basic Admin Dashboard — Multi-Tenant

**Files:**
- Modify: `adapters/telegram/web/stats.py` — add community selector + per-community views

**Step 1: Add community views**

New routes:
- `/stats/communities` — list all communities (super-admin)
- `/stats/community/{id}` — dashboard for specific community
- `/stats/community/{id}/members` — member list with onboarding status
- `/stats/community/{id}/settings` — configurable settings form

Add community selector dropdown to existing dashboard header.

**Step 2: Compile and commit**

```bash
python3 -m py_compile adapters/telegram/web/stats.py
git add adapters/telegram/web/stats.py
git commit -m "feat: multi-tenant admin dashboard — community selector + settings"
```

---

### Task 11: Loader + Init — Wire Everything Together

**Files:**
- Modify: `adapters/telegram/loader.py` — init community_repo, community_service, user_source_repo, scheduler
- Modify: `adapters/telegram/handlers/__init__.py` — ensure community_group router is in right position

**Step 1: Init new services in loader.py**

```python
community_repo = CommunityRepository()
user_source_repo = UserSourceRepository()
community_service = CommunityService(community_repo, user_repo, bot)
```

**Step 2: Compile and commit**

```bash
python3 -m py_compile adapters/telegram/loader.py
git add adapters/telegram/loader.py
git commit -m "feat: wire community services into loader — Phase 1 complete"
```

---

## Phase 2 — Games (Week 3-4)

### Task 12: Game Engine — Base Framework

**Files:**
- Create: `core/services/game_service.py`
- Create: `infrastructure/database/game_repository.py`
- Create: `adapters/telegram/handlers/community_games.py`

Game service methods:
- `create_game(community_id, game_type, game_data)` → GameSession
- `submit_response(game_session_id, user_id, response)` → GameResponse
- `end_game(game_session_id)` → results
- `get_active_games(community_id)` → List[GameSession]
- `schedule_next_game(community_id)` → None

Handler: register callback handlers for game buttons (`game_vote_{session}_{option}`, etc.)

**Commit:** `git commit -m "feat: game engine — base framework with session management"`

---

### Task 13: Mystery Profile Game

**Files:**
- Add to: `core/services/game_service.py` — `create_mystery_profile(community_id)`
- Add to: `adapters/telegram/handlers/community_games.py` — handlers

Flow:
1. Pick a member with rich profile
2. Generate puzzle clues via gpt-4o-mini (ambiguous, fun)
3. Post in group with poll (4-5 candidate names)
4. After timeout or enough votes: reveal + "Want YOUR mystery card?" button
5. Button opens `t.me/bot?start=game_mystery_{session_id}`

**Commit:** `git commit -m "feat: Mystery Profile game — puzzle clues + voting + reveal"`

---

### Task 14: This or That Game

Flow:
1. Pick a fun binary question from question bank
2. Post with 2 inline buttons
3. Collect votes, show running count
4. After timeout: show compatibility clusters
5. "See full compatibility →" button

**Commit:** `git commit -m "feat: This or That game — binary choices + compatibility clusters"`

---

### Task 15: Group Vibe Check Game

Flow:
1. Post a fun multiple-choice question
2. Members pick answers via inline buttons
3. Show who matched each answer
4. "Deep vibe analysis →" button

**Commit:** `git commit -m "feat: Group Vibe Check — fun questions + answer matching"`

---

### Task 16: Hot Take Roulette

Flow:
1. Post a spicy statement
2. Agree/Disagree inline buttons
3. Group people by stance
4. "Meet someone who thinks different →" button

**Commit:** `git commit -m "feat: Hot Take Roulette — polarizing statements + stance grouping"`

---

### Task 17: Personality Card Generator

**Files:**
- Create: `core/utils/personality_card.py`

Generate shareable image:
1. After DM onboarding, generate personality summary via LLM
2. Create branded card image (Pillow) with:
   - User's "type" (AI-generated, like MBTI but custom)
   - Key traits, interests, vibe
   - QR code linking to vibe matching
3. Send in DM, user can forward/share in group

**Commit:** `git commit -m "feat: Personality Card — shareable image with QR for vibe matching"`

---

### Task 18: Common Ground Detection

Flow:
1. Periodically scan community members' profiles for overlaps
2. When 2 members share surprising commonality: post teaser in group
3. Reveal button shows the connection
4. Both users get "Connect? →" button

**Commit:** `git commit -m "feat: Common Ground — auto-detect member overlaps + tease in group"`

---

## Phase 3 — Intelligence (Week 5-6)

### Task 19: Message Observation Pipeline

**Files:**
- Create: `core/services/observation_service.py`

Batch processing:
1. Queue messages from group handler (in-memory list)
2. Every 30 min: batch process via gpt-4o-mini
3. Extract: topics, sentiment per message
4. Store in `message_observations`
5. After enough observations per user: generate `community_profile_summary`

Optimizations:
- Skip messages < 10 words
- Cap 20 observations/user/day
- Only text messages (skip media, stickers, forwards)

**Commit:** `git commit -m "feat: message observation pipeline — batched topic extraction"`

---

### Task 20: Community Pulse (Weekly Digest)

Generate and post weekly summary:
- Top topics discussed
- Most active members
- "N members share your interest in X"
- Trending conversations
- "Join Sphere to find your people →" CTA

**Commit:** `git commit -m "feat: Community Pulse — AI-generated weekly digest"`

---

### Task 21: Community Bingo

Weekly bingo card:
1. Generate card image with traits ("works in AI", "lived abroad", "plays guitar")
2. Post in group
3. Members tag each other to fill squares
4. Complete a row → "Claim badge →" button in DM

**Commit:** `git commit -m "feat: Community Bingo — weekly trait matching game"`

---

### Task 22: Cross-Community Matching with Tier Limits

Enforce free tier limits:
1. After 1 free cross-community match, show paywall teaser
2. "You have 3 more matches outside your community (locked)"
3. DB: track `cross_community_match_count` per user
4. Paywall UI placeholder (actual payment = later)

**Commit:** `git commit -m "feat: cross-community matching with free tier limit + paywall placeholder"`

---

### Task 23: Event-Within-Community

Allow admins to create events linked to a community:
1. `/quickevent` in group chat (or via admin dashboard)
2. Event gets `community_id` set
3. Event deep link includes community context
4. Event matches show in both event AND community match views

**Commit:** `git commit -m "feat: event-within-community — linked events with shared context"`

---

### Task 24: Sphere Global Community

Setup:
1. Create TG group "Sphere Community"
2. Add bot as admin
3. Auto-register as first community
4. After DM onboarding, offer: "Join the Sphere community to meet people beyond your group"
5. Send invite link
6. This group runs all the same games

**Commit:** `git commit -m "feat: Sphere Global Community — cross-community hub"`

---

### Task 25: Full Analytics Dashboard

Per-community dashboard pages:
- Member growth chart (daily signups)
- Onboarding funnel (group → deep link → DM → onboarded → matched)
- Game engagement (participation rate, most popular games)
- Matching stats (within community, cross-community)
- Message activity heatmap
- Source attribution breakdown (deep link vs detected vs referral)

**Commit:** `git commit -m "feat: full analytics dashboard — per-community charts + attribution"`

---

### Task 26: Update CLAUDE.md + .memory/ for Community Branch

**Files:**
- Modify: `CLAUDE.md` — update for community-v1 branch context
- Modify: `.memory/status.md` — current state
- Modify: `.memory/decisions.md` — append community decisions

**Commit:** `git commit -m "docs: update CLAUDE.md and .memory for community-v1 branch"`

---

## Future Roadmap (not in this plan)

- **events-v2 branch:** Offline event onboarding (QR, check-in, time-boxed matching)
- **Payment integration:** Telegram Stars / Stripe for $3/match and $10/mo Pro
- **Sphere App (PWA):** Profile sharing, discovery, creation
- **Premium Profile Card:** Designer-grade shareable cards
- **App Store wrapper:** iOS/Android distribution

---

## Branch & Worktree Reference

| Location | Branch | Purpose |
|----------|--------|---------|
| `sphere-bot/` | `main` | Archive — old event-only |
| `worktrees/sphere-community/` | `community-v1` | Active dev — THIS PLAN |
| `worktrees/sphere-global/` | `global-mode-v1` | Global mode — social/ads onboarding |
| `worktrees/sphere-events/` | `events-v2` | Future — offline events |

## Git Commit Convention

Every commit message follows this format and serves as long-term memory:

```
<type>: <description>

[optional body with context, rationale, what was tried]

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`

Commits should be self-documenting — anyone reading `git log` should understand what was built and why.
