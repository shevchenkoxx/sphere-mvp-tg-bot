# Sphere Integration Plan

## Current State Analysis

### Database Schema (Supabase)
Current tables: `users`, `events`, `event_participants`, `matches`, `messages`

**Issues to fix:**
1. No `current_event_id` on users - can't track which event user is currently at
2. No deep profile fields (profession, company, skills, etc.)
3. No social links parsing storage
4. No audio transcription storage

### Data Flow
```
User scans QR → Joins via deep link → Onboarding → Profile saved → Matching → Top 3 shown
                    ↓
              event_code extracted
              (CRITICAL: save to current_event_id)
```

---

## Phase 1: Database Enhancement (CRITICAL)

### 1.1 Schema Updates

```sql
-- Add to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS current_event_id UUID REFERENCES events(id);
ALTER TABLE users ADD COLUMN IF NOT EXISTS profession VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS company VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT '{}';
ALTER TABLE users ADD COLUMN IF NOT EXISTS looking_for TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS can_help_with TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'ru';

-- Deep profile from LLM
ALTER TABLE users ADD COLUMN IF NOT EXISTS deep_profile JSONB DEFAULT '{}';

-- Audio data
ALTER TABLE users ADD COLUMN IF NOT EXISTS audio_transcription TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS raw_highlights TEXT[] DEFAULT '{}';

-- Social parsing
ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_url TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_data JSONB DEFAULT '{}';
```

### 1.2 Current Event Tracking

**Flow:**
1. User clicks `t.me/bot?start=event_ABC123`
2. Extract `event_ABC123` → event_code = `ABC123`
3. On successful onboarding: `UPDATE users SET current_event_id = (SELECT id FROM events WHERE code = 'ABC123')`

**Code changes:**
- `adapters/telegram/handlers/start.py` - save event_code to state
- `adapters/telegram/handlers/onboarding_*.py` - update current_event_id on completion
- `core/services/user_service.py` - add `set_current_event()` method

---

## Phase 2: Deep Profiling

### 2.1 Enhanced Audio Extraction

**Current prompt extracts:**
- about, looking_for, can_help_with
- interests, goals
- profession, company

**Add to extraction:**
```json
{
  "personality_traits": ["analytical", "creative", "social"],
  "communication_style": "direct/warm/formal",
  "expertise_level": "beginner/intermediate/expert",
  "availability": "full-time/part-time/looking",
  "industry_experience": ["fintech", "healthtech"],
  "languages_spoken": ["en", "ru"],
  "meeting_preference": "1on1/group/both"
}
```

### 2.2 LLM Deep Profile Generation

After basic profile extraction, run second pass:

```python
DEEP_PROFILE_PROMPT = """
Based on this profile, create a deep analysis:

Profile:
{profile_data}

Transcription:
{transcription}

Generate JSON:
{
  "personality_summary": "2-3 sentences about who this person really is",
  "ideal_match_profile": "description of who they'd connect well with",
  "conversation_starters": ["topic1", "topic2", "topic3"],
  "networking_score": 0.0-1.0,
  "expertise_areas": [{"area": "x", "level": "expert"}],
  "red_flags": [],  // anything concerning
  "super_power": "their unique value"
}
"""
```

---

## Phase 3: Social Parsing

### 3.1 LinkedIn Integration

**Option A: User pastes URL** (MVP - start here)
```
User: "linkedin.com/in/johndoe"
Bot: Fetches public data, enriches profile
```

**Option B: Proxycurl API** (Paid, better data)
```python
async def parse_linkedin(url: str) -> dict:
    response = await httpx.get(
        "https://nubela.co/proxycurl/api/v2/linkedin",
        params={"url": url},
        headers={"Authorization": f"Bearer {PROXYCURL_KEY}"}
    )
    return response.json()
```

**Option C: User connects OAuth** (Future - best data)

### 3.2 Other Socials
- Twitter/X: bio, followers, interests
- Instagram: bio, content type
- GitHub: repos, languages, activity

Store in `social_links` JSONB field.

---

## Phase 4: Matching Engine

### 4.1 Current Matching
```python
compatibility_score = AI_analyze(user_a, user_b)
```

### 4.2 Enhanced Matching

