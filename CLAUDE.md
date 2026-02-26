# Sphere Bot — Community Mode

## Branch: `community-v1` (@Matchd_bot)
- **Branch:** `community-v1`
- **Bot:** @Matchd_bot (not production!)
- **Railway:** Project `loving-possibility` → Environment `Community` → Service `Service (Community)`
- **Dashboard:** `https://humorous-enchantment-staging.up.railway.app/stats?token=sphere-admin-2026`
- **DO NOT** push to main from here!

## Overview
Telegram bot for meaningful connections within communities. Bot is added to TG groups, observes messages, runs games, and matches members via DM. Global Mode + Community Mode combined.

**Repo:** https://github.com/shevchenkoxx/sphere-mvp-tg-bot
**Production (main):** @Spheresocial_bot — DO NOT TOUCH from here

---

## IMPORTANT for Claude Code

### Git Memory (MANDATORY)
**Read `.memory/status.md` at session start. Update at session end.**

- `.memory/FORMAT.md` — format rules
- `.memory/status.md` — current state (overwrite each session)
- `.memory/decisions.md` — append-only decision log
- `.memory/sessions/YYYY-MM-DD.md` — session changelogs

### Branch Safety
- This is `worktrees/sphere-community/` on branch **community-v1**
- Production is on branch **main**
- Push with `git push origin community-v1` (NOT main!)

### Credentials
- **All credentials stored in:** `.credentials/keys.md` (gitignored)
- Supabase URL, Service Key, DB Password
- OpenAI API Key
- Telegram Bot Token (different from production!)

### Deploy
- **ALWAYS push to git** for Railway deployment
- Railway auto-deploys from configured branch
- After `git push` wait ~1-2 min for deploy

### Database (Supabase)
- URL: `https://cfppunyxxelqutfwqfbi.supabase.co`
- **psql path:** `/opt/homebrew/Cellar/libpq/18.1/bin/psql`
- Migrations in `supabase/migrations/`
- **Claude CAN run migrations directly** via psql

---

## Current Status (February 2026)

### Community Mode — All 3 Phases Complete

**Phase 1: Foundation** (Tasks 1-11) — DB migration, domain models, repositories, community service, group handler, deep link parser, community-scoped matching, community-aware onboarding, scheduler, admin dashboard, loader wiring.

**Phase 2: Games** (Tasks 12-18) — Game engine with 5 game types (Mystery Profile, This or That, Vibe Check, Hot Take, Common Ground), personality card generation (Pillow), inline button interactions.

**Phase 3: Intelligence** (Tasks 19-26) — Message observation pipeline, community pulse (weekly AI digest), bingo game, cross-community paywall (free tier limit), event-in-community, Sphere Global virtual community, full analytics dashboard, code review + bug fixes.

### Inherited Features (from global-mode-v1)
- Agent onboarding (AI-driven, personalized)
- Global matching (vector + LLM re-ranking)
- Sphere City (city-based matching)
- Profile expansion flow
- Vibe Check (AI compatibility game)
- Share/referral system
- Events system
- Conversation logging
- Admin dashboard (HTMX + Chart.js)

### Known Issues — Critical
1. **Games never expire** — scheduler doesn't check `ends_at`, `post_game_results` never called → after first game, new games permanently blocked per community (`scheduler_service.py`, `community_games.py`)
2. **Bingo is dead code** — service initialized in loader but not wired to scheduler, handlers, or keyboards (`loader.py`, `bingo_service.py`)
3. **Cross-community paywall counter** — `count_cross_community_matches` counts ALL community matches, not just cross-community → paywall triggers after 1st match (`match_repository.py`)
4. **Sync Pillow rendering** — personality card + bingo card block event loop, needs `run_in_executor` (`personality_card.py`, `bingo_service.py`)
5. **N+1 DB queries** — sequential `get_by_id` in loops in `bingo_service._generate_traits`, `game_service.create_mystery_profile`, `game_service.detect_common_ground`, `matching_service.find_community_matches`

### Known Issues — Important
6. Community context lost for non-agent onboarding paths (audio, v2, intent)
7. Observation summary never refreshes after first generation (permanent suppression in `observation_service.py`)
8. `auto_associate_user` is dead code — organic group users never get community-associated
9. Scheduler has no overlap protection; unbounded queries on communities, matches, observations
10. `run_sync` default thread pool (6 threads) — exhaustion risk under concurrent load
11. FSM in memory — `MemoryStorage()` loses state on Railway restart

