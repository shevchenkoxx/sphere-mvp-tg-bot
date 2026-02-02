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

5. **Profile Editing** (NEW)
   - Two modes: Quick Edit + Conversational (LLM)
   - Quick Edit: Select field → Type/voice value → Preview → Confirm
   - Conversational: "Add crypto to interests" → LLM interprets → Preview → Confirm
   - Supports text and voice input
   - Auto-regenerates embeddings after changes
   - FSM states: ProfileEditStates in states/onboarding.py

6. **AI Matching**
   - Vector similarity pre-filter (pgvector)
   - GPT-4o-mini for deep compatibility analysis
   - Scores: compatibility_score (0-1), match_type
   - AI explanation + icebreaker
   - Notifications to matched users

7. **Event System**
   - QR codes with deep links
   - Admin can create events and run matching
   - `current_event_id` tracks user's event

8. **Matches Display**
   - Pagination (◀️ ▶️)
   - Photo display, hashtags, AI explanation
   - Icebreaker suggestion, contact @username

9. **Sphere City** (NEW)
   - City-based matching outside events
   - City picker: Moscow, Kyiv, Dubai, Berlin, London, NYC, Tbilisi, Yerevan, + custom
   - Matches menu with Event + Sphere City options
   - City detection from voice + manual selection

10. **Enhanced Extraction** (NEW)
    - Chain-of-thought prompting for better analysis
    - Now extracts: profession, company, skills, location, experience_level
    - `/test_extract` command for debugging (admin-only)

### Known Issues / Gaps ❌

1. **No in-app messaging** - must leave bot to contact match
2. **No match actions** - can't say "met them" or "not interested"
3. **No event discovery** - only via QR codes
4. **Language not saved** - detected but not persisted
5. **LinkedIn integration** - linkedin_url, linkedin_data fields unused

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
│   │   └── supabase_client.py
│   └── ai/
│       ├── openai_service.py   # GPT-4o-mini + profession/skills in matching
│       ├── whisper_service.py  # Voice transcription
│       └── embedding_service.py # text-embedding-3-small
├── scripts/
│   └── test_extraction.py      # CLI for testing extraction prompts
├── supabase/migrations/
│   ├── 002_enhanced_profiles.sql
│   ├── 003_vector_embeddings.sql # pgvector + match_candidates()
│   └── 004_sphere_city.sql     # experience_level, city on matches
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

## Quick Commands

```bash
# Deploy
git add -A && git commit -m "message" && git push

# Run migration
psql "postgresql://postgres:PASSWORD@db.cfppunyxxelqutfwqfbi.supabase.co:5432/postgres" -f supabase/migrations/XXX.sql

# Check syntax
python3 -m py_compile path/to/file.py
```
