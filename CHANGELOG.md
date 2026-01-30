# Changelog

All notable changes to Sphere Bot will be documented in this file.

## [0.3.0] - 2025-01-30

### Added
- **Conversational Onboarding v2** - LLM-driven natural conversation
- Multilingual support (auto-detects user language)
- `core/interfaces/conversation.py` - Abstract conversation interfaces
- `core/services/conversation_service.py` - Conversation orchestration
- `infrastructure/ai/conversation_ai.py` - OpenAI conversation implementation
- `adapters/telegram/handlers/onboarding_v2.py` - New conversational handler
- Profile extraction from conversation with separate LLM call
- `ONBOARDING_VERSION` config to switch between v1/v2

### Technical
- Modular AI provider design (easy to swap OpenAI → Anthropic)
- Serializable conversation state for FSM storage
- Factory pattern for conversation AI instantiation

## [0.2.0] - 2025-01-30

### Added
- Centralized AI prompts in `core/prompts/templates.py`
- Fast onboarding flow (60 seconds target)
- Voice message support for bio (Whisper transcription)
- Emoji-based interest/goal selection keyboards
- Skip option for optional fields

### Changed
- Simplified onboarding: Name → Interests → Goals → Bio (removed city step)
- More conversational, friendly tone in all messages
- Compact button layouts for better mobile UX

### Technical
- Clean architecture: core → infrastructure → adapters
- Platform abstraction for future WhatsApp/Web support
- Repository pattern for data access

## [0.1.0] - 2025-01-30

### Added
- Initial project structure
- Telegram bot with aiogram 3.x
- Supabase integration (PostgreSQL)
- User registration and onboarding
- Event system with QR codes
- AI-powered matching (OpenAI GPT-4o-mini)
- Basic match notifications

### Database
- Users table with platform support
- Events and event_participants tables
- Matches table with compatibility scores
- Messages table for future in-app chat

---

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for planned features.
