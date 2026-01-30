"""
Audio Onboarding Prompts - Extract structured profile from voice message.
User speaks freely for 60 seconds, we extract everything needed.
"""

# System prompt for guiding the user what to say
AUDIO_GUIDE_PROMPT = """Record a 60-second voice message telling us about yourself:

🎤 **What to include:**
- Who you are and what you do
- What you're passionate about
- Who you'd like to meet here
- How you can help others

Just speak naturally - no need to follow a script!
"""

AUDIO_GUIDE_PROMPT_RU = """Запиши голосовое сообщение на 60 секунд о себе:

🎤 **Что рассказать:**
- Кто ты и чем занимаешься
- Что тебя вдохновляет
- Кого хочешь встретить
- Чем можешь помочь другим

Говори свободно - без скриптов!
"""

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


# Follow-up prompt if we need more info
AUDIO_FOLLOWUP_PROMPT = """Based on the profile extracted, we're missing some key information.

Current profile:
- About: {about}
- Looking for: {looking_for}
- Can help: {can_help_with}

Missing: {missing_fields}

Generate a short, friendly follow-up question (1-2 sentences) to get the missing info.
The question should feel natural, not like a form.

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
