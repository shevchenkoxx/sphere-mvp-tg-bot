# Multi-Platform Research Report: Maximum Coverage, Minimum Implementation

## TL;DR Recommendation

**Priority order: WhatsApp > Messenger+Instagram > iMessage (skip)**

| Platform | Users (global) | Implementation Effort | Coverage Value | Recommendation |
|----------|---------------|----------------------|----------------|----------------|
| WhatsApp | 2.9B | 3-4 weeks (full), 3-5 days (MVP) | Highest | Do first |
| Messenger + Instagram | 1B + 2B | 2-3 weeks (shares Meta infra with WA) | High | Do second (2-for-1 deal) |
| iMessage | 1.8B | Months, $99/yr Apple dev + enterprise approval | Low ROI | Skip |

**Total coverage: ~5.8B users across 3 platforms + Telegram**

---

## Platform Details

### 1. WhatsApp (Best ROI)

- **API:** WhatsApp Cloud API (hosted by Meta, on-prem sunsetted Oct 2025)
- **Cost:** FREE for service messages (user-initiated, 24h window). Paid templates only for outbound after 24h (~$0.01-0.05/msg by country)
- **Python lib:** PyWa (`pip install pywa`) — async, FastAPI integration, decorator-based handlers (similar to aiogram)
- **Voice messages:** OGG/Opus — same format as Telegram. Whisper pipeline works with zero changes
- **Key limitation:** Max 3 reply buttons per message (vs unlimited in Telegram). Must redesign menus as list messages (up to 10 items)
- **No message editing** — can't do the current edit-in-place pagination pattern
- **Setup:** Meta Business verification (1-14 days), dedicated phone number
- **Webhook only** — needs HTTPS endpoint (Railway provides this)

**Quick Win (3-5 days):** Voice onboarding only — user sends voice, bot transcribes, creates profile, sends matches as plain text. No buttons needed.

### 2. Facebook Messenger + Instagram DMs (2-for-1)

- **Same Meta infra** — same webhook, same JSON format, same app. Instagram just has `"object": "instagram"` instead of `"object": "page"`
- **Cost:** FREE (no per-message charges for Messenger)
- **Python lib:** None worth using (all abandoned, sync-only). Write thin async wrapper with httpx (~200 lines)
- **Voice messages:** Receive as audio attachment URL (MP3/M4A from Meta CDN, may need format conversion for Whisper)
- **Key advantages:** Quick Replies (up to 13 options — better than WhatsApp's 3), Carousels (up to 10 cards — natural for match browsing), Persistent Menu
- **Key limitation:** 24h messaging window (same as WhatsApp), App Review takes 2-4 weeks
- **Carousels** are actually better than Telegram for match cards — native swipe through match profiles

**Instagram bonus:** Same webhook, same code, different object field. Essentially free if you build Messenger.

### 3. iMessage (Not Recommended)

- Apple Messages for Business — requires $99/yr developer account + enterprise-level approval
- No direct API — must go through Apple Business Register + Message Service Provider (Sinch, Zendesk, etc.)
- Not designed for bots — designed for customer service with live agents
- No voice message support via the API
- **Verdict:** Not viable for a small startup. Would cost months of effort and approval time.

---

## Architecture Recommendation

Your codebase is already ~70% platform-agnostic (good news):

| Layer | Platform-Agnostic? | Notes |
|-------|-------------------|-------|
| `core/services/` | Yes | Matching, events, user logic |
| `core/domain/` | Yes | Models already have `MessagePlatform.WHATSAPP` |
| `infrastructure/ai/` | Yes | OpenAI, Whisper, embeddings |
| `infrastructure/database/` | Yes | Supabase repos |
| `adapters/telegram/handlers/` | No | aiogram-specific |
| `adapters/telegram/keyboards/` | No | Telegram InlineKeyboard |
| `adapters/telegram/states/` | No | aiogram FSM |

**Key principle:** DO NOT try to unify handlers across platforms. The UX paradigms are too different (Telegram inline keyboards vs WhatsApp 3-button limit vs Messenger carousels). Instead:

```
adapters/
├── telegram/          # Existing, unchanged
├── whatsapp/          # New - PyWa handlers
│   ├── handlers/
│   ├── keyboards/     # WhatsApp interactive messages
│   ├── webhook.py     # FastAPI endpoint
│   └── loader.py
├── messenger/         # New - httpx wrapper
│   ├── handlers/
│   ├── keyboards.py   # Quick replies, carousels
│   ├── webhook.py     # aiohttp/FastAPI endpoint
│   └── loader.py
core/                  # UNCHANGED - already shared
infrastructure/        # UNCHANGED - already shared
```

**State management fix:** Current `MemoryStorage()` loses state on Railway deploy (Known Issue #6). For multi-platform, move to database-backed state (Supabase `conversation_states` table) or Redis (aiogram has built-in `RedisStorage`). This fixes both platforms at once.

---

## Implementation Roadmap

### Phase 1: WhatsApp MVP (1 week)

1. Meta Business Account + phone number + verification
2. FastAPI webhook alongside existing aiogram polling
3. Voice onboarding: receive OGG → Whisper → extract profile → text reply
4. Simple text-based match display (no buttons needed for MVP)
5. Event deep links: `wa.me/PHONE?text=event_CODE`

### Phase 2: WhatsApp Full (2 more weeks)

1. WhatsApp list messages for menus (city picker, match navigation)
2. Reply buttons for confirmations (max 3)
3. Photo support for profile pics
4. Template messages for match notifications (after 24h window)
5. DB-backed state management

### Phase 3: Messenger + Instagram (2 weeks)

1. Meta App dashboard — add Messenger + Instagram products
2. Shared webhook endpoint (route by object field)
3. Carousel for match cards (potentially better UX than Telegram!)
4. Quick Replies for menus (up to 13 options)
5. App Review submission (2-4 week wait)

**Total: ~5-6 weeks for all 3 new platforms (WhatsApp + Messenger + Instagram)**

---

## Cost Summary

| Platform | Setup Cost | Per-Message | Monthly Estimate (100 users) |
|----------|-----------|-------------|------------------------------|
| Telegram | Free | Free | $0 |
| WhatsApp | Free (Cloud API) | Free (user-initiated) | $0-5 (templates only) |
| Messenger | Free | Free | $0 |
| Instagram | Free | Free | $0 |
| **Total** | **Free** | **Mostly free** | **~$0-5** |

---

## Bottom Line

**Start with WhatsApp.** It's the highest-value platform, has the best Python library (PyWa), voice messages work identically to Telegram, and your architecture already supports it (`MessagePlatform.WHATSAPP` exists). A working MVP in 3-5 days, full parity in 3-4 weeks.

**Then add Messenger + Instagram** as a 2-for-1 deal using the same Meta infrastructure. Carousels actually improve match browsing UX.

**Skip iMessage entirely** — enterprise-only, no bot support, no voice API.
