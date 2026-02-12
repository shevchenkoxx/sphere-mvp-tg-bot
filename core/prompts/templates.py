"""
AI Prompts Templates - Easy to modify and localize.
All AI prompts are centralized here for easy tuning.
"""

# === CONVERSATIONAL ONBOARDING (Multilingual) ===

ONBOARDING_SYSTEM_PROMPT = """You are Sphere - an event networking assistant. Your job is to collect attendee profiles through a quick, friendly onboarding conversation.

LANGUAGE: Detect user's language from their first message and respond in the SAME language throughout the conversation. Default to English if unclear.

PERSONALITY: Friendly, energetic, concise (2-3 sentences max per message). Use occasional emoji but don't overdo it.

EVENT CONTEXT: {event_name}

ONBOARDING FLOW - Collect info ONE AT A TIME:

STEP 1 - GREETING & ABOUT:
Greet the user warmly, mention the event name if provided. Ask:
"Tell me about yourself - what do you do, what are you passionate about?"

STEP 2 - LOOKING FOR:
"Who would you like to meet at this event? What kind of connections are you looking for?"

STEP 3 - CAN HELP WITH:
"How can you help other attendees? What's your superpower or expertise?"

STEP 4 - LINK (optional):
"Got it! Last question - do you have a LinkedIn profile or website you'd like to share? (say 'skip' to skip)"

RULES:
- Ask ONE question at a time, wait for response
- After each answer: briefly acknowledge (1 sentence), then ask next question
- If answer is too short (<15 words): gently ask for more details before moving on
- For link step: accept URL or "skip"/"пропустить"/"нет" to skip
- Keep conversation natural, not robotic

STEP 5 - SHOW PROFILE FOR CONFIRMATION:
After collecting all info, show summary:
"Here's your profile:
👤 About: [answer1 summary]
🔍 Looking for: [answer2 summary]
💪 Can help: [answer3 summary]
🔗 Link: [link or 'not provided']

All correct? Say 'yes' to confirm or tell me what to change!"

STEP 6 - FINAL CONFIRMATION:
ONLY after user explicitly confirms (yes/да/ок/верно/correct), respond with:
"Perfect! Your profile is saved! 🚀

👤 About: [answer1]
🔍 Looking for: [answer2]
💪 Can help: [answer3]
🔗 Link: [link or 'not provided']

🎉 PROFILE_COMPLETE 🎉"

CRITICAL RULES:
- 🎉 PROFILE_COMPLETE 🎉 marker ONLY appears after user explicitly confirms
- If user wants to change something, update and show profile again
- Never skip steps or combine questions
- Detect language from FIRST user message and stick to it

OUTPUT FORMAT for each message:
Respond naturally. System will parse your responses to extract profile data.
When profile is complete, the 🎉 PROFILE_COMPLETE 🎉 marker triggers data extraction."""


# === PROFILE EXTRACTION (from conversation) ===

PROFILE_EXTRACTION_PROMPT = """Extract structured profile data from this onboarding conversation.

CONVERSATION:
{conversation_history}

Extract and return ONLY valid JSON:
{{
  "display_name": "name if mentioned, otherwise null",
  "about": "what they do, their background, passions",
  "looking_for": "what connections/help they're seeking",
  "can_help_with": "their expertise, how they can help others",
  "link": "LinkedIn/website URL or null if skipped",
  "language": "detected language code (en/ru/es/etc)",
  "interests": ["inferred interest tags based on about field"],
  "goals": ["inferred goal tags based on looking_for field"]
}}

Interest tags to choose from: tech, business, startups, crypto, design, art, music, books, travel, sport, wellness, psychology, gaming, ecology, cooking, cinema
Goal tags to choose from: networking, friends, business, mentorship, cofounders, creative, learning, dating

Return ONLY the JSON, no explanations."""


# === USER SUMMARY ===

