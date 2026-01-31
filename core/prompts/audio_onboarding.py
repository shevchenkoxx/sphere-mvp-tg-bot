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
AUDIO_EXTRACTION_PROMPT = """You are a profile data extractor. Extract structured information from this voice message transcription.

TRANSCRIPTION:
{transcription}

CONTEXT:
- Event: {event_name}
- Language detected: {language}

Extract the following and return as JSON:

{{
  "display_name": "name if mentioned, null otherwise",
  "language": "language code (en/ru/es/de/fr/etc)",

  "about": "concise summary of who they are, what they do (2-3 sentences max)",
  "looking_for": "what kind of people/connections they want to meet",
  "can_help_with": "their expertise, how they can help others",

  "interests": ["list of 3-5 relevant interest tags"],
  "goals": ["list of 1-3 goal tags"],

  "profession": "their job/role if mentioned",
  "company": "company name if mentioned",
  "link": "any URL mentioned (linkedin, website, etc)",

  "raw_highlights": ["3-5 key quotes or interesting points from their message"],
  "confidence_score": 0.0-1.0
}}

INTEREST TAGS (choose from):
tech, business, startups, crypto, design, art, music, books, travel, sport, wellness, psychology, gaming, ecology, cooking, cinema, science, education, marketing, finance

GOAL TAGS (choose from):
networking, friends, business, mentorship, cofounders, creative, learning, dating, hiring, investing

RULES:
- Extract ONLY what was explicitly said or strongly implied
- Keep "about" concise but capture personality
- If something wasn't mentioned, use null or empty array
- confidence_score: how complete/clear the information was (1.0 = very clear, 0.5 = partial)
- raw_highlights: memorable quotes that show personality

Return ONLY valid JSON, no markdown or explanations."""


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
