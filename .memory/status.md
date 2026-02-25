# Current Status

Branch: `global-mode-v1`
Bot: @Matchd_bot
Deploy: Railway (auto-deploy from `global-mode-v1` / service `humorous-enchantment`)
Last session: 2026-02-24

## What Works
- Global mode onboarding (agent-driven, no events required)
- Profile creation + editing
- Global matching (vector + LLM re-ranking)
- Sphere City (city-based matching)
- Profile expansion flow (no matches -> ask more -> rematch)
- Agent chat (post-onboarding AI conversation)
- Vibe Check (AI compatibility game)
- Share/referral system
- Admin dashboard (`/stats` web UI)
- Events system (just enabled: `EVENTS_ENABLED=true`)
- `/quickevent` command (create event + QR in one step)
- QR code generation (programmatic via `core/utils/qr_generator.py`)

## What's Broken / WIP
- Event onboarding ordering bug: `join_event()` called AFTER event-scoped matching check in `onboarding_agent.py:662-687` — event matches won't trigger on first join
- QR font falls back to tiny bitmap on Linux (Railway) — works fine on macOS

## Active Events
- `CORAD` — created 2026-02-24, active, deep link: `t.me/Matchd_bot?start=event_CORAD`
- `SXN`, `POSTSW24`, `TEST2024` — legacy events from main branch

## Environment (Railway)
- `ONBOARDING_MODE=agent`
- `EVENTS_ENABLED=true` (changed from false, 2026-02-24)
- `TELEGRAM_BOT_TOKEN=8551957014:AAF7...` (@Matchd_bot)
- `DEBUG=true`
