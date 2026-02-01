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

### Deploy
- **ALWAYS push to git** for Railway deployment
- Railway auto-deploys from `main` branch
- After `git push` wait ~1-2 min for deploy

### Database (Supabase)
- Manage via REST API (credentials in `.env`)
- URL: `https://cfppunyxxelqutfwqfbi.supabase.co`
- Use `SUPABASE_SERVICE_KEY` for full access

### Testing
- Test event: `TEST2024` (10 test profiles with looking_for/can_help_with)
- Deep link: `t.me/Matchd_bot?start=event_TEST2024`
- Reset profile: `/reset` in bot (needs DEBUG=true or admin)
- Find matches: `/find_matches` - manually trigger AI matching

### Language
- **English is default** - all prompts and messages
- Russian supported via auto-detect from Telegram settings
- User's language detected from `message.from_user.language_code`
- **ALL buttons and keyboards support lang parameter**

---

## Current Status (February 2026)

### Working Features ✅

1. **Vector-Based Matching (NEW)**
   - Two-stage pipeline: pgvector similarity + LLM re-ranking
   - 70% fewer API calls (~350 vs 1,225 for 50 users)
   - OpenAI text-embedding-3-small (1536 dimensions)
   - Auto-fallback to base score if embeddings unavailable
   - Embeddings generated after onboarding completion

2. **Audio Onboarding**
   - LLM generates personalized intro
   - Voice transcription via Whisper (run_in_executor for non-blocking)
   - AI extracts: about, looking_for, can_help_with, interests, goals, skills
   - Validation: asks follow-up if key info missing
   - "Add details" button to incrementally update profile
   - **Selfie request** after profile - explains it helps matches find you
   - Switch to text mode available

2. **Text Onboarding (v2)**
   - Conversational flow with LLM
   - Step-by-step questions
   - Can switch from audio mode
   - Both routers registered when audio mode enabled

