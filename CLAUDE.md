# Sphere Bot - Project Documentation

## Overview
Telegram bot for meaningful connections at events. Users scan QR → quick voice onboarding → AI matching → meet interesting people.

**Bot:** @Matchd_bot
**Repo:** https://github.com/shevchenkoxx/sphere-mvp-tg-bot
**Deploy:** Railway (auto-deploy from main branch)

---

## IMPORTANT for Claude Code

### Context Management Rules
1. **After every important change** - update this CLAUDE.md file with current status
2. **Before 5% context remaining** - MUST update CLAUDE.md with full project state
3. **Always maintain** super clear and detailed context in this file
4. **On session start** - read this file first to understand project state

### Credentials
- **All credentials stored in:** `.credentials/keys.md` (gitignored)
- Supabase URL, Service Key, DB Password
- OpenAI API Key
- Telegram Bot Token

### Deploy
- **ALWAYS push to git** for Railway deployment
- Railway auto-deploys from `main` branch
- After `git push` wait ~1-2 min for deploy

### Database (Supabase)
- URL: `https://cfppunyxxelqutfwqfbi.supabase.co`
- Direct SQL: `psql "postgresql://postgres:[password]@db.cfppunyxxelqutfwqfbi.supabase.co:5432/postgres"`
- Migrations in `supabase/migrations/`

### Testing
- Test event: `TEST2024`
- Deep link: `t.me/Matchd_bot?start=event_TEST2024`
- Reset profile: `/reset` in bot (needs DEBUG=true or admin)
- Find matches: `/find_matches` - manually trigger AI matching

---

## Current Status (February 2026)

### Working Features ✅

1. **Vector-Based Matching**
   - Two-stage pipeline: pgvector similarity + LLM re-ranking
   - 70% fewer API calls (~350 vs 1,225 for 50 users)
   - OpenAI text-embedding-3-small (1536 dimensions)
   - Embeddings generated in background (non-blocking)
   - Auto-fallback to base score if embeddings unavailable

2. **Audio Onboarding**
   - LLM generates personalized intro
   - Voice transcription via Whisper (non-blocking)
   - AI extracts: about, looking_for, can_help_with, interests, goals
   - Validation: asks follow-up if key info missing
   - Selfie request after profile
   - Switch to text mode available

3. **Text Onboarding (v2)**
   - Conversational flow with LLM
   - Step-by-step questions
   - Can switch from audio mode