USER_SUMMARY_PROMPT = """Проанализируй профиль пользователя и создай краткое описание для системы матчинга.

Данные:
- Имя: {display_name}
- Город: {city_current}
- Интересы: {interests}
- Цели: {goals}
- О себе: {bio}

Создай summary в 2-3 предложениях:
1. Ключевые характеристики (на основе интересов)
2. Что ищет (на основе целей)
3. Потенциальные точки соприкосновения

Пиши от третьего лица, тепло и информативно. Без эмодзи. Только текст."""


# === MATCH ANALYSIS ===

MATCH_ANALYSIS_PROMPT = """Проанализируй совместимость двух людей.

=== ЧЕЛОВЕК А ===
Имя: {user_a_name}
Город: {user_a_city}
Интересы: {user_a_interests}
Цели: {user_a_goals}
О себе: {user_a_bio}
Профиль: {user_a_summary}

=== ЧЕЛОВЕК Б ===
Имя: {user_b_name}
Город: {user_b_city}
Интересы: {user_b_interests}
Цели: {user_b_goals}
О себе: {user_b_bio}
Профиль: {user_b_summary}

{event_context}

Определи:
1. compatibility_score (0.0-1.0) — насколько интересны друг другу
2. match_type — один из: "friendship", "professional", "romantic", "creative"
3. explanation — почему интересны друг другу (2-3 предложения, БЕЗ имён)
4. icebreaker — вопрос для начала разговора

Отвечай ТОЛЬКО JSON:
{{"compatibility_score": 0.75, "match_type": "friendship", "explanation": "...", "icebreaker": "..."}}"""


# === ICEBREAKER ===

ICEBREAKER_PROMPT = """Сгенерируй интересный вопрос для начала разговора.

Интересы А: {user_a_interests}
Интересы Б: {user_b_interests}
Тип: {match_type}

Вопрос должен быть:
- Открытым (не да/нет)
- Связанным с общими интересами
- Легким и дружелюбным

Отвечай ТОЛЬКО вопросом."""


# === PROFILE ENRICHMENT ===

PROFILE_ENRICHMENT_PROMPT = """На основе профиля пользователя, задай один вопрос который раскроет личность.

Профиль:
- Интересы: {interests}
- Цели: {goals}
- О себе: {bio}

Требования:
- Интересный и не банальный
- Раскрывает личность
- Дружелюбная формулировка

Отвечай ТОЛЬКО вопросом."""


# === LINKEDIN PARSER (future) ===

LINKEDIN_PARSE_PROMPT = """Извлеки ключевую информацию из LinkedIn профиля:

{linkedin_content}

Верни JSON:
{{
  "name": "имя",
  "headline": "заголовок",
  "location": "город",
  "skills": ["навык1", "навык2"],
  "interests": ["интерес1", "интерес2"],
  "summary": "краткое описание"
}}"""


# === HELPER FUNCTIONS ===

def format_prompt(template: str, **kwargs) -> str:
    """Format prompt template with given values"""
    # Replace None with placeholder
    for key, value in kwargs.items():
        if value is None:
            kwargs[key] = "Not specified"
        elif isinstance(value, list):
            kwargs[key] = ", ".join(value) if value else "Not specified"
    return template.format(**kwargs)


def get_user_summary_prompt(user_data: dict) -> str:
    """Get formatted user summary prompt"""
    return format_prompt(
        USER_SUMMARY_PROMPT,
        display_name=user_data.get("display_name"),
        city_current=user_data.get("city_current"),
        interests=user_data.get("interests"),
        goals=user_data.get("goals"),
        bio=user_data.get("bio")
    )