3. **Profile System**
   - Fields: display_name, bio, interests, goals, looking_for, can_help_with, photo_url
   - Hashtag display (#tech #startups etc)
   - Photo display in profile view
   - Structured view via 👤 Profile button
   - `/reset` fully clears all profile fields

5. **AI Matching**
   - **Vector similarity pre-filter** (pgvector) for fast candidate selection
   - OpenAI GPT-4o-mini (AsyncOpenAI!) for deep compatibility analysis
   - Scores: compatibility_score (0-1), match_type (professional/creative/friendship/romantic)
   - AI explanation of why matched
   - Icebreaker suggestion
   - `/find_matches` command for manual trigger
   - **Notifications** sent to existing users when new match found

6. **Event System**
   - QR codes with deep links
   - `current_event_id` tracks user's event (set on join)
   - Participants visible in event
   - Admin can create events and run matching

7. **Matches Display**
   - 💫 Matches button shows matches with pagination (◀️ ▶️)
   - **Photo display** of match partner
   - Full profile with hashtags, looking_for, can_help_with
   - AI explanation prominently displayed ("Why this match")
   - Icebreaker suggestion, contact @username
   - Back to menu from all screens

### Bot Commands
```
/start - Start bot / main menu
/menu - Show main menu
/reset - Full profile reset (admin/debug only)
/matches - View your matches
/find_matches - Trigger AI matching for current event
/help - Help info
```

### Main Menu Buttons
- 👤 Profile - View your profile (with photo)
- 🎉 Events - Your events
- 💫 Matches - View and interact with matches

---

## Architecture

```
sphere-bot/
├── adapters/telegram/
│   ├── handlers/
│   │   ├── start.py           # /start, menu, profile, reset
│   │   ├── onboarding_audio.py # Voice onboarding + selfie
│   │   ├── onboarding_v2.py    # Text onboarding flow
│   │   ├── matches.py          # Match display, pagination, notifications
│   │   └── events.py           # Event creation & joining
│   ├── keyboards/inline.py     # All keyboards (with lang support!)
│   ├── states.py               # FSM states
│   ├── config.py               # ONBOARDING_VERSION
│   └── loader.py               # Bot & services init
├── core/
│   ├── domain/
│   │   ├── models.py           # User, Event, Match, MatchResultWithId
│   │   └── constants.py        # INTERESTS, GOALS, get_goal_display
│   ├── services/
│   │   ├── user_service.py
│   │   ├── event_service.py    # join_event sets current_event_id
│   │   └── matching_service.py # AI matching, returns MatchResultWithId
│   └── prompts/
│       ├── audio_onboarding.py # Rich extraction prompts
│       └── templates.py        # Conversational prompts
├── infrastructure/
│   ├── database/               # Supabase repositories
│   └── ai/
│       ├── openai_service.py   # GPT-4o-mini (AsyncOpenAI!)
│       ├── whisper_service.py  # Voice transcription (run_in_executor)
│       └── embedding_service.py # Vector embeddings (text-embedding-3-small)
├── config/
│   ├── settings.py             # Environment config
│   └── features.py             # ONBOARDING_MODE, feature flags
└── scripts/
    └── create_matches.py       # Manual matching script
```

---

## Database Schema

### users
- id, platform, platform_user_id, username, first_name, display_name
- interests[], goals[], bio
- **looking_for** - what connections they want
- **can_help_with** - their expertise
- **photo_url** - selfie file_id for display
- current_event_id - active event
- ai_summary - LLM-generated summary
- onboarding_completed
- **profile_embedding** - vector(1536) for similarity search
- **interests_embedding** - vector(1536) for interest matching
- **expertise_embedding** - vector(1536) for expertise matching

### events
- id, code, name, description, location
- is_active, settings
- **(TODO: event_info - detailed info for LLM)**

### event_participants
- event_id, user_id, joined_at

### matches
- event_id, user_a_id, user_b_id
- compatibility_score, match_type
- ai_explanation, icebreaker
- status (pending/accepted/declined)

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `adapters/telegram/handlers/onboarding_audio.py` | Main onboarding + selfie flow + embeddings |
| `adapters/telegram/handlers/matches.py` | Match display, pagination, photo, notifications |
| `adapters/telegram/handlers/start.py` | Menu, profile with photo, /reset |
| `adapters/telegram/keyboards/inline.py` | All keyboards with lang support |
| `adapters/telegram/handlers/__init__.py` | Router registration (audio + v2) |
| `core/services/matching_service.py` | AI matching, vector search, MatchResultWithId |
| `core/services/event_service.py` | join_event sets current_event_id |
| `infrastructure/ai/openai_service.py` | GPT prompts (AsyncOpenAI!) |
| `infrastructure/ai/embedding_service.py` | Vector embedding generation (text-embedding-3-small) |
| `core/prompts/audio_onboarding.py` | Rich extraction prompts |
| `supabase/migrations/003_vector_embeddings.sql` | pgvector setup + match_candidates function |

---

## Recent Changes (This Session)

1. **Vector Matching Implementation** - Two-stage matching for scalability
   - Created `supabase/migrations/003_vector_embeddings.sql` with pgvector setup
   - Added `infrastructure/ai/embedding_service.py` for embedding generation
   - Added embedding fields to User model (profile, interests, expertise)
   - Updated `user_repository.py` with `update_embeddings()` method
   - Added `find_vector_candidates()` and `find_matches_vector()` to matching_service
   - Integrated embeddings into both audio and text onboarding flows
   - `/find_matches` now uses vector matching when embeddings available

2. **Match pagination** - ◀️ ▶️ buttons to scroll through matches
2. **Back to menu** - all screens have ← Menu button
3. **Fix current_event_id** - now set when existing user joins event
4. **Rich extraction prompt** - extracts skills, personality, experience level
5. **Text onboarding fix** - v2 router now included when audio mode enabled
6. **Match notifications** - existing users notified when new person matches
7. **Selfie feature** - photo request after onboarding with explanation
8. **Full /reset** - clears ALL profile fields (bio, interests, goals, etc.)
9. **Photo display** - shown in profile, matches, and match profile view
10. **Multilingual buttons** - all keyboards support lang parameter
11. **Fix goals language** - uses get_goal_display(g, lang)
12. **Fix text onboarding state** - better state handling after switch from audio
13. **Bug fixes batch** - multiple fixes from code review:
    - Silent failures now show error messages (matches.py)
    - Photo send failures logged for debugging
    - Infinite loop fix - message recorded BEFORE LLM call
    - FSM state fully cleared on error recovery
    - Fallback profile has valid looking_for/can_help_with defaults
    - Improved matching prompt with weighted criteria
14. **Language detection fixes** - all commands and callbacks use proper language:
    - /menu, /help, /reset detect and use user's language
    - back_to_menu, show_events callbacks fixed
    - Added detect_lang_callback() for callback handlers
15. **Reset command fixed** - now properly clears ALL profile fields in DB
    - Added reset_user() method with proper NULL handling
    - Added reset_profile() to repository
16. **Selfie request for text onboarding** - v2 now asks for photo too
    - Added waiting_selfie state
    - Photo upload, skip button, text fallback handlers
17. **Profile fields separation** - looking_for and can_help_with saved separately
    - Fixed _build_bio_from_extracted() merging all fields into bio
    - Now correctly saves each field to its own DB column
18. **Profile UI redesign** - clean card-style layout
    - Name • @username header
    - Bio as main description
    - Hashtags for interests
    - Visual divider line
    - Looking for / Can help with sections
    - Goals at bottom
    - Consistent style across profile, matches, and match details

---

## TODO / Next Steps

### Completed ✅
- [x] **Vector-based matching** - pgvector + LLM re-ranking (70% API cost reduction)
- [x] Match pagination (next/prev buttons)
- [x] Back to menu from all screens
- [x] Better match explanations display
- [x] Fix: current_event_id not set on join_event
- [x] Improve extraction prompt for richer profiles
- [x] Fix: text onboarding after switch from audio
- [x] Notifications when new match found
- [x] Selfie feature - photo upload after onboarding
- [x] Full /reset command - clears all profile fields
- [x] Fix goals display language
- [x] Show photo in profiles and matches
- [x] All buttons support multilingual (en/ru)

### High Priority
- [ ] **Event info system** - upload event details (schedule, speakers, etc.) for LLM to answer questions
- [ ] **Language preference storage** - add `language_preference` field to User model, save during onboarding
- [ ] LinkedIn URL parsing from voice/text
- [ ] Edit profile button (change photo, update info)

### Medium Priority
- [ ] Admin dashboard for events
- [ ] Event-specific matching settings
- [ ] Profile editing after onboarding

### Future Ideas
- [ ] Group matching (find common groups)
- [ ] Follow-up reminders after event
- [ ] Event analytics for organizers
- [ ] AI event assistant (answer questions about event)

---

## Flow: When Users Register

1. **User scans QR** → opens `t.me/Matchd_bot?start=event_EVENTCODE`
2. **If new user:**
   - Starts audio onboarding (or switch to text)
   - Records 60-sec voice message
   - LLM extracts: about, looking_for, can_help_with, skills, interests
   - **Asks for selfie** - explains it helps matches find you
   - Saves profile + sets `current_event_id`
   - Joins event automatically
3. **If existing user:**
   - Clicks "Join Event" button
   - Added to event_participants
   - `current_event_id` updated
4. **Matching triggers:**
   - Manual: user runs `/find_matches`
   - Auto: admin runs event matching
   - **Two-stage matching**: Vector similarity (pgvector) → LLM analysis (top candidates only)
   - ~70% fewer API calls compared to O(n²) approach
   - **Existing users notified** about new matches
5. **User sees matches:**
   - 💫 Matches button shows paginated list with photos
   - AI explanation of why matched
   - Icebreaker to start conversation
   - Direct @username link

---

## Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=xxx
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx  # or SUPABASE_SERVICE_KEY
OPENAI_API_KEY=sk-xxx

# Optional
ADMIN_TELEGRAM_IDS=123,456
DEBUG=true
DEFAULT_MATCH_THRESHOLD=0.6
ONBOARDING_MODE=audio  # audio, v2, v1
```

---

## Critical Implementation Notes

### AsyncOpenAI
```python
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key=settings.openai_api_key)
response = await client.chat.completions.create(...)
```

### Whisper (non-blocking)
```python
loop = asyncio.get_event_loop()
return await loop.run_in_executor(None, self._transcribe_sync, ...)
```

### Router Registration (handlers/__init__.py)
```python
if ONBOARDING_VERSION == "audio":
    # Include BOTH routers - users can switch to text
    onboarding_routers = [onboarding_audio.router, onboarding_v2.router]
```

### MatchResultWithId
```python
class MatchResultWithId(MatchResult):
    match_id: UUID  # For notifications
```

### Vector Matching Architecture
```python
# Two-stage pipeline for scalable matching
# Stage 1: Vector similarity (pgvector) - fast, cheap
candidates = await matching_service.find_vector_candidates(user, event_id, limit=10)

# Stage 2: LLM re-ranking - deep analysis of top candidates
for candidate, vector_score in candidates:
    result = await self.analyze_pair(user, candidate, event_name)
```

### Embedding Generation
```python
from infrastructure.ai.embedding_service import EmbeddingService
embedding_service = EmbeddingService()
profile_emb, interests_emb, expertise_emb = await embedding_service.generate_embeddings(user)
```

### Database Migration (pgvector)
Run `supabase/migrations/003_vector_embeddings.sql` in Supabase SQL Editor:
1. Enable pgvector extension
2. Add embedding columns to users table
3. Create IVFFlat indexes for fast similarity search
4. Create `match_candidates()` function for vector search