4. **Profile System**
   - Fields: display_name, bio, interests, goals, looking_for, can_help_with, photo_url
   - Hashtag display (#tech #startups etc)
   - Photo display in profile view
   - `/reset` fully clears all profile fields

5. **AI Matching**
   - Vector similarity pre-filter (pgvector)
   - GPT-4o-mini for deep compatibility analysis
   - Scores: compatibility_score (0-1), match_type
   - AI explanation + icebreaker
   - Notifications to matched users

6. **Event System**
   - QR codes with deep links
   - Admin can create events and run matching
   - `current_event_id` tracks user's event

7. **Matches Display**
   - Pagination (◀️ ▶️)
   - Photo display, hashtags, AI explanation
   - Icebreaker suggestion, contact @username

### Known Issues / Gaps ❌

1. **No profile editing** - users can't update after onboarding
2. **No in-app messaging** - must leave bot to contact match
3. **No match actions** - can't say "met them" or "not interested"
4. **No event discovery** - only via QR codes
5. **Language not saved** - detected but not persisted
6. **Unused DB fields** - profession, skills, linkedin_data never populated

---

## Architecture

```
sphere-bot/
├── adapters/telegram/
│   ├── handlers/
│   │   ├── start.py           # /start, menu, profile, reset
│   │   ├── onboarding_audio.py # Voice onboarding + selfie + embeddings
│   │   ├── onboarding_v2.py    # Text onboarding flow
│   │   ├── matches.py          # Match display, pagination, notifications
│   │   └── events.py           # Event creation & joining
│   ├── keyboards/inline.py     # All keyboards (with lang support)
│   ├── states.py               # FSM states
│   └── loader.py               # Bot & services init (includes embedding_service)
├── core/
│   ├── domain/
│   │   ├── models.py           # User (with embeddings), Event, Match
│   │   └── constants.py        # INTERESTS, GOALS
│   ├── services/
│   │   ├── matching_service.py # Vector + LLM matching
│   │   └── event_service.py
│   └── prompts/
│       └── audio_onboarding.py # Extraction prompts
├── infrastructure/
│   ├── database/
│   │   ├── user_repository.py  # includes update_embeddings()
│   │   └── supabase_client.py
│   └── ai/
│       ├── openai_service.py   # GPT-4o-mini
│       ├── whisper_service.py  # Voice transcription
│       └── embedding_service.py # text-embedding-3-small
├── supabase/migrations/
│   ├── 002_enhanced_profiles.sql
│   └── 003_vector_embeddings.sql # pgvector + match_candidates()
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
current_event_id
-- Vector embeddings (1536 dims each)
profile_embedding, interests_embedding, expertise_embedding
-- Unused but available
profession, company, skills[], linkedin_url, linkedin_data, deep_profile
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
```

### messages (exists but unused)
```sql
id, match_id, sender_id, content, is_read, created_at
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

| Feature | Description | Time |
|---------|-------------|------|
| **Profile Editing** | Hybrid: manual fields + LLM conversational | 4h |
| **In-app Messaging** | Chat within bot, DB ready | 4h |
| **Match Actions** | Accept/Decline/Met buttons | 2h |
| **Auto-join Event** | After onboarding, auto-join pending event | 1h |

### 🟡 Phase 2: Quality

| Feature | Description | Time |
|---------|-------------|------|
| Match Feedback | "Was this match helpful?" buttons | 2h |
| Language Preference | Save during onboarding | 1h |
| Fix Fallback Language | Pass lang to analyze_match() | 30m |
| Follow-up Reminders | "Remind me to contact X" | 3h |

### 🟢 Phase 3: Growth

| Feature | Description | Time |
|---------|-------------|------|
| Event Discovery | Browse available events | 3h |
| Event Info System | Schedule, speakers for LLM context | 2h |
| Use All Embeddings | Update match_candidates() SQL | 2h |

### 📊 Phase 4: Organizers

| Feature | Description | Time |
|---------|-------------|------|
| Analytics Dashboard | Participant count, acceptance rate | 4h |
| Participant Profiles | View individual profiles | 2h |
| Export CSV | Participant list export | 2h |
| Per-event Settings | Adjust matching threshold | 2h |

---

## Profile Editing Design (TODO)

**Two modes:**
1. **Quick Edit** - Select field → Type new value → Confirm
2. **Conversational** - "Add crypto to my interests" → LLM interprets → Preview → Confirm

**Flow:**
```
👤 Profile → ✏️ Edit →
  ├── 📝 Edit field (bio/interests/goals/looking_for/can_help_with/photo)
  └── 💬 Describe changes (text or voice → LLM → preview → confirm)
```

**After edit:**
- Update DB
- Regenerate embeddings (background)
- Show updated profile

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
ONBOARDING_MODE=audio
```

---

## Recent Session Changes

1. **Vector Matching** - pgvector + LLM two-stage pipeline
2. **Background Embeddings** - asyncio.create_task (non-blocking)
3. **Embedding Timeout** - 15s timeout on API calls
4. **Error Handling** - Selfie handlers now always clear state
5. **Migration** - 003_vector_embeddings.sql executed
6. **Credentials** - Moved to `.credentials/keys.md`

---

## Quick Commands

```bash
# Deploy
git add -A && git commit -m "message" && git push

# Run migration
psql "postgresql://postgres:PASSWORD@db.cfppunyxxelqutfwqfbi.supabase.co:5432/postgres" -f supabase/migrations/XXX.sql

# Check syntax
python3 -m py_compile path/to/file.py
```
