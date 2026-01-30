# Changelog

All notable changes to Sphere Bot.

## [0.4.0] - 2026-01-30

### Added
- Railway deployment support (railway.json, Procfile, runtime.txt)
- Graceful error handling for bot conflicts (5 retries, clear messages)
- Support for both `SUPABASE_KEY` and `SUPABASE_SERVICE_KEY`

### Fixed
- TelegramConflictError no longer crashes - retries with backoff
- Missing env vars show clear error message instead of cryptic exception

## [0.3.0] - 2026-01-30

### Added
- **Audio Onboarding** - 60 sec voice message → structured profile
- Feature flags system (`config/features.py`)
- Prompt testing framework (`tests/prompts/`)
- Database migration 002 with enhanced profile fields
- PLAN.md with integration roadmap

### Database
- `current_event_id` - track user's current event
- `profession`, `company`, `skills` - professional info
- `looking_for`, `can_help_with` - networking goals
- `deep_profile` JSONB - LLM-generated analysis
- `audio_transcription` - voice message text
- `linkedin_url`, `linkedin_data` - social parsing prep

### Technical
- Modular AI provider design (easy to swap OpenAI → Anthropic)
- Serializable conversation state for FSM storage
- Factory pattern for conversation AI

## [0.2.0] - 2026-01-30

### Added
- **Conversational Onboarding v2** - LLM-driven multilingual chat
- Centralized AI prompts in `core/prompts/templates.py`
- `ONBOARDING_SYSTEM_PROMPT` with auto language detection
- `PROFILE_EXTRACTION_PROMPT` for structured data extraction

### Changed
- Onboarding simplified: Name → Interests → Goals → Bio
- More conversational, friendly tone

## [0.1.0] - 2026-01-30

### Added
- Initial project structure (clean architecture)
- Telegram bot with aiogram 3.x
- Supabase integration (PostgreSQL)
- User registration and onboarding (v1 - buttons)
- Event system with QR codes / deep links
- AI-powered matching (GPT-4o-mini)
- Voice transcription (Whisper)
- Match notifications

### Database
- Users table with platform support (Telegram/WhatsApp/Web ready)
- Events and event_participants tables
- Matches table with compatibility scores
- Messages table for future in-app chat

---

## Upcoming

### v0.5.0 (Next)
- [ ] Current event tracking in onboarding flow
- [ ] Top 3 matches display after onboarding
- [ ] Contact sharing (username/link)
- [ ] Icebreaker suggestions

### v0.6.0
- [ ] Deep profiling (second LLM pass)
- [ ] LinkedIn URL parsing
- [ ] Enhanced matching algorithm

### v1.0.0
- [ ] WhatsApp adapter
- [ ] REST API
- [ ] Admin dashboard
