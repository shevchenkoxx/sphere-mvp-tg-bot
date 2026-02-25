# Sphere Bot — Global Mode

## Branch: `global-mode-v1` (@Matchd_bot)
- **Branch:** `global-mode-v1`
- **Bot:** @Matchd_bot (not production!)
- **Railway:** Auto-deploys from `global-mode-v1` branch (service: `humorous-enchantment`)
- **DO NOT** push to main from here!

## Overview
Telegram bot for meaningful connections. Global Mode = no events required, universal matching. Events supported optionally.

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

**Every session must:**
1. Read `.memory/status.md` to understand current state
2. Create/append `.memory/sessions/YYYY-MM-DD.md` with changes
3. Update `.memory/status.md` with new state
4. Append to `.memory/decisions.md` for any architectural decisions
5. Commit `.memory/` changes with the rest of the code

### Branch Safety
- This is `sphere-bot/` on branch **global-mode-v1**
- Production is on branch **main**
- ALWAYS verify `git branch` before committing
- Push with `git push origin global-mode-v1` (NOT main!)

### Credentials
- **All credentials stored in:** `.credentials/keys.md` (gitignored)
- Supabase URL, Service Key, DB Password
- OpenAI API Key
- Telegram Bot Token (different from production!)

### Deploy
- **ALWAYS push to git** for Railway deployment
- Railway auto-deploys from `v1.1` branch for this bot
- After `git push origin v1.1` wait ~1-2 min for deploy

### Database (Supabase)
- URL: `https://cfppunyxxelqutfwqfbi.supabase.co`
- **psql path:** `/opt/homebrew/Cellar/libpq/18.1/bin/psql`
- Direct SQL: `/opt/homebrew/Cellar/libpq/18.1/bin/psql "postgresql://postgres:[password]@db.cfppunyxxelqutfwqfbi.supabase.co:5432/postgres"`
- Migrations in `supabase/migrations/`
- **Claude CAN run migrations directly** via psql

### Testing
- **Production event: `POSTSW24`** (Post Software - Feb 4, 2026)
- Deep link: `t.me/Spheresocial_bot?start=event_POSTSW24`
- QR code: `POSTSW24_QR.png` in project root
- Test event: `TEST2024`
- Reset profile: `/reset` in bot (needs DEBUG=true or admin)
- Find matches: `/find_matches` - manually trigger AI matching
- Demo mode: `/demo` - interactive walkthrough of all features

### Admin Commands
- `/stats [event_code]` - Event statistics (participants, matches, feedback)
- `/participants [event_code]` - List participants with details
- `/broadcast <text>` - Send message to all event participants
- `/event [code]` - Show event info (or list all active events)
- `/checkmatches [event_code]` - Show all matches with time, users, score, feedback, AI explanation
- `/followup [event_code]` - Send follow-up check-in to all participants with matches

### Auto-Matching (Event Testing)
- **Script:** `scripts/event_matching_test.py`
- Runs every 20 min, sends admin TG notifications
- Start: `nohup python3 scripts/event_matching_test.py &`
- Stop: `pkill -f event_matching`
- Log: `event_matching.log`

### Test Bot (Staging)
- **Bot**: @Socialconnection_bot
- **Branch**: `staging`
- **Bot Token**: in `.credentials/keys.md`
- **Railway**: separate service, deploys from `staging` branch
- **DEBUG=true**: shows test mode selector on /start

---

## Current Status (February 13, 2026)

### V1.1 NEW Features

1. **Intent-Based Onboarding** (`onboarding_intent.py` — 1517 lines)
   - User picks intents: Networking / Friendship / Romance / Hookup
   - 4 onboarding modes:
     - **Agent** — free-form LLM conversation (3-layer: chat/extraction/strategy)
     - **Voice** — 4 guided stages with Whisper transcription
     - **Quick Choices** — button-based Q&A from question bank
     - **Social Media** — import from URL/screenshot with GPT-4o vision
   - City selection + photo request + profile confirmation
   - Activate with `ONBOARDING_MODE=intent`

