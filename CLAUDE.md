# Sphere Bot - Project Documentation

## Overview
Telegram bot for meaningful connections at events. Users scan QR → quick voice onboarding → AI matching → meet top 3 people.

**Bot:** @Matchd_bot
**Repo:** https://github.com/shevchenkoxx/sphere-mvp-tg-bot
**Deploy:** Railway (auto-deploy from main branch)

---

## What's Done ✅

### Core Features
- **Audio Onboarding** (60 sec) - user records voice, AI extracts structured profile
- **Conversational Onboarding** (v2) - LLM-driven multilingual chat
- **Button Onboarding** (v1) - classic flow with inline keyboards
- **Event System** - QR codes, deep links, participant tracking
- **AI Matching** - GPT-4o-mini analyzes compatibility
- **Voice Transcription** - Whisper API

### Architecture
```
sphere-bot/
├── core/                    # Business logic (platform-agnostic)
│   ├── domain/              # Models, constants
│   ├── interfaces/          # Abstract repositories & services
│   ├── services/            # UserService, EventService, MatchingService
│   └── prompts/             # All AI prompts (easy to modify)
├── infrastructure/          # External services
│   ├── database/            # Supabase repositories
│   └── ai/                  # OpenAI, Whisper, ConversationAI
├── adapters/                # Platform adapters
│   └── telegram/            # Bot handlers, keyboards
├── config/                  # Settings, feature flags
├── tests/prompts/           # Prompt testing framework
└── supabase/                # SQL schema & migrations
```

### Database (Supabase)
Tables: `users`, `events`, `event_participants`, `matches`, `messages`

New columns (migration 002):
- `current_event_id` - tracks which event user is at
- `profession`, `company`, `skills` - professional info
- `looking_for`, `can_help_with` - networking goals
- `deep_profile` (JSONB) - LLM-generated analysis
- `audio_transcription` - voice message text
- `linkedin_url`, `linkedin_data` - social parsing

### Feature Flags
```bash
ONBOARDING_MODE=audio    # v1, v2, audio
MATCHING_ENABLED=true
AUTO_MATCH_ON_JOIN=true
SHOW_TOP_MATCHES=3
DEEP_PROFILE_ENABLED=true
DEBUG=false
```

### Deployment
- **Railway** - auto-deploy from GitHub
- **Graceful error handling** - retries on conflicts, clear error messages
- Supports both `SUPABASE_KEY` and `SUPABASE_SERVICE_KEY`

---

## In Progress 🔄

### Current Event Tracking
When user joins via QR link (`t.me/bot?start=event_CODE`):
1. Extract event_code from deep link
2. Save to `current_event_id` on profile completion
3. Use for matching context

### Top 3 Matches Display
After onboarding, show:
```
🎯 Meet these people at [Event]:

1️⃣ Anna - Product Designer
   💡 You both love AI, she needs a technical co-founder
   📱 @anna_design

2️⃣ Mike - ML Engineer
   💡 He's looking to join a startup, you're hiring
   📱 @mike_ml
```

---

## Planned 📋

### Phase 1: Enhanced Matching
- [ ] Multi-factor scoring (interests + goals + skills + AI)
- [ ] Show top 3 matches immediately after onboarding
- [ ] Include contact info (username/link)
- [ ] Icebreaker suggestions

### Phase 2: Deep Profiling
- [ ] Second LLM pass for personality analysis
- [ ] Ideal match profile generation
- [ ] Conversation starters based on shared interests
- [ ] Confidence scoring

### Phase 3: LinkedIn/Social Parsing
- [ ] Accept LinkedIn URL during onboarding
- [ ] Fetch public profile data (Proxycurl API)
- [ ] Enrich profile with skills, experience
- [ ] Parse other socials (Twitter, GitHub)

### Phase 4: Multi-Platform
- [ ] WhatsApp adapter
- [ ] REST API for PWA
- [ ] Admin dashboard (event creation, QR codes)

---

## Quick Commands

```bash
# Run locally
cd sphere-bot && python3 main.py

# Test prompts
python3 tests/prompts/runner.py

# Apply DB migration
# Copy supabase/migrations/002_enhanced_profiles.sql to Supabase SQL Editor
```

## Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=xxx
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx  # or SUPABASE_SERVICE_KEY
OPENAI_API_KEY=sk-xxx

# Optional
ADMIN_TELEGRAM_IDS=123,456
ONBOARDING_MODE=audio
DEBUG=false
```

## Key Files

| File | Purpose |
|------|---------|
| `config/features.py` | Feature flags (on/off toggles) |
| `core/prompts/templates.py` | Conversational prompts |
| `core/prompts/audio_onboarding.py` | Voice extraction prompts |
| `adapters/telegram/config.py` | Telegram-specific config |
| `main.py` | Entry point with error handling |
