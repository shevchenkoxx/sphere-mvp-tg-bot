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

---

## Current Status (January 2026)

### Working Features ✅

1. **Audio Onboarding**
   - LLM generates personalized intro
   - Voice transcription via Whisper
   - AI extracts: about, looking_for, can_help_with, interests, goals
   - Validation: asks follow-up if key info missing
   - "Add details" button to incrementally update profile

2. **Profile System**
   - Fields: display_name, bio, interests, goals, looking_for, can_help_with
   - Hashtag display (#tech #startups etc)
   - Structured view via 👤 Profile button

3. **AI Matching**
   - OpenAI GPT-4o-mini analyzes compatibility
   - Scores: compatibility_score (0-1), match_type (professional/creative/friendship/romantic)
   - AI explanation of why matched
   - Icebreaker suggestion
   - `/find_matches` command for manual trigger

4. **Event System**
   - QR codes with deep links
   - `current_event_id` tracks user's event
   - Participants visible in event

5. **Matches Display**
   - 💫 Matches button shows matches with pagination (◀️ ▶️)
   - Full profile with hashtags, looking_for, can_help_with
   - AI explanation prominently displayed ("Why this match")
   - Icebreaker suggestion, contact @username
   - Back to menu from all screens

### Bot Commands
```
/start - Start bot / main menu
/menu - Show main menu
/reset - Reset profile (admin/debug only)
/matches - View your matches
/find_matches - Trigger AI matching for current event
/help - Help info
```

### Main Menu Buttons
- 👤 Profile - View your profile
- 🎉 Events - Your events
- 💫 Matches - View and interact with matches

---

## Architecture

```
sphere-bot/
├── adapters/telegram/
│   ├── handlers/
│   │   ├── start.py           # /start, menu, profile callbacks
│   │   ├── onboarding_audio.py # Voice onboarding flow
│   │   ├── onboarding_v2.py    # Text onboarding flow
│   │   ├── matches.py          # Match display & interaction
│   │   └── events.py           # Event handlers
│   ├── keyboards/inline.py     # All inline keyboards
│   ├── states.py               # FSM states
│   └── loader.py               # Bot & services init
├── core/
│   ├── domain/models.py        # User, Event, Match models
│   ├── services/
│   │   ├── user_service.py
│   │   ├── event_service.py
│   │   └── matching_service.py # AI matching logic
│   └── prompts/
│       ├── audio_onboarding.py # Voice extraction prompts
│       └── templates.py        # Conversational prompts
├── infrastructure/
│   ├── database/               # Supabase repositories
│   └── ai/
│       ├── openai_service.py   # GPT-4o-mini (AsyncOpenAI)
│       └── whisper_service.py  # Voice transcription
├── config/
│   ├── settings.py             # Environment config
│   └── features.py             # Feature flags
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
- current_event_id - active event
- ai_summary - LLM-generated summary
- onboarding_completed

### events
- id, code, name, description, location
- is_active, settings

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
| `adapters/telegram/handlers/onboarding_audio.py` | Main onboarding flow |
| `adapters/telegram/handlers/matches.py` | Match display & pagination |
| `adapters/telegram/handlers/start.py` | Menu & profile display |
| `adapters/telegram/keyboards/inline.py` | All keyboards |
| `core/services/matching_service.py` | AI matching algorithm |
| `infrastructure/ai/openai_service.py` | GPT prompts (AsyncOpenAI!) |
| `core/prompts/audio_onboarding.py` | Extraction prompts |

---

## Common Tasks

### Add new keyboard button
1. Edit `adapters/telegram/keyboards/inline.py`
2. Add callback handler in appropriate handler file
3. Register callback_data pattern

### Modify AI prompts
1. Edit `core/prompts/audio_onboarding.py` for voice extraction
2. Edit `infrastructure/ai/openai_service.py` for matching analysis

### Test matching locally
```bash
python scripts/create_matches.py 44420077
```

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
```

---

## TODO / Next Steps

### Completed
- [x] Match pagination (next/prev buttons) - DONE
- [x] Back to menu from all screens - DONE
- [x] Better match explanations display - DONE
- [x] Fix: current_event_id not set on join_event - DONE
- [x] Improve extraction prompt for richer profiles - DONE

### High Priority
- [ ] **Selfie feature** - photo upload to find people at event
- [ ] LinkedIn URL parsing from voice/text
- [ ] Notifications when new match found

### Medium Priority
- [ ] Admin dashboard for events
- [ ] Multi-match chat forwarding
- [ ] Profile editing after onboarding
- [ ] Event-specific matching settings

### Future Ideas
- [ ] Group matching (find common groups)
- [ ] Follow-up reminders after event
- [ ] Event analytics for organizers

---

## Flow: When 5 Real People Register

1. **User scans QR** → opens `t.me/Matchd_bot?start=event_EVENTCODE`
2. **If new user:**
   - Starts audio onboarding
   - Records 60-sec voice message
   - LLM extracts: about, looking_for, can_help_with, skills, interests
   - Saves profile + sets `current_event_id`
3. **If existing user:**
   - Clicks "Join Event" button
   - Added to event_participants + `current_event_id` updated
4. **Matching triggers:**
   - Manual: user runs `/find_matches`
   - Auto: admin runs event matching
   - OpenAI analyzes all pairs → creates matches above threshold
5. **User sees matches:**
   - 💫 Matches button shows paginated list
   - AI explanation of why matched
   - Icebreaker to start conversation
   - Direct @username link

---

## Extraction Prompt (Improved)

Located in `core/prompts/audio_onboarding.py`

Now extracts:
- **about** - rich 3-4 sentence summary with personality
- **looking_for** - SPECIFIC people/connections wanted
- **can_help_with** - SPECIFIC expertise and skills
- **profession** - detailed job title (Senior PM, not just PM)
- **experience_level** - junior/mid/senior/founder
- **skills** - technical and soft skills
- **personality_traits** - how they come across
- **unique_value** - what makes them special to meet

Key improvements:
- Reads between the lines (infers from context)
- More generous extraction (better to include than miss)
- Captures personality and communication style
- Specific actionable info for matching
