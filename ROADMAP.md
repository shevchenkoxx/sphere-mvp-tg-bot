# Sphere Roadmap

## Current Version: 0.2.0 (MVP)

---

## Phase 1: Enhanced Profile Creation (Next)

### Image Uploads
**Plan:**
1. Accept photos in Telegram chat during onboarding
2. Store in Supabase Storage bucket
3. Generate thumbnail for fast loading
4. Use in match cards and profile views

**Implementation:**
```python
# adapters/telegram/handlers/onboarding.py
@router.message(OnboardingStates.waiting_photo, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]  # Largest size
    file = await bot.get_file(photo.file_id)
    # Download and upload to Supabase Storage
```

**Database changes:**
```sql
ALTER TABLE users ADD COLUMN avatar_url TEXT;
ALTER TABLE users ADD COLUMN photos JSONB DEFAULT '[]';
```

### LinkedIn Profile Parsing
**Plan:**
1. User sends LinkedIn URL
2. Fetch public profile data (name, headline, skills)
3. Pre-fill onboarding fields
4. Generate AI summary from LinkedIn data

**Implementation approach:**
- Option A: Use LinkedIn API (requires OAuth, complex)
- Option B: Use web scraping service (Proxycurl, Scrapin)
- Option C: Ask user to copy-paste profile text

**Recommended: Option B with Proxycurl**
```python
# infrastructure/external/linkedin_service.py
class LinkedInService:
    async def parse_profile(self, url: str) -> dict:
        response = await httpx.get(
            "https://nubela.co/proxycurl/api/v2/linkedin",
            params={"url": url},
            headers={"Authorization": f"Bearer {PROXYCURL_KEY}"}
        )
        return response.json()
```

**Prompt for parsing (already in templates.py):**
```python
LINKEDIN_PARSE_PROMPT = """Извлеки ключевую информацию из LinkedIn профиля..."""
```

---

## Phase 2: Enhanced Matching

### Smart Recommendations
- [ ] ML-based compatibility scoring
- [ ] Learn from user feedback (likes/skips)
- [ ] Time-decay for event relevance
- [ ] Location-based suggestions

### Match Quality
- [ ] Mutual interests weighting
- [ ] Goal alignment scoring
- [ ] Event context boost
- [ ] Conversation starter quality

---

## Phase 3: Multi-Platform

### WhatsApp Integration
**Plan:**
1. Use WhatsApp Business API (Meta)
2. Same core services, new adapter
3. Webhook-based message handling

**Structure:**
```
adapters/
  telegram/     # Current
  whatsapp/     # New adapter
    handlers/
    keyboards/  # WhatsApp buttons
    loader.py
```

### PWA (Progressive Web App)
**Plan:**
1. REST API layer (FastAPI)
2. Simple React/Vue frontend
3. QR code scanner in browser
4. Push notifications

**Structure:**
```
adapters/
  api/          # REST API
    routes/
    schemas/
```

### Admin Dashboard
**Plan:**
1. Event creation/management
2. QR code generation
3. Analytics dashboard
4. User moderation

---

## Phase 4: Advanced Features

### In-App Chat
- [ ] Real-time messaging
- [ ] Message encryption
- [ ] Read receipts
- [ ] Media sharing

### Event Features
- [ ] Event scheduling
- [ ] Attendance tracking
- [ ] Post-event surveys
- [ ] Connection quality metrics

### Gamification
- [ ] Profile completion rewards
- [ ] Successful match badges
- [ ] Event participation streaks

---

## Technical Debt

### Performance
- [ ] Redis caching for user data
- [ ] Connection pooling for Supabase
- [ ] Rate limiting

### Monitoring
- [ ] Sentry for error tracking
- [ ] Prometheus metrics
- [ ] Logging aggregation

### Testing
- [ ] Unit tests for core services
- [ ] Integration tests for handlers
- [ ] E2E tests for onboarding flow

---

## Timeline Estimate

| Phase | Target |
|-------|--------|
| Phase 1 (Images, LinkedIn) | Feb 2025 |
| Phase 2 (Better Matching) | Mar 2025 |
| Phase 3 (WhatsApp, PWA) | Apr-May 2025 |
| Phase 4 (Advanced) | Q3 2025 |
