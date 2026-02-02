"""
Audio Onboarding Prompts - Extract structured profile from voice message.
User speaks freely for 60 seconds, we extract everything needed.

Language handling: English is the default. Russian supported.
Language is auto-detected from Telegram settings.
"""

# LLM prompt to generate personalized intro (replaces static guide)
AUDIO_INTRO_PROMPT = """You are a friendly networking bot helping someone at a {event_context}.

Generate a SHORT, warm welcome message (3-4 sentences max) that:
1. Greets them naturally
2. Explains we'll use their voice intro to find great matches
3. Tells them what to include in their 60-second voice message:
   - Who they are & what they do
   - What kind of people they want to meet
   - How they can help others / their expertise
4. Encourages them to speak naturally

Language: {language_name}
User's first name: {first_name}

Keep it conversational, not like a form. Use 1-2 relevant emojis.
Return ONLY the message text."""

# Fallback static guides (used if LLM fails)
AUDIO_GUIDE_PROMPT = """🎤 Record a 60-second voice message about yourself:

**Please include:**
• Who you are and what you do
• What kind of people you'd like to meet here
• How you can help others (your expertise)

Speak naturally - I'll use this to find your best matches!"""

AUDIO_GUIDE_PROMPT_RU = """🎤 Запиши голосовое сообщение на 60 секунд о себе:

**Расскажи:**
• Кто ты и чем занимаешься
• Кого хотел бы встретить здесь
• Чем можешь помочь другим (твоя экспертиза)

Говори свободно — я использую это чтобы найти лучшие матчи!"""

# Extraction prompt - converts transcription to structured data
# Using Chain-of-thought (A3) approach for deeper analysis
AUDIO_EXTRACTION_PROMPT = """You are an expert profile data extractor for a networking app.

TRANSCRIPTION:
{transcription}

CONTEXT:
- Event: {event_name}
- User's UI language preference: {language}

---

Analyze this transcription STEP BY STEP:

## STEP 1 - FACTS
List all concrete facts mentioned:
- Name?
- Current job/role?
- Company/organization?
- Location/city?
- Years of experience?
- Specific skills or expertise?
- What they're looking for?
- How they can help others?

## STEP 2 - CONTEXT
What can we understand from context:
- Experience level (junior/mid/senior/founder/executive)?
- Industry they work in?
- Their communication style?
- Personality traits that come through?

## STEP 3 - INSIGHTS
What makes this person unique:
- What's their unique value proposition?
- What type of connections would benefit them most?
- Any memorable quotes or points?

## STEP 4 - JSON OUTPUT

Based ONLY on what was stated or very clearly implied, extract as JSON:

{{
  "display_name": "name if mentioned",
  "language": "language code (en/ru/etc)",

  "about": "WHO they are - rich summary (3-4 sentences) capturing personality, background, current focus. Include: what they do, experience level, what makes them unique",

  "looking_for": "SPECIFIC types of people/connections they want. Be detailed: 'looking for technical co-founder for AI startup' not just 'co-founder'",

  "can_help_with": "SPECIFIC expertise. Be detailed: 'UX design, user research, design systems for mobile apps' not just 'design'",

  "interests": ["3-5 tags ONLY if explicitly mentioned or very clearly implied"],
  "goals": ["2-4 goal tags - what they want from networking"],

  "profession": "specific job title/role (e.g. 'Senior Product Manager' not 'PM')",
  "company": "company/organization if mentioned",
  "industry": "industry/field",
  "experience_level": "junior/mid/senior/founder/executive",

  "skills": ["specific skills - technical and soft"],
  "expertise_areas": ["areas of deep knowledge"],

  "personality_traits": ["2-3 traits - e.g. ambitious, creative, analytical"],
  "communication_style": "brief description",

  "link": "any URL mentioned",
  "location": "city/country if mentioned",

  "raw_highlights": ["4-6 memorable quotes or points that show personality"],
  "unique_value": "one sentence: what makes this person uniquely valuable to meet",

  "confidence_score": 0.0-1.0,
  "extraction_notes": "any ambiguities or assumptions made"
}}

---

VALID TAGS:

INTERESTS (choose ONLY if explicitly mentioned):
tech, AI, ML, product, business, startups, crypto, web3, design, UX, art, music, books, travel, sport, fitness, wellness, psychology, gaming, ecology, cooking, cinema, science, education, marketing, growth, finance, investing, sales, HR, legal, healthcare, real_estate

GOALS (choose from):
networking, friends, business, mentorship, cofounders, creative, learning, dating, hiring, investing, partnerships, advice, collaboration

---

CRITICAL RULES:
- Extract in the SAME LANGUAGE as the transcription
- ONLY include interests that are EXPLICITLY mentioned (90%+ confidence)
- "tech" does NOT imply crypto/web3/finance
- "startups" does NOT imply crypto/investing
- "about", "looking_for", "can_help_with" must be from their ACTUAL words
- confidence_score: 1.0 = explicit, 0.7 = clearly implied, 0.5 = inferred (risky)

Return the full chain of thought, then the JSON at the end.
Mark the JSON section clearly with "## JSON:" header."""


# Validation prompt - check what's missing and generate follow-up
AUDIO_VALIDATION_PROMPT = """Analyze this extracted profile and determine if we have enough info for good matching.

EXTRACTED PROFILE:
- Name: {display_name}
- About: {about}
- Looking for: {looking_for}
- Can help with: {can_help_with}
- Interests: {interests}

REQUIRED FOR GOOD MATCHING:
1. "about" - who they are (REQUIRED)
2. "looking_for" - what kind of connections they want (IMPORTANT)
3. "can_help_with" - their expertise/how they help others (IMPORTANT)

Analyze and return JSON:
{{
  "is_complete": true/false,
  "missing_fields": ["looking_for", "can_help_with"],  // list of missing important fields
  "completeness_score": 0.0-1.0,
  "follow_up_question": "natural question to get missing info (in {language})" or null
}}

RULES:
- is_complete = true if we have "about" AND at least one of (looking_for, can_help_with)
- If both looking_for AND can_help_with are missing, ask about BOTH in one natural question
- Keep follow_up_question conversational, not robotic
- Use the specified language for the question

Return ONLY valid JSON."""

# Legacy follow-up prompt (for simple cases)
AUDIO_FOLLOWUP_PROMPT = """Generate a natural follow-up question to complete someone's networking profile.

Current info we have:
- About: {about}

What we're missing: {missing_fields}

Language: {language}

Generate ONE short, friendly question (1-2 sentences) that asks about the missing info naturally.
Don't sound like a form - be conversational.

Return ONLY the question text."""


# Confirmation message template
AUDIO_CONFIRMATION_TEMPLATE = """Got it! Here's your profile:

👤 **{display_name}**
{about}

🔍 **Looking for:** {looking_for}
💪 **Can help with:** {can_help_with}

{interests_display}

All good? Say "yes" to confirm or record another message to update."""

AUDIO_CONFIRMATION_TEMPLATE_RU = """Отлично! Вот твой профиль:

👤 **{display_name}**
{about}

🔍 **Ищу:** {looking_for}
💪 **Могу помочь:** {can_help_with}

{interests_display}

Всё верно? Скажи "да" для подтверждения или запиши новое сообщение."""