2. **Daily Questions** (`daily_question.py` — 623 lines)
   - 53 questions across 6 categories (networking, friends, romance, hookup, self_discovery, icebreaker)
   - Gap-based selection (asks what's missing from profile)
   - LLM follow-up chat after answer
   - Auto-extraction to profile + embedding regeneration

3. **Profile Enrichment** (`profile_enrichment.py` — 438 lines)
   - Works anytime (StateFilter(None) — only outside FSM states)
   - Voice → transcribe + extract + merge
   - Link → fetch URL + LLM extraction
   - Screenshot → GPT-4o vision analysis

4. **i18n System** (`locales/en.py`, `locales/ru.py`)
   - `t(key, lang, **kwargs)` function for all strings
   - Full EN/RU support
   - Language saved to user profile

5. **Question Bank** (`questions/bank.py` — 560 lines)
   - 53 questions with EN/RU text
   - Categories, intent tags, depth levels, extract targets
   - Smart selection based on user intents + asked questions

6. **DB Schema** (`012_v1_1_schema.sql`)
   - New user columns: connection_intents[], gender, looking_for_gender[], age_range, partner_values[], personality_vibe, hookup_preference, language
   - New table: user_questions (tracks asked questions + answers)

### Inherited Features (from main)

- Vector-Based Matching (pgvector + LLM re-ranking)
- Audio/Text/v1 Onboarding (still available, mode-selectable)
- Profile System + Editing (quick + conversational)
- Event System + QR codes
- Matches Display + Pagination
- Sphere City (city-based matching)
- AI Speed Dating
- Meetup Proposals
- Admin Commands (/stats, /participants, /broadcast, etc.)

### NOT on V1.1 (main only)
- Vibe Check AI compatibility game (vibe_check.py, vibe_check.py prompts, 012_vibe_checks.sql)

### Known Issues
1. **FSM in memory** — MemoryStorage() loses state on restart
2. **Migration not run** — 012_v1_1_schema.sql may need to be executed on Supabase
3. **Not tested yet** — intent onboarding needs end-to-end testing

---

## Architecture

```
sphere-bot/
├── adapters/telegram/
│   ├── handlers/
│   │   ├── start.py           # /start, menu, profile, reset, matches menu
│   │   ├── profile_edit.py    # Profile editing (quick + conversational)
│   │   ├── onboarding_audio.py # Voice onboarding + selfie + /test_extract
│   │   ├── onboarding_v2.py    # Text onboarding flow
│   │   ├── matches.py          # Match display, pagination, notifications
│   │   ├── sphere_city.py      # City-based matching (Sphere City)
│   │   └── events.py           # Event creation & joining
│   ├── keyboards/inline.py     # All keyboards + city picker + Sphere City
│   ├── web/stats.py              # Admin dashboard (aiohttp + HTMX + Chart.js)
│   ├── states/onboarding.py    # FSM states (includes ProfileEditStates)
│   └── loader.py               # Bot & services init (includes embedding_service)
├── core/
│   ├── domain/
│   │   ├── models.py           # User, Event, Match (with city field)
│   │   └── constants.py        # INTERESTS, GOALS
│   ├── services/
│   │   ├── matching_service.py # Vector + LLM + City matching
│   │   └── event_service.py
│   └── prompts/
│       └── audio_onboarding.py # Chain-of-thought extraction prompts
├── infrastructure/
│   ├── database/
│   │   ├── user_repository.py  # includes update_embeddings(), get_users_by_city()
│   │   ├── match_repository.py # includes get_city_matches()
│   │   ├── speed_dating_repository.py # AI Speed Dating cache
│   │   ├── conversation_log_repository.py # Message logging + analytics queries
│   │   └── supabase_client.py
│   └── ai/
│       ├── openai_service.py   # GPT-4o-mini + profession/skills in matching
│       ├── whisper_service.py  # Voice transcription
│       ├── embedding_service.py # text-embedding-3-small
│       ├── speed_dating_service.py # AI Speed Dating conversation generator
│       └── event_parser_service.py # LLM URL parser for event info
├── scripts/
│   ├── test_extraction.py      # CLI for testing extraction prompts
│   ├── auto_matching.py        # Original auto-matching (deprecated)
│   ├── event_matching_test.py  # Event matching with admin notifications
│   ├── backfill_embeddings.py  # Generate embeddings for users missing them
│   └── test_matching.py        # End-to-end matching pipeline test
├── supabase/migrations/
│   ├── 002_enhanced_profiles.sql
│   ├── 003_vector_embeddings.sql # pgvector + match_candidates()
│   ├── 004_sphere_city.sql     # experience_level, city on matches
│   ├── 005_speed_dating.sql    # AI Speed Dating cache table
│   ├── 006_match_feedback.sql  # Match feedback (👍/👎)
│   └── 007_event_info.sql      # Event info JSONB (schedule, speakers)
└── .credentials/keys.md        # All credentials (gitignored)
```

---

## Database Schema

### users
```sql
id, platform, platform_user_id, username, first_name, display_name
interests[], goals[], bio
looking_for, can_help_with
photo_url, voice_intro_url
ai_summary, onboarding_completed
current_event_id, city_current
-- Vector embeddings (1536 dims each)
profile_embedding, interests_embedding, expertise_embedding
-- Professional info (populated from extraction)
profession, company, skills[], experience_level
-- Available but unused
linkedin_url, linkedin_data, deep_profile
```

### events
```sql
id, code, name, description, location, event_date
organizer_id, is_active, settings
```

### matches
```sql
id, event_id, user_a_id, user_b_id
compatibility_score, match_type
ai_explanation, icebreaker
status (pending/accepted/declined)
user_a_notified, user_b_notified
city  -- For Sphere City matches (event_id is NULL)
```

### messages (exists but unused)
```sql
id, match_id, sender_id, content, is_read, created_at
```

### speed_dating_conversations
```sql
id, match_id, viewer_user_id
conversation_text, language
created_at
-- Unique constraint: (match_id, viewer_user_id)
```

### match_feedback (NEW)
```sql
id, match_id, user_id
feedback_type ('good' or 'bad')
created_at
-- Unique constraint: (match_id, user_id)
```

---

## Key Implementation Details

### Embedding Generation (Background, Non-blocking)
```python
# In onboarding handlers - fire and forget
async def generate_embeddings_background(user_obj):
    result = await embedding_service.generate_embeddings(user_obj)
    if result:
        await user_repo.update_embeddings(user_obj.id, *result)

asyncio.create_task(generate_embeddings_background(user))
```

### Vector Matching
```python
# Stage 1: pgvector similarity search (fast)
candidates = await matching_service.find_vector_candidates(user, event_id, limit=10)

# Stage 2: LLM re-ranking (thorough)
for candidate, vector_score in candidates:
    result = await self.analyze_pair(user, candidate, event_name)
```

### Selfie Flow with Error Handling
```python
# Always clears state even on error
async def finish_onboarding_after_selfie(...):
    try:
        # ... show matches
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("Profile ready!", reply_markup=menu)
    finally:
        await state.clear()
```

---

## Roadmap / TODO

### 🔴 Phase 1: Critical (Next)

| Feature | Description | Status |
|---------|-------------|--------|
| ~~Profile Editing~~ | Hybrid: manual fields + LLM conversational | ✅ Done |
| **In-app Messaging** | Chat within bot, DB ready | TODO |
| **Match Actions** | Accept/Decline/Met buttons | TODO |
| **Auto-join Event** | After onboarding, auto-join pending event | TODO |

### 🟡 Phase 2: Quality

| Feature | Description | Status |
|---------|-------------|--------|
| ~~Match Feedback~~ | 👍/👎 buttons on match cards | ✅ Done |
| Language Preference | Save during onboarding | TODO |
| Fix Fallback Language | Pass lang to analyze_match() | TODO |
| Follow-up Reminders | "Remind me to contact X" | TODO |

### 🟢 Phase 3: Growth

| Feature | Description | Status |
|---------|-------------|--------|
| Event Discovery | Browse available events | TODO |
| **Event Info System** | Schedule, speakers, topics for LLM context | TODO |
| Use All Embeddings | Update match_candidates() SQL | TODO |
| **Refer a Friend** | Dynamic top 3 topics based on actual user looking_for data aggregation | TODO |

### 📊 Phase 4: Organizers

| Feature | Description | Status |
|---------|-------------|--------|
| **Analytics Dashboard** | Participant count, matches, feedback stats | TODO |
| Participant Profiles | View individual profiles | TODO |
| Export CSV | Participant list export | TODO |
| Per-event Settings | Adjust matching threshold per event | TODO |

---

## Future Feature Plans

### Event Info System (Priority)

**Goal:** Allow organizers to add custom event info that improves matching context.

**Database Changes:**
```sql
-- Add to events table or create new table
ALTER TABLE events ADD COLUMN event_info JSONB DEFAULT '{}';

-- event_info structure:
{
  "schedule": [
    {"time": "10:00", "title": "Opening", "speaker": "John"},
    {"time": "11:00", "title": "AI Panel", "topics": ["LLM", "agents"]}
  ],
  "speakers": [
    {"name": "John Doe", "bio": "CEO of X", "topics": ["startup", "funding"]}
  ],
  "topics": ["AI", "Web3", "Startups"],
  "networking_focus": "B2B partnerships",
  "matching_hints": "Focus on co-founder matches"
}
```

**Implementation:**
1. **Admin command:** `/event_info <code>` to set/edit event info
2. **FSM flow:** Add schedule → Add speakers → Add topics → Confirm
3. **Matching integration:** Pass `event_info` to `analyze_match()` prompt
4. **Display:** Show relevant event context in match cards

**Files to modify:**
- `supabase/migrations/007_event_info.sql` - DB schema
- `adapters/telegram/handlers/events.py` - Admin FSM for editing
- `infrastructure/ai/openai_service.py` - Include in matching prompt
- `adapters/telegram/handlers/matches.py` - Display context

**Matching Prompt Update:**
```python
# In analyze_match(), add event context:
event_context = f"""
Event: {event_name}
Focus: {event_info.get('networking_focus', 'General networking')}
Topics: {', '.join(event_info.get('topics', []))}
Hint: {event_info.get('matching_hints', '')}
"""
```

---

### Analytics Dashboard (Phase 4)

**Goal:** Real-time stats for organizers during events.

**Metrics to track:**
- Participants count (total, new in last hour)
- Matches created (total, pending, accepted)
- Feedback ratio (👍 vs 👎)
- Most matched participants (top 5)
- Matching quality score (avg compatibility)
- Response rate (matches viewed / total)

**Implementation options:**
1. **In-bot:** `/analytics` command with formatted text
2. **Web dashboard:** Simple Next.js page with Supabase realtime
3. **Telegram Mini App:** Native-feeling analytics

**Recommended:** Start with `/analytics` command, then web dashboard.

**Example output:**
```
📊 POSTSW24 Analytics (Live)

👥 Participants: 47 (+5 in last hour)
💫 Matches: 89 total
   ├ Pending: 34
   ├ Accepted: 55
   └ Rate: 62%

⭐ Quality: 0.67 avg score
📈 Feedback: 23 👍 / 4 👎 (85% positive)

🏆 Top Networkers:
1. Alex - 8 matches
2. Maria - 7 matches
3. John - 6 matches
```
| Participant Profiles | View individual profiles | 2h |
| Export CSV | Participant list export | 2h |
| Per-event Settings | Adjust matching threshold | 2h |

---

## Profile Editing (Implemented)

**Two modes:**
1. **Quick Edit** - Select field → Type/voice new value → Preview → Confirm
2. **Conversational** - "Add crypto to my interests" → LLM interprets → Preview → Confirm

**Flow:**
```
👤 Profile → ✏️ Edit →
  ├── 📝 Edit field (bio/interests/goals/looking_for/can_help_with/photo)
  │     └── Enter new value (text or voice) → Preview → Confirm
  └── 💬 Describe changes
        └── LLM parses request → Preview → Confirm
```

**Key files:**
- `adapters/telegram/handlers/profile_edit.py` - Main handler
- `adapters/telegram/states/onboarding.py` - ProfileEditStates
- `adapters/telegram/keyboards/inline.py` - Edit keyboards

**After edit:**
- Update DB via user_service.update_user()
- Regenerate embeddings in background (asyncio.create_task)
- Show "Continue editing" or "Done" options

---

## Environment Variables

```bash
TELEGRAM_BOT_TOKEN=xxx          # V1.1 test bot token (NOT production!)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
SUPABASE_SERVICE_KEY=xxx
OPENAI_API_KEY=sk-xxx
ADMIN_TELEGRAM_IDS=123,456
DEBUG=true
DEFAULT_MATCH_THRESHOLD=0.4
ONBOARDING_MODE=intent          # V1.1: use "intent" mode
DB_SCHEMA=v1_1                  # Optional: schema isolation
```

---

## Recent Session Changes

### February 21, 2026 — Dashboard Analytics Full Upgrade

**Admin dashboard** (`adapters/telegram/web/stats.py`) — major upgrade from basic stats to full analytics suite.

**Foundation:**
- Chart.js CDN + auto-destroy on HTMX swap
- New CSS: filter bars, funnel visualization, activity heatmap
- Helpers: `_parse_range()`, `_date_range_picker_html()`, `_chart_html()`, `_funnel_html()`

**Overview tab:**
- Date range picker (Today/7d/30d/All)
- Daily signups line chart (30d)
- Conversion funnel: Total → Onboarded → Got matches → Active (7d)
- Profile depth distribution doughnut

**Users tab — multi-filter:**
- City dropdown (with counts), Intent dropdown, Onboarding status, Has photo, Date range
- HTMX `change` triggers on selects

**Onboarding tab (NEW — `/stats/onboarding`):**
- FSM state funnel (drop-off analysis)
- Onboarding mode distribution doughnut (agent/voice/quick/social)
- Avg onboarding duration
- Profile completeness histogram

**Matches tab — analytics:**
- Stat cards: total, pending/accepted/declined, avg score, feedback ratio
- Score distribution bar chart (5 buckets)
- Matches over time line chart (30d)
- Top 10 matched users table

**Conversations tab — analytics:**
- Summary cards: total messages, in/out, unique users, avg per user
- Message type doughnut (text/voice/photo/callback)
- Activity heatmap (7 days × 24 hours)
- Content search toggle (search by name / search messages)

**Files modified:** `adapters/telegram/web/stats.py` (1402→2182 lines), `infrastructure/database/conversation_log_repository.py` (+2 methods: `get_fsm_state_logs`, `get_message_stats`)

---

### February 19, 2026 — Agent Onboarding Bug Fixes + SOTA Prompt

**Bug fixes (agent onboarding — silent bot):**
1. `orchestrator_service.py`: `tool_choice="none"` on follow-up, skip when show_profile/complete, fallback text
2. `onboarding_agent.py`: `parse_mode="HTML"`, HTML escape, always respond, fix user_id fallback
3. `orchestrator_models.py`: fix `trim_messages` (don't break tool groups), fix `from_dict`

**Matches / Sphere City:**
4. Fix `show_matches` crash (None state), double callback.answer()
5. Sphere City: random 10-150 available matches, "🔒 Unlock" instead of @username
6. Profile edit: handle URL text gracefully

**SOTA Prompt (complete rewrite):**
7. Personality-driven: "friend at a party" not "service bot"
8. Zero topic restrictions
9. Stealth data extraction through stories
10. Mirror matching: adapts to user's style
11. Banned corporate speak, conversational markers

**Data:**
12. 10 fake Warsaw users (diverse profiles, no usernames)

**Files modified:** `orchestrator_service.py`, `orchestrator_models.py`, `orchestrator_prompts.py`, `onboarding_agent.py`, `sphere_city.py`, `start.py`, `profile_edit.py`

---

### February 18, 2026 — Conversation Logging + AI UI + Agent Chat

See `progress.md` for full details.

---

### February 12, 2026 - SXN Event Day Session 4 (Pre-Event Final)

**Bot renamed:** @Matchd_bot → @Spheresocial_bot

**Round 4 fixes (this session):**

1. **Chat button → direct TG chat** — `get_profile_view_keyboard()` now accepts `partner_username`, uses URL button `https://t.me/{username}` when available (same pattern as match card keyboard). Also fixed `get_meetup_confirmation_keyboard()` to use URL button instead of callback.
2. **Anytime in meetup time picker** — Added `0` = "Anytime" to `MEETUP_TIME_SLOTS`. New `_format_time_slot()` helper in meetup.py. Receiver keyboard, preview, confirmation all display "Anytime" correctly.
3. **Matching prompt softened** — Removed strict "NEVER infer" rules. Now allows smart approximation within same domain. Prevents cross-domain leaps (leadership ≠ design). Weights: VALUE EXCHANGE 0.4, TOPIC RELEVANCE 0.35, GOALS 0.25.
4. **Invitations section** — New "📩 Invitations" button in main menu with pending count badge. Handler `show_invitations` lists pending meetup proposals with accept/decline buttons. New `get_received_pending()` method in meetup_repository.
5. **Bot username switch** — All hardcoded `Matchd_bot` → `Spheresocial_bot` in start.py + CLAUDE.md.

**Round 3 fixes (previous in this session):**
6. **Instagram @sphere.match** — clickable HTML link with full Instagram URL
7. **Remove Moscow from cities** — removed from SPHERE_CITIES
8. **Remove all text truncation** — 6 locations in matches.py, 3 in start.py — full text shown
9. **Photo handlers in onboarding** — added for `confirming` and `adding_details` states
10. **experience_level saved to DB** — was extracted but lost, now saved in `save_audio_profile()`
11. **Tighter matching (now softened)** — strict VALUE EXCHANGE only, no inferred synergy
12. **Live profile refresh** — edits existing profile message instead of sending new

**Round 2 fixes (previous in this session):**
13. Confirmation footer text → "Just send a message and I'll add new details"
14. Giveaway Date Dinner text + +2 chances restored
15. Refer a Friend "Make matches sharper" copy with 6 categories + QR code
16. Keep profile visible when adding details
17. Photo display during match pagination (delete+resend)
18. Fix double message when loading matches
19. Chat button photo message handling
20. Delayed optimization — check if user has matches
21. SHOW_TOP_MATCHES 3→5
22. Welcome giveaway teaser updated

**Key files modified this session:**
- `adapters/telegram/keyboards/inline.py` — profile view URL button, menu invitations, Anytime, meetup confirmation URL
- `adapters/telegram/handlers/start.py` — invitations handler, back_to_menu badge, bot username
- `adapters/telegram/handlers/meetup.py` — _format_time_slot(), Anytime display
- `adapters/telegram/handlers/matches.py` — profile view partner_username
- `infrastructure/ai/openai_service.py` — softened matching prompt
- `infrastructure/database/meetup_repository.py` — get_received_pending()

---

### February 12, 2026 - SXN Event Day (Live Event)

**Event: SXN - SeXXXess Night: Digital Intimacy & Dating Apps (Warsaw)**

**Changes deployed:**

1. **Admin match notifications** — bot notifies admin on every new match (user, partner, score, event)
2. **Multi-select personalization** — Step 3 adaptive buttons now toggle with ✓, "Done (N) →" button
3. **`/checkmatches` admin command** — all matches with timestamp, users, score, feedback, AI explanation
4. **Stuck user handling:**
   - `/start` clears FSM state (unstick mid-flow users)
   - Catch-all handler for users with no state (prompts /start or shows menu)
   - Photo nudge 2 min after matches if no photo
5. **Bug fixes from code review (3 agents):**
   - `match_prev`/`match_next`: added callback.answer(), state param, ValueError guard
   - `openai_service.py`: ValueError on MatchType enum now caught
   - `matching_service.py`: RPC response KeyError/ValueError guard, null event_name fix
6. **UX text updates:**
   - "Finding interesting people" → "Sphere is searching for the best possible matches"
   - Audio ready button keeps questions visible with parse_mode="HTML"
   - Match threshold capped at 0.4 (prevents Railway env override)
7. **Warm feedback messages** after match rating (👍/👎)
8. **Follow-up always English** with dinner draw reminder
9. **Language auto-detect** — default EN, switches to RU if Telegram lang is "ru"
10. **`/demo` updated** for SXN event theme

**Key files modified:**
- `adapters/telegram/handlers/matches.py` — admin notifications, feedback messages, nav fixes
- `adapters/telegram/handlers/onboarding_audio.py` — audio_ready questions, photo nudge, admin notif
- `adapters/telegram/handlers/start.py` — /start clears state, catch-all, demo SXN theme
- `adapters/telegram/handlers/personalization.py` — multi-select, text fix
- `adapters/telegram/handlers/events.py` — /checkmatches, /followup
- `adapters/telegram/keyboards/inline.py` — multi-select adaptive buttons
- `core/services/matching_service.py` — threshold cap, RPC fix, null event fix
- `infrastructure/ai/openai_service.py` — ValueError catch fix

---

### February 10, 2026 - Pre-Release Hardening

**Release target: February 12, 2026**

**Bug fixes (6 items):**

1. **Null-check in start_chat_with_match** (`matches.py`)
   - Added null checks on `user` and `partner` to prevent crash when partner is deleted

2. **Vector search fallback** (`matching_service.py`)
   - `find_vector_candidates()` now calls `_fallback_base_score_candidates()` on exception instead of returning empty list

3. **OpenAI API timeouts** (5 AI services)
   - `openai_service.py`: timeout=30s
   - `speed_dating_service.py`: timeout=30s
   - `conversation_ai.py`: timeout=30s
   - `whisper_service.py`: timeout=60s (sync, larger files)
   - `embedding_service.py`: timeout=20s (already had asyncio.wait_for, now also client-level)

4. **Graceful shutdown** (`main.py`)
   - Moved `bot.session.close()` to outer try/finally (was inside while loop = closed on every retry)
   - Session now always closes on exit, including on exceptions

5. **Reset error handling** (`user_service.py`)
   - Wrapped Supabase delete operations in try/except with logging
   - Reset continues even if cleanup of old matches/events fails

6. **"No matches" UX** (`matches.py`)
   - Now shows specific reason: no event joined / not enough participants / profile incomplete / just try later
   - Different messages for each case in both EN and RU

**Data fixes:**
- Backfilled embeddings for 25/28 users who were missing them (all 28 now have embeddings)
- Cleaned up test matches

**New scripts:**
- `scripts/backfill_embeddings.py` - one-off script to generate embeddings for all users
- `scripts/test_matching.py` - end-to-end test of vector matching pipeline

**Systems tested (all OK):**
- Supabase DB connection + REST API
- Telegram Bot API (@Spheresocial_bot)
- OpenAI API (models endpoint)
- pgvector extension (v0.8.0) + match_candidates() function
- All 8 database tables present
- Full matching pipeline: vector search -> LLM re-ranking -> match creation
- All Python files compile without errors

**DB state:**
- 28 users (all onboarded, all with embeddings)
- 2 events: TEST2024 (26 participants), POSTSW24 (2 participants)
- 0 matches (cleaned for release)

---

### February 4, 2026 - Post Software Event Prep

**Current Runtime Status:**
- Auto-matching script running (PID checked via `ps aux | grep event_matching`)
- Log: `event_matching.log` - shows iterations and new matches
- Admin notifications: Telegram chat_id 44420077
- Participants: 2 (Admin "A" + Test Profile)
- Matches created: 1 (score 0.55)
- Next iteration: every 20 min until 23:59

**To check status:**
```bash
# Check if running
ps aux | grep event_matching

# View log
tail -f event_matching.log

# Stop
pkill -f event_matching
```

---

1. **Event POSTSW24 Created**
   - Code: `POSTSW24`
   - QR: `POSTSW24_QR.png`
   - Deep link: `t.me/Spheresocial_bot?start=event_POSTSW24`

2. **Photo Request Moved to Matches Tab**
   - Removed selfie request from onboarding
   - Now asks for photo when opening Matches (if no photo)
   - User can skip with "Later" button

3. **Feedback Buttons Added**
   - 👍/👎 buttons on match cards
   - Saves to `match_feedback` table
   - Migration: `006_match_feedback.sql`

4. **Improved Matching Logic**
   - `base_score` now considers `looking_for` ↔ `can_help_with` match (+0.4)
   - Better pre-filtering before LLM analysis
   - Lower threshold for testing (0.3)

5. **Enhanced Match Profile Display**
   - Shows profession + company as subtitle
   - City + experience level
   - Up to 10 hashtags (interests + skills)
   - Goals with emoji labels

6. **AI Speed Dating Updated**
   - Skips small talk, goes straight to collaboration
   - Short messages (1 sentence max)
   - Concrete next steps at end

7. **Auto-Matching Script**
   - `scripts/event_matching_test.py`
   - Runs every 20 min until 23:59
   - Admin TG notifications for new matches
   - Generates missing embeddings automatically

8. **Bug Fixes**
   - Fixed UUID type mismatch in `current_event_id` (was breaking event join)
   - Removed redundant event join update in onboarding
   - Added missing keyboard exports to `__init__.py`

9. **Test Profile Created**
   - Name: "Test Profile"
   - AI Engineer @ OpenAI
   - In POSTSW24 event

10. **Language Always English**
    - All `detect_lang` functions now return "en"
    - Telegram language settings ignored
    - Files changed: start.py, matches.py, sphere_city.py, events.py, profile_edit.py, personalization.py, onboarding_audio.py, onboarding_v2.py

11. **Photo Display Fixed**
    - Photos now shown WITH profile text as caption (not separate)
    - Telegram caption limit handled (1024 chars)
    - Keyboard attached to photo message

12. **Matching Prompt Bug Fixed**
    - User model was missing `profession`, `company`, `skills`, `experience_level`
    - Added to `core/domain/models.py` User class
    - Added to `infrastructure/database/user_repository.py` `_to_model()`
    - Now "Why this match" uses all profile data

13. **Event Info System** (NEW)
    - JSONB field `event_info` in events table
    - LLM URL parser: fetch page → GPT extracts schedule, speakers, topics
    - New buttons in event management: ℹ️ Info, 🔗 Import URL, ✏️ Edit, 📢 Broadcast
    - Rich event card display with schedule preview, speakers list
    - Files: `infrastructure/ai/event_parser_service.py`, `007_event_info.sql`
    - FSM: `EventInfoStates` for import and broadcast flows

### February 5, 2026 - Session 2

14. **Admin Commands Added**
    - `/stats [code]` - Event statistics (participants, matches, feedback)
    - `/participants [code]` - List participants with details
    - `/broadcast <text>` - Send message to all event participants
    - `/event [code]` - Show event info or list all active events

15. **Demo Command** `/demo`
    - Interactive walkthrough of all bot features
    - Shows: QR flow → Onboarding → Profile → Matching → Match card
    - Great for presentations and onboarding new users
    - "Try it now" button starts real onboarding

16. **Reset Fixed**
    - `/reset` now fully clears: events, matches, all profile fields
    - Deletes from `event_participants` table
    - Deletes user's matches
    - Clears embeddings, city, profession, etc.

17. **Auto-Matching on Demand**
    - When user clicks Matches and has none → automatically runs matching
    - After onboarding: embeddings generated → matching runs in background
    - User sees matches immediately, no need to wait

18. **No Matches CTA**
    - When no matches found, shows tip: "Add more info about yourself"
    - Buttons: ✏️ Add more info | 🔄 Try again | ◀️ Menu
    - "Try again" retries matching

---

### February 2026 - AI Speed Dating

1. **AI Speed Dating Feature** (NEW)
   - Button "⚡ AI Speed Dating" on match cards
   - Generates simulated 5-exchange conversation between users
   - Uses GPT-4o-mini with personas built from profiles
   - Cached in `speed_dating_conversations` table
   - "Regenerate" bypasses cache for new conversation
   - Auto-detects language (RU/EN) from profile content

2. **New Files**
   - `infrastructure/ai/speed_dating_service.py` - conversation generation
   - `infrastructure/database/speed_dating_repository.py` - DB cache
   - `supabase/migrations/005_speed_dating.sql` - table schema

3. **Modified Files**
   - `adapters/telegram/loader.py` - init speed_dating_service, speed_dating_repo
   - `adapters/telegram/keyboards/inline.py` - added button + result keyboard
   - `adapters/telegram/handlers/matches.py` - speed_dating_preview handler

---

### February 2026 - Extraction & Sphere City

1. **Sphere City Feature** (NEW)
   - City-based matching outside events
   - City picker with major cities + custom input
   - New handler: `sphere_city.py`
   - New keyboards: city picker, Sphere City menu
   - Matches menu now shows Event + Sphere City options

2. **Enhanced Extraction (Chain-of-thought)**
   - Updated `AUDIO_EXTRACTION_PROMPT` with step-by-step analysis
   - Steps: FACTS → CONTEXT → INSIGHTS → JSON
   - Now saves: profession, company, skills, city_current
   - Extended `validate_extracted_profile()` with more fields

3. **Improved Matching Prompt**
   - Now includes profession, company, skills in matching context
   - Better professional matching with additional context

4. **Testing Tools**
   - CLI script: `scripts/test_extraction.py`
   - Telegram command: `/test_extract` (admin-only)
   - Shows raw extraction JSON for debugging

5. **Database Migration**
   - `004_sphere_city.sql`: experience_level on users, city on matches

6. **Bug Fixes** (code review by agents)
   - Added `profession`, `company`, `skills` to `UserUpdate` model (data was silently lost)
   - Fixed `event_matches` to filter by current event only (was showing ALL matches)
   - Fixed double `callback.answer()` in `show_city_matches`
   - Added missing `state.clear()` in city selection handler
   - Removed unused `bot` import from sphere_city.py

### Previous Changes

1. **Profile Editing Feature**
   - Quick edit: select field → type/voice → preview → confirm
   - Conversational: describe changes → LLM parses → preview → confirm
   - Auto-regenerates embeddings in background after edit
2. **OpenAI chat() method** - Added generic chat method to OpenAIService
3. **Vector Matching** - pgvector + LLM two-stage pipeline
4. **Background Embeddings** - asyncio.create_task (non-blocking)
5. **Migration** - 003_vector_embeddings.sql executed

---

## Git Worktrees (Parallel Development)

Worktrees allow running multiple Claude sessions on different branches simultaneously.

| Directory | Branch | Purpose |
|-----------|--------|---------|
| `sphere-bot/` | main | Production code |
| `worktrees/sphere-bot-staging/` | staging | Test before deploy |
| `worktrees/sphere-bot-experiment/` | experiment | Experimental features |

**Commands:**
```bash
# List worktrees
git worktree list

# Create new feature worktree
git worktree add ../worktrees/sphere-bot-feature-name -b feature-name

# Remove when done
git worktree remove ../worktrees/sphere-bot-feature-name

# Merge staging to main
git merge staging && git push origin main
```

**Parallel Claude Sessions:**
- Open Claude Code in `sphere-bot/` for production
- Open another in `worktrees/sphere-bot-staging/` for testing
- They work independently without conflicts

---

## Claude Code Skills

Skills are invocable workflows in `.claude/skills/`:

| Skill | Command | Description |
|-------|---------|-------------|
| `/deploy` | Deploy to production | Syntax check → commit → push → Railway |
| `/migrate` | Run DB migration | Execute SQL on Supabase via psql |
| `/test-staging` | Test in worktree | Workflow for testing before merge |
| `/review` | Code review | Checklist for bugs, security, performance |

---

## Quick Commands

```bash
# Deploy (Claude can do this)
git add -A && git commit -m "message" && git push

# Run migration (Claude can do this)
/opt/homebrew/Cellar/libpq/18.1/bin/psql "postgresql://postgres:PASSWORD@db.cfppunyxxelqutfwqfbi.supabase.co:5432/postgres" -f supabase/migrations/XXX.sql

# Check syntax
python3 -m py_compile path/to/file.py

# List worktrees
git worktree list
```

---

## Claude Code Capabilities

**What I can do for this project:**

### Code
- Read, edit, write any file in the project
- Create new handlers, services, models
- Fix bugs, refactor code
- Add new features end-to-end
- Run syntax checks (`python3 -m py_compile`)

### Git & Deploy
- `git status`, `git diff`, `git log`
- Stage files, commit with proper messages
- **Push to origin → Railway auto-deploys** (I can do this!)
- Create branches, PRs via `gh` CLI

### Database (Supabase)
- Write SQL migrations
- Design schema changes
- **Run migrations via psql** (I can do this!)
- Query database directly
- Connection string in `.credentials/keys.md`

### AI/LLM
- Update prompts (extraction, matching, onboarding)
- Test and iterate on prompt quality
- Add new AI features

### Research & Analysis
- Search codebase with Glob/Grep
- Read and understand any file
- Web search for docs/solutions
- Review code for bugs (via subagents)

### Project Management
- Update CLAUDE.md with current state
- Create/update task lists
- Plan features before implementation
- Track what's done vs TODO

**What I need help with:**
- Testing in actual Telegram (need you to interact with bot)
- Approving destructive git operations (force push, reset --hard)

**What I CAN do autonomously:**
- Run database migrations via psql
- Git add, commit, push to deploy
- Read credentials from `.credentials/keys.md`
