# Sphere Bot - Claude Code Instructions

## Project Overview
Telegram bot for meaningful connections at events. Users scan QR code → onboard via AI conversation → get AI-matched with other participants.

## Key Concept: Conversational Onboarding (v2)
Instead of scripted questions with buttons, we use LLM-driven conversation:
- **Multilingual**: Auto-detects user language, responds in same language
- **Natural flow**: LLM asks questions one at a time, acknowledges answers
- **Data extraction**: After conversation, extract structured data with separate prompt
- **Marker-based**: `PROFILE_COMPLETE` marker signals successful onboarding
- **Modular**: Easy to swap LLM providers (OpenAI → Anthropic, local models)

### Switching Onboarding Versions
In `adapters/telegram/handlers/__init__.py`:
```python
ONBOARDING_VERSION = "v2"  # "v1" = buttons, "v2" = LLM conversation
```

### Key Components
- `core/interfaces/conversation.py` - Abstract interfaces
- `core/services/conversation_service.py` - Orchestration logic
- `infrastructure/ai/conversation_ai.py` - OpenAI implementation
- `adapters/telegram/handlers/onboarding_v2.py` - Telegram handler
- `core/prompts/templates.py` - Prompts (ONBOARDING_SYSTEM_PROMPT)

## Architecture

```
sphere-bot/
├── core/                    # Business logic (platform-agnostic)
│   ├── domain/              # Models, constants
│   ├── interfaces/          # Abstract repositories
│   ├── services/            # Business services
│   └── prompts/             # AI prompt templates
├── infrastructure/          # External services
│   ├── database/            # Supabase repositories
│   └── ai/                  # OpenAI services
├── adapters/                # Platform adapters
│   └── telegram/            # Telegram bot
│       ├── handlers/        # Message handlers
│       └── keyboards/       # Inline keyboards
└── config/                  # Settings
```

## Key Files

### Prompts (easy to modify)
- `core/prompts/templates.py` - All AI prompts in Russian

### Onboarding Flow
- `adapters/telegram/handlers/onboarding.py` - 4-step flow
- `adapters/telegram/keyboards/inline.py` - Selection keyboards

### Business Logic
- `core/services/matching_service.py` - AI matching algorithm
- `core/services/user_service.py` - User management

### Database
- `supabase/schema.sql` - PostgreSQL schema
- `infrastructure/database/user_repository.py` - User CRUD

## Commands

```bash
# Run bot
cd sphere-bot && python main.py

# Check logs
tail -f logs/*.log

# Apply DB schema
# Copy supabase/schema.sql to Supabase SQL Editor
```

## Environment Variables

```env
TELEGRAM_BOT_TOKEN=xxx
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=xxx
OPENAI_API_KEY=sk-xxx
ADMIN_TELEGRAM_IDS=44420077
```

## Coding Guidelines

1. **Russian UI**: All user-facing text in Russian
2. **Short messages**: Telegram messages should be concise
3. **Emoji usage**: Use sparingly, for visual structure
4. **Error handling**: Always show friendly error messages
5. **Platform abstraction**: Use `MessagePlatform` enum for future WhatsApp/Web

## Adding New Features

### New Interest/Goal
Edit `core/domain/constants.py`:
```python
INTERESTS = {
    "new_key": {"label_ru": "Новый интерес", "category": "category"},
    ...
}
```

### New AI Prompt
Edit `core/prompts/templates.py`:
```python
NEW_PROMPT = """Your prompt here with {placeholders}..."""
```

### New Handler
Create in `adapters/telegram/handlers/`:
```python
from aiogram import Router
router = Router()

@router.message(SomeFilter())
async def handler(message: Message):
    ...
```
Register in `adapters/telegram/handlers/__init__.py`.

## Database Schema

### Users
- `platform` + `platform_user_id` = unique identifier
- `interests`, `goals` = JSONB arrays
- `ai_summary` = AI-generated profile summary

### Events
- `code` = unique QR code identifier
- `created_by` = admin user ID

### Matches
- `compatibility_score` = 0.0-1.0
- `match_type` = friendship/professional/romantic/creative

## Testing Locally

1. Create test event in Supabase
2. Generate deep link: `https://t.me/BOT_USERNAME?start=event_CODE`
3. Test onboarding flow
4. Check matches in database

## Common Issues

### Bot not responding
- Check if another instance is running
- Regenerate token in BotFather if needed

### Database errors
- Verify schema is applied
- Check Supabase service key permissions

### AI errors
- Check OpenAI API key and credits
- Review prompt format in templates.py