---

## Architecture

```
sphere-bot/
├── adapters/telegram/
│   ├── handlers/
│   │   ├── start.py                # /start, menu, profile, reset, matches, Sphere Global join/skip
│   │   ├── onboarding_agent.py     # AI agent onboarding + personality card + expansion flow
│   │   ├── onboarding_audio.py     # Voice onboarding (legacy)
│   │   ├── matches.py              # Match display, pagination, notifications
│   │   ├── sphere_city.py          # City-based matching
│   │   ├── profile_edit.py         # Profile editing (quick + conversational)
│   │   ├── events.py               # Event creation & joining
│   │   ├── community_group.py      # NEW: Bot added/removed, passive message observation
│   │   ├── community_games.py      # NEW: Game posting, inline callbacks, results
│   │   ├── vibe_check.py           # AI compatibility game
│   │   ├── agent_chat.py           # Post-onboarding AI chat
│   │   └── personalization.py      # Post-onboarding personalization
│   ├── keyboards/inline.py         # All keyboards
│   ├── web/stats.py                # Admin dashboard (HTMX + Chart.js) with community analytics
│   ├── states/onboarding.py        # FSM states
│   └── loader.py                   # Bot & services init (all services wired here)
├── core/
│   ├── domain/
│   │   ├── models.py               # User, Event, Match, Community, CommunityMember, GameSession, GameResponse
│   │   └── constants.py            # INTERESTS, GOALS
│   ├── services/
│   │   ├── matching_service.py     # Vector + LLM + City + Community matching + cross-community paywall
│   │   ├── community_service.py    # NEW: Community lifecycle, admin sync, Sphere Global
│   │   ├── game_service.py         # NEW: 5 game types, question banks, LLM clue generation
│   │   ├── observation_service.py  # NEW: Batch topic/sentiment extraction via LLM
│   │   ├── community_pulse_service.py # NEW: Weekly AI community digest
│   │   ├── bingo_service.py        # NEW: 3x3 trait bingo with Pillow rendering
│   │   ├── scheduler_service.py    # NEW: Hourly tick — games, observations, pulse, reminders
│   │   └── event_service.py
│   ├── utils/
│   │   ├── personality_card.py     # NEW: Pillow personality card renderer
│   │   ├── deep_link_parser.py     # NEW: Parse deep link attribution
│   │   └── qr_generator.py         # QR code generation
│   └── prompts/
│       └── audio_onboarding.py     # Chain-of-thought extraction prompts
├── infrastructure/
│   ├── database/
│   │   ├── user_repository.py      # includes embeddings, city, global candidates
│   │   ├── match_repository.py     # includes community matches, cross-community counts
│   │   ├── community_repository.py # NEW: Community + CommunityMember CRUD
│   │   ├── game_repository.py      # NEW: GameSession + GameResponse CRUD
│   │   ├── event_repository.py     # includes community_id support
│   │   ├── speed_dating_repository.py
│   │   ├── conversation_log_repository.py
│   │   └── supabase_client.py
│   └── ai/
│       ├── openai_service.py       # GPT-4o-mini matching + profession context
│       ├── orchestrator_service.py  # Agent onboarding orchestrator
│       ├── whisper_service.py       # Voice transcription
│       ├── embedding_service.py     # text-embedding-3-small
│       └── speed_dating_service.py
├── supabase/migrations/
│   ├── 016_community_tables.sql    # NEW: communities, community_members, game_sessions, game_responses, message_observations
│   └── (earlier migrations inherited)
└── .credentials/keys.md            # All credentials (gitignored)
```

---

## Database Schema (Community-Specific Tables)

### communities
```sql
id UUID PK, telegram_group_id BIGINT UNIQUE, name TEXT
owner_user_id UUID FK, is_active BOOLEAN, member_count INT
settings JSONB, created_at TIMESTAMPTZ
-- settings: {reminder_enabled, reminder_hours, games_enabled, game_hours,
--            pulse_days, cross_community_matching, max_free_cross_matches,
--            last_reminder_at, last_game_at, last_pulse_at}
```