**Multi-factor scoring:**
```python
def calculate_match_score(user_a, user_b, event):
    scores = {
        "interests_overlap": calculate_interests_overlap(user_a, user_b),
        "goals_alignment": calculate_goals_alignment(user_a, user_b),
        "complementary_skills": calculate_skill_complement(user_a, user_b),
        "communication_style": calculate_style_match(user_a, user_b),
        "ai_compatibility": await ai_analyze(user_a, user_b),
        "event_relevance": calculate_event_relevance(user_a, user_b, event)
    }

    # Weighted average
    weights = {
        "interests_overlap": 0.15,
        "goals_alignment": 0.25,
        "complementary_skills": 0.20,
        "communication_style": 0.10,
        "ai_compatibility": 0.20,
        "event_relevance": 0.10
    }

    return sum(scores[k] * weights[k] for k in weights)
```

### 4.3 Top 3 Matches Display

**Flow:**
1. User completes onboarding at event
2. System finds all other participants
3. Runs matching algorithm
4. Returns top 3 with explanations

**Message template:**
```
🎯 Вот с кем тебе стоит познакомиться на [Event Name]:

1️⃣ **Анна** - Product Designer @ Yandex
   💡 Вы оба в продукте, она ищет кофаундера — идеальный мэтч!
   📱 @anna_design

2️⃣ **Михаил** - AI Researcher
   💡 Ты ищешь ML-специалиста, он хочет в стартап
   📱 @mikhail_ai

3️⃣ **Елена** - Инвестор
   💡 Она инвестирует в AI-стартапы на ранней стадии
   📱 @elena_vc

Напиши им прямо сейчас! 🚀
```

---

## Phase 5: Implementation Order

### Step 1: Database Migration (30 min)
- [ ] Create migration SQL
- [ ] Apply to Supabase
- [ ] Update models in code

### Step 2: Current Event Tracking (1 hour)
- [ ] Update start.py to save event context
- [ ] Update onboarding handlers to set current_event_id
- [ ] Add `set_current_event()` to user_service

### Step 3: Enhanced Profile Fields (1 hour)
- [ ] Update User model
- [ ] Update user_repository
- [ ] Update audio extraction prompt
- [ ] Test extraction

### Step 4: Deep Profile Generation (1 hour)
- [ ] Create deep_profile_prompt
- [ ] Add deep_profile service
- [ ] Store in users.deep_profile
- [ ] Test

### Step 5: Matching Algorithm (2 hours)
- [ ] Create scoring functions
- [ ] Update matching_service
- [ ] Create match display templates
- [ ] Test with sample data

### Step 6: Top 3 Display (1 hour)
- [ ] Create match notification handler
- [ ] Create contact sharing
- [ ] Test full flow

### Step 7: LinkedIn Parsing (2 hours)
- [ ] Create linkedin_service
- [ ] Add URL detection in onboarding
- [ ] Parse and enrich profile
- [ ] Test

---

## Files to Update

### Database
- `supabase/migrations/002_enhanced_profiles.sql` (new)

### Models
- `core/domain/models.py` - add new fields to User
- `core/interfaces/repositories.py` - update IUserRepository

### Services
- `core/services/user_service.py` - add current_event, deep_profile methods
- `core/services/matching_service.py` - enhance matching algorithm
- `core/services/linkedin_service.py` (new)
- `core/services/deep_profile_service.py` (new)

### Prompts
- `core/prompts/audio_onboarding.py` - enhance extraction
- `core/prompts/deep_profile.py` (new)
- `core/prompts/matching.py` (new)

### Handlers
- `adapters/telegram/handlers/start.py` - event context
- `adapters/telegram/handlers/onboarding_audio.py` - current_event_id
- `adapters/telegram/handlers/matches.py` - top 3 display

### Infrastructure
- `infrastructure/database/user_repository.py` - new fields
- `infrastructure/external/linkedin_service.py` (new)

---

## Testing Checklist

- [ ] User joins via QR link → event_code saved
- [ ] Audio onboarding → profile extracted correctly
- [ ] Deep profile generated after onboarding
- [ ] LinkedIn URL parsed (if provided)
- [ ] current_event_id set correctly
- [ ] Matching runs on event participants
- [ ] Top 3 matches displayed with contacts
- [ ] User can contact matches