def get_match_analysis_prompt(user_a: dict, user_b: dict, event_name: str = None) -> str:
    """Get formatted match analysis prompt"""
    event_context = f'Контекст: оба на ивенте "{event_name}"' if event_name else ""

    return format_prompt(
        MATCH_ANALYSIS_PROMPT,
        user_a_name=user_a.get("display_name") or user_a.get("first_name"),
        user_a_city=user_a.get("city_current"),
        user_a_interests=user_a.get("interests"),
        user_a_goals=user_a.get("goals"),
        user_a_bio=user_a.get("bio"),
        user_a_summary=user_a.get("ai_summary"),
        user_b_name=user_b.get("display_name") or user_b.get("first_name"),
        user_b_city=user_b.get("city_current"),
        user_b_interests=user_b.get("interests"),
        user_b_goals=user_b.get("goals"),
        user_b_bio=user_b.get("bio"),
        user_b_summary=user_b.get("ai_summary"),
        event_context=event_context
    )


# === POST-ONBOARDING PERSONALIZATION PROMPTS ===

PASSION_EXTRACTION_PROMPT = """Extract 2-4 key themes from the user's passion statement.

USER'S PASSION STATEMENT:
{passion_text}

USER'S PROFILE CONTEXT:
- Profession: {profession}
- Interests: {interests}
- Looking for: {looking_for}
- Can help with: {can_help_with}

TASK: Analyze what the user is passionate about RIGHT NOW and extract actionable themes.

Return JSON:
{{
  "themes": ["theme1", "theme2", "theme3"],
  "summary": "One sentence capturing the essence of their current passion/focus",
  "matching_signals": ["type of person 1 who would match well", "type of person 2"]
}}

RULES:
1. Themes should be SPECIFIC (not generic like "tech" but "AI product development")
2. Maximum 4 themes, minimum 2
3. Summary should be in the SAME language as passion_text
4. matching_signals: describe 2-3 types of people who would be valuable connections

Return ONLY valid JSON."""


PERSONALIZED_ADAPTIVE_BUTTONS_PROMPT = """Generate 5 specific, context-aware buttons for networking preference.

=== USER PROFILE ===
Name: {display_name}
Profession: {profession}
Bio: {bio}
Interests: {interests}
Looking for: {looking_for}
Can help with: {can_help_with}

=== CURRENT SESSION ===
Passion: {passion_text}
Extracted Themes: {passion_themes}
Connection Mode: {connection_mode}

=== TASK ===
Create 5 SPECIFIC buttons that help identify what kind of connection this user wants TODAY.

MODE-SPECIFIC APPROACH:
- If connection_mode = "give_help" → buttons about WHO they want to help (e.g., "Помочь начинающим предпринимателям", "Поделиться опытом с продуктовыми командами")
- If connection_mode = "receive_help" → buttons about WHAT help they need (e.g., "Найти ментора по привлечению инвестиций", "Получить фидбек на продукт")
- If connection_mode = "exchange" → buttons about WHAT topic to exchange (e.g., "Обсудить масштабирование AI продуктов", "Обменяться опытом в управлении командой")

RULES:
1. Each button MUST reference user's SPECIFIC context (their profession, passion themes)
2. Buttons should be mutually exclusive - choosing one gives CLEAR signal
3. Language: {language} (match user's language)
4. Button text: 4-8 words, starts with action verb
5. NO generic options like "Просто познакомиться" or "Networking"

Return JSON:
{{
  "header": "Question text to show above buttons (1 sentence in {language})",
  "buttons": ["Button 1 text", "Button 2 text", "Button 3 text", "Button 4 text", "Button 5 text"]
}}

Return ONLY valid JSON."""


IDEAL_CONNECTION_QUESTION_PROMPT = """Generate a personalized open-ended question based on user's connection mode.

Connection Mode: {connection_mode}
Passion Themes: {passion_themes}
Selected Preference: {personalization_preference}
Language: {language}

Generate ONE open-ended question (15-25 words) that helps the user describe their ideal connection.

If connection_mode = "receive_help":
  Ask about what advice/help would be most valuable for them

If connection_mode = "give_help":
  Ask about who they could help the most / what knowledge they want to share

If connection_mode = "exchange":
  Ask about the ideal person to exchange experience with

Make the question SPECIFIC to their context, not generic.
Use the same language as specified.

Return ONLY the question text, nothing else."""
