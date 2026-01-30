# Sphere Bot 🌐

**AI-powered networking at events.** Scan QR → 60 sec voice intro → meet your top 3 matches.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/sphere-bot)

## How It Works

```
1. 📱 Scan QR code at event
2. 🎤 Record 60-sec voice intro about yourself
3. 🤖 AI extracts your profile & finds matches
4. 🎯 Get top 3 people to meet with reasons why
5. 💬 Connect via Telegram
```

## Features

- **Audio Onboarding** - Natural voice intro, no typing
- **Multilingual** - Auto-detects language (EN/RU/+)
- **AI Matching** - GPT-4o analyzes compatibility
- **Event Context** - Matches within your event
- **Deep Profiles** - LLM-generated personality insights

## Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/shevchenkoxx/sphere-mvp-tg-bot.git
cd sphere-mvp-tg-bot
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Setup Database
Run `supabase/schema.sql` in Supabase SQL Editor, then `supabase/migrations/002_enhanced_profiles.sql`

### 4. Run
```bash
python main.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather |
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_KEY` | Yes | Service role key |
| `OPENAI_API_KEY` | Yes | For GPT + Whisper |
| `ONBOARDING_MODE` | No | `audio` / `v2` / `v1` |
| `ADMIN_TELEGRAM_IDS` | No | Comma-separated admin IDs |

## Architecture

```
sphere-bot/
├── core/           # Business logic (platform-agnostic)
│   ├── domain/     # Models
│   ├── services/   # UserService, MatchingService
│   └── prompts/    # AI prompts (easy to modify!)
├── infrastructure/ # Supabase, OpenAI
├── adapters/       # Telegram (WhatsApp ready)
└── config/         # Settings, feature flags
```

## Onboarding Modes

| Mode | Description | Best For |
|------|-------------|----------|
| `audio` | 60 sec voice message | Natural, fast |
| `v2` | LLM conversation | Flexible, multilingual |
| `v1` | Button selection | Predictable, simple |

Set via `ONBOARDING_MODE` env var.

## Roadmap

- [x] Audio onboarding
- [x] AI matching
- [x] Railway deploy
- [ ] Top 3 matches display
- [ ] LinkedIn parsing
- [ ] Deep profiling
- [ ] WhatsApp adapter
- [ ] Admin dashboard

## Tech Stack

- **Bot**: aiogram 3.x (Python)
- **Database**: Supabase (PostgreSQL)
- **AI**: OpenAI GPT-4o-mini + Whisper
- **Deploy**: Railway

## License

MIT

---

Built with ❤️ for meaningful connections.
