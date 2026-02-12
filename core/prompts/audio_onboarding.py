"""
Audio Onboarding Prompts - Extract structured profile from voice message.
User speaks freely for 60 seconds, we extract everything needed.

Language handling: English is the default. Russian supported.
Language is auto-detected from Telegram settings.
"""

# Whisper transcription prompts — domain vocabulary hints.
# These are NOT instructions; Whisper treats them as "preceding context"
# so it knows which words to expect and spell correctly.
WHISPER_PROMPT_EN = (
    "Hi, my name is Alexander Petrov. I'm a Senior Product Manager "
    "at a tech startup, working on AI, machine learning, and SaaS solutions. "
    "I'm looking for co-founders, angel investors, and blockchain developers. "
    "I can help with fundraising, venture capital, UX design, growth hacking, "
    "B2B sales, and product-market fit. I'm passionate about Web3, DeFi, "
    "cryptocurrency, and decentralized finance."
)

WHISPER_PROMPT_RU = (
    "Привет, меня зовут Александр Петров. Я продакт-менеджер в стартапе, "
    "работаю с искусственным интеллектом, машинным обучением и SaaS. "
    "Ищу кофаундеров, инвесторов и блокчейн-разработчиков. "
    "Могу помочь с фандрайзингом, венчурным капиталом, UX-дизайном, "
    "growth-маркетингом, B2B-продажами и product-market fit. "
    "Увлекаюсь Web3, DeFi, криптовалютами и децентрализованными финансами."
)

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

# Rich static templates (used instead of LLM for consistent formatting)
AUDIO_WELCOME_EN = """Hey{name_part}! Welcome to <b>Sphere</b> 👋

<b>The Future of Dating is here</b>

I'll find you the best people to meet — just record a quick voice intro (30-60 sec).

<b>Here's what to include:</b>

   🙋 <i>Who are you and what do you do?</i>
   🔍 <i>What kind of people do you want to meet?</i>
   💡 <i>How can you help others with your expertise?</i>

Just relax and speak naturally — this is all about making meaningful connections!

🎁 <b>Sphere × Valentine's Day Giveaway</b>
Rate your matches and win a prize! Details in the menu ✨"""

AUDIO_WELCOME_RU = """Привет{name_part}! Добро пожаловать в <b>Sphere</b> 👋

<b>The Future of Dating is here</b>

Я найду тебе лучших людей для знакомства — просто запиши короткое голосовое (30-60 сек).

<b>Расскажи:</b>

   🙋 <i>Кто ты и чем занимаешься?</i>
   🔍 <i>Кого хочешь встретить?</i>
   💡 <i>Чем можешь помочь другим?</i>

Говори свободно и естественно — здесь важны живые люди, а не формальности!

🎁 <b>Sphere × Valentine's Day Giveaway</b>
Оцени свои матчи и выиграй приз! Подробности в меню ✨"""

# Fallback static guides (used if LLM fails)
AUDIO_GUIDE_PROMPT = AUDIO_WELCOME_EN
AUDIO_GUIDE_PROMPT_RU = AUDIO_WELCOME_RU

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
- **"about" MUST be written in FIRST PERSON** ("I build...", "I work at...", "I'm passionate about...") — NEVER third person ("They are involved...", "He works at...")
- **Correct obvious transcription errors** based on context. Speech-to-text often mishears domain-specific words (e.g. "phones" → "funds" when talking about investing, "bloc chain" → "blockchain"). Use surrounding context to fix these.
- **For "display_name"**: extract the person's FULL NAME as spoken (e.g. "My name is Artem Shevchenko" → "Artem Shevchenko"). If no name is clearly stated, set display_name to empty string "" — the system will fall back to their Telegram name.

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
# NOTE: These are now format-string fragments. The actual assembly
# happens in show_profile_confirmation() which conditionally includes
# sections only when data is present.

AUDIO_CONFIRMATION_HEADER = "Got it! Here's your profile:\n"
AUDIO_CONFIRMATION_HEADER_RU = "Отлично! Вот твой профиль:\n"

AUDIO_CONFIRMATION_FOOTER = "\nAll good? Say \"yes\" to confirm or record another message to update."
AUDIO_CONFIRMATION_FOOTER_RU = "\nВсё верно? Скажи \"да\" для подтверждения или запиши новое сообщение."


# Post-transcription correction prompt — fast LLM pass to fix Whisper errors
TRANSCRIPT_CORRECTION_PROMPT = """Fix speech-to-text errors in this transcription of a networking event voice intro.

TRANSCRIPTION:
{transcription}

RULES:
- Fix obvious misheard words using context (e.g. "phones" → "funds", "bloc chain" → "blockchain", "founder raising" → "fundraising")
- Fix garbled proper nouns, company names, tech terms
- Do NOT rephrase, summarize, or change meaning — only fix errors
- Do NOT add punctuation that changes meaning
- Keep the EXACT same language (if Russian, output Russian)
- If the transcription looks clean, return it unchanged

Return ONLY the corrected text, nothing else."""
