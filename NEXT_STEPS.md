# Sphere Bot - Next Steps

## Current Status (v0.4.0)

### Working ✅
- Audio onboarding (60 sec voice → profile)
- Conversational onboarding (LLM chat)
- Button onboarding (classic)
- Supabase database with enhanced schema
- Railway deployment
- Feature flags system
- Error handling

### To Test 🧪
- [ ] Audio onboarding full flow on Railway
- [ ] Event join via QR/deep link
- [ ] Profile extraction quality

---

## Priority 1: Core Flow (Next Session)

### 1.1 Test & Fix Audio Onboarding
```
User: /start → Bot shows audio guide → User records voice →
AI extracts profile → Shows confirmation → Saves to DB
```

### 1.2 Current Event Tracking
**Critical** — when user joins via `t.me/bot?start=event_CODE`:
- Extract event_code
- Save `current_event_id` to user profile
- Use for matching context

Files to edit:
- `adapters/telegram/handlers/onboarding_audio.py` — save current_event_id
- `core/services/user_service.py` — add `set_current_event()`

### 1.3 Top 3 Matches Display
After onboarding completion:
```python
# In complete_onboarding:
matches = await matching_service.get_top_matches(user_id, event_id, limit=3)
await send_top_matches_message(user, matches)
```

Message format:
```
🎯 Top 3 people to meet at [Event]:

1️⃣ **Name** - Role @ Company
   💡 Why you match
   📱 @username

2️⃣ ...
```

---

## Priority 2: Profile Quality

### 2.1 Improve Audio Extraction Prompt
Current issues to check:
- Is language detection working?
- Are interests/goals extracted correctly?
- Is the bio meaningful?

Test with `python tests/prompts/runner.py`

### 2.2 Deep Profiling (Optional)
Second LLM pass after basic extraction:
- Personality traits
- Ideal match description
- Conversation starters

---

## Priority 3: Matching

### 3.1 Enhanced Algorithm
```python
score = (
    interests_overlap * 0.2 +
    goals_alignment * 0.3 +
    skills_complement * 0.2 +
    ai_compatibility * 0.3
)
```

### 3.2 Icebreakers
Generate specific conversation starters based on shared interests.

---

## Priority 4: Future Features

### LinkedIn Parsing
- User sends URL → fetch via Proxycurl → enrich profile
- Cost: ~$0.01 per lookup

### WhatsApp Adapter
- Same core services, new adapter
- `adapters/whatsapp/`

### Admin Dashboard
- Create events
- Generate QR codes
- View analytics

---

## Key Files Reference

| What | File |
|------|------|
| Feature toggles | `config/features.py` |
| Audio prompts | `core/prompts/audio_onboarding.py` |
| Conversation prompts | `core/prompts/templates.py` |
| Audio handler | `adapters/telegram/handlers/onboarding_audio.py` |
| Matching service | `core/services/matching_service.py` |
| User service | `core/services/user_service.py` |
| DB schema | `supabase/schema.sql` + `migrations/002_*.sql` |

---

## Commands

```bash
# Local dev
cd sphere-bot && python3 main.py

# Test prompts
python3 tests/prompts/runner.py

# Check bot status
curl -s "https://api.telegram.org/bot$TOKEN/getMe"
```

## Environment (Railway)

```
TELEGRAM_BOT_TOKEN=<from .env>
SUPABASE_URL=<from .env>
SUPABASE_KEY=<from .env>
OPENAI_API_KEY=<from .env>
ONBOARDING_MODE=audio
```