### community_members
```sql
id UUID PK, community_id UUID FK, user_id UUID FK
role TEXT (admin/member), is_onboarded BOOLEAN
joined_via TEXT (deep_link/auto_detected/referral/tg_admin_sync)
joined_at TIMESTAMPTZ
-- UNIQUE(community_id, user_id)
```

### game_sessions
```sql
id UUID PK, community_id UUID FK, game_type TEXT
status TEXT (active/ended), game_data JSONB
telegram_message_id BIGINT, ends_at TIMESTAMPTZ
created_at TIMESTAMPTZ
```

### game_responses
```sql
id UUID PK, game_session_id UUID FK, user_id UUID FK
response JSONB, is_correct BOOLEAN
created_at TIMESTAMPTZ
-- UNIQUE(game_session_id, user_id)
```

### message_observations
```sql
id UUID PK, community_id UUID FK, user_id UUID FK
topics TEXT[], sentiment TEXT, snippet TEXT
message_type TEXT, created_at TIMESTAMPTZ
```

### users (added columns)
```sql
tier TEXT DEFAULT 'free'  -- 'free' or 'pro'
community_profile_summary TEXT  -- AI-generated from observations
```

### matches (added column)
```sql
community_id UUID FK  -- NULL for non-community matches
```

### events (added column)
```sql
community_id UUID FK  -- For events linked to a community
```

---

## Key Patterns

### Community Game Lifecycle
```
create → post to group (inline buttons) → collect responses → end → reveal results
Game types: mystery_profile, this_or_that, vibe_check, hot_take, common_ground
Callback format: game_{uuid}_{action}_{param}
```

### Deep Link Attribution
```
community_{uuid}                    → joined from group deep link
community_{uuid}_ref_{tg_id}        → group + referral tracking
event_{code}_community_{uuid}       → event inside community
ref_{tg_id}                         → referral only
(no args)                           → organic
```

### Scheduler (Hourly Tick)
```
1. Drain observation queue → batch LLM extraction
2. For each active community:
   a. Maybe launch game (configurable interval, default 24h)
   b. Maybe send pulse (configurable interval, default 7d)
   c. Maybe send reminder (configurable interval, default 48h)
3. Skip Sphere Global (sentinel group_id = -1)
4. First-run guard: initialize timestamps for new communities
```

### Sphere Global
- Virtual community with `telegram_group_id = -1` (sentinel)
- Offered after onboarding for DM users not from a community
- Users can join/skip via inline buttons
- Skipped by auto_associate_user and scheduler

### Cross-Community Paywall
- `user.tier`: 'free' (default) or 'pro'
- Free tier: 1 cross-community match limit
- `matching_service.check_cross_community_paywall()` returns paywall status

---

## Commits (community-v1 branch)

1. `de85478` — Python 3.9 compat fix + Phase 1 verification
2. `c1c17a8` — Game engine + 5 game types
3. `688cd31` — Personality Card (Pillow)
4. `3eb4b69` — Observation pipeline + pulse + bingo
5. `5deea9e` — Cross-community paywall + event-in-community + Sphere Global
6. `0935048` — 11 bug fixes from code review
7. `be660bd` — Full analytics dashboard
8. `e0fe182` — CLAUDE.md + .memory/ update
9. `a0ddb18` — Dashboard review fixes (XSS, Chart.js HTMX, query limits)

---

## Railway Structure
| Project | Environment | Service | Bot | Branch |
|---------|-------------|---------|-----|--------|
| `loving-possibility` | Main | `sphere-production` | @Spheresocial_bot | `main` |
| `loving-possibility` | Community | `Service (Community)` | @Matchd_bot | `community-v1` |
| `Sphere Marketing` | production | marketing agent | — | — |

## Worktree Layout
| Location | Branch | Purpose |
|----------|--------|---------|
| `sphere-bot/` | `main` | Archive |
| `worktrees/sphere-community/` | `community-v1` | Active dev (THIS) |
| `worktrees/sphere-global/` | `global-mode-v1` | Global mode |

---

## Environment Variables

```bash
TELEGRAM_BOT_TOKEN=xxx
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
OPENAI_API_KEY=sk-xxx
ADMIN_TELEGRAM_IDS=123,456
DEBUG=true
DEFAULT_MATCH_THRESHOLD=0.6
ONBOARDING_MODE=agent
```
