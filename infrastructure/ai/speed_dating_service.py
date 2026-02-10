"""
AI Speed Dating Service - generates simulated conversations between matched users.
Uses OpenAI GPT-4o-mini to create realistic networking dialogue previews.
"""

import logging
from typing import Optional
from openai import AsyncOpenAI
from core.domain.models import User
from config.settings import settings

logger = logging.getLogger(__name__)


class SpeedDatingService:
    """Service for generating AI speed dating conversation previews"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
        self.model = "gpt-4o-mini"

    def _build_persona(self, user: User, lang: str = "en") -> str:
        """Build persona description from user profile"""
        parts = [f"Name: {user.display_name or user.first_name or 'Anonymous'}"]

        if user.bio:
            parts.append(f"About: {user.bio[:200]}")

        # Professional context
        profession = getattr(user, 'profession', None)
        company = getattr(user, 'company', None)
        if profession:
            role_str = f"Role: {profession}"
            if company:
                role_str += f" at {company}"
            parts.append(role_str)

        if user.can_help_with:
            parts.append(f"Expertise: {user.can_help_with[:150]}")

        if user.looking_for:
            parts.append(f"Looking for: {user.looking_for[:150]}")

        if user.interests:
            parts.append(f"Interests: {', '.join(user.interests[:5])}")

        if user.goals:
            parts.append(f"Goals: {', '.join(user.goals[:3])}")

        return "\n".join(parts)

    def _detect_language(self, user_a: User, user_b: User) -> str:
        """Detect conversation language from user profiles"""
        # Check for Cyrillic characters in both profiles
        texts = []
        for user in [user_a, user_b]:
            if user.bio:
                texts.append(user.bio)
            if user.looking_for:
                texts.append(user.looking_for)
            if user.can_help_with:
                texts.append(user.can_help_with)

        combined = " ".join(texts)
        if not combined:
            return "en"

        cyrillic_count = sum(1 for c in combined if '\u0400' <= c <= '\u04FF')
        return "ru" if cyrillic_count > len(combined) * 0.1 else "en"

    async def generate_conversation(
        self,
        user_a: User,
        user_b: User,
        match_context: Optional[str] = None,
        language: Optional[str] = None
    ) -> str:
        """
        Generate a simulated networking conversation between two users.

        Args:
            user_a: First user (typically the viewer)
            user_b: Second user (the match partner)
            match_context: Optional context (e.g., event name)
            language: Force specific language ('en' or 'ru')

        Returns:
            Raw conversation text in format "Name: message\nName: message\n..."
        """
        # Auto-detect language if not specified
        if not language:
            language = self._detect_language(user_a, user_b)

        # Build personas
        persona_a = self._build_persona(user_a, language)
        persona_b = self._build_persona(user_b, language)

        # Get names for the prompt
        name_a = user_a.display_name or user_a.first_name or "Person A"
        name_b = user_b.display_name or user_b.first_name or "Person B"

        # Context for conversation
        context = match_context or ("a networking event" if language == "en" else "нетворкинг-мероприятие")

        # Language instruction
        if language == "ru":
            lang_instruction = "Write the conversation in Russian. Use informal 'ты' style."
        else:
            lang_instruction = "Write the conversation in English. Keep it casual and friendly."

        prompt = f"""Simulate a fast-paced networking conversation between two people at {context}.

=== PERSON A ===
{persona_a}

=== PERSON B ===
{persona_b}

Generate exactly 5 exchanges (10 messages total). CRITICAL RULES:
1. SKIP small talk - immediately dive into VALUE EXCHANGE in the first 2 messages
2. First message: Direct opener about potential collaboration/help/shared interest
3. By message 2-3: Already discussing concrete ways to help each other or collaborate
4. Messages 4-6: Specific project/idea/opportunity they could work on together
5. Messages 7-10: Making concrete plans (exchange contacts, schedule call, share resources)
6. Keep each message SHORT (1 sentence max) - people are busy
7. Be direct and action-oriented - no fluff or pleasantries
8. End with CONCRETE next step (not vague "let's stay in touch")
9. {lang_instruction}

BAD: "Hi, nice to meet you. What brings you here?"
GOOD: "You're into AI? I have a problem you could help with."

Format (exactly like this, no extra text):
{name_a}: [message]
{name_b}: [response]
{name_a}: [message]
{name_b}: [response]
{name_a}: [message]
{name_b}: [response]
{name_a}: [message]
{name_b}: [response]
{name_a}: [message]
{name_b}: [response]"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=800,
                temperature=0.8,  # Slightly higher for more natural variation
                messages=[{"role": "user", "content": prompt}]
            )

            conversation = response.choices[0].message.content.strip()
            logger.info(f"Generated speed dating conversation for {name_a} and {name_b}")
            return conversation

        except Exception as e:
            logger.error(f"Speed dating generation failed: {e}")
            # Return fallback conversation
            if language == "ru":
                return f"""{name_a}: Привет! Рад познакомиться на этом мероприятии.
{name_b}: Привет! Взаимно, интересно узнать чем ты занимаешься.
{name_a}: Я работаю в сфере технологий. А ты?
{name_b}: Тоже в tech-индустрии. Может пообщаемся подробнее?
{name_a}: С удовольствием! Давай обменяемся контактами."""
            else:
                return f"""{name_a}: Hey! Nice to meet you at this event.
{name_b}: Hi! Same here, curious to learn what you're working on.
{name_a}: I'm in tech. How about you?
{name_b}: Also in the tech space. Maybe we should chat more?
{name_a}: Definitely! Let's exchange contacts."""

    def format_for_telegram(
        self,
        conversation: str,
        name_a: str,
        name_b: str,
        lang: str = "en"
    ) -> str:
        """
        Format conversation for Telegram display with nice styling.

        Args:
            conversation: Raw conversation text
            name_a: First person's name
            name_b: Second person's name
            lang: Language for UI strings

        Returns:
            Formatted HTML text for Telegram
        """
        # Header
        if lang == "ru":
            header = "<b>AI Speed Dating Preview</b>"
            footer = "\n<i>Сгенерировано на основе ваших профилей</i>"
        else:
            header = "<b>AI Speed Dating Preview</b>"
            footer = "\n<i>Generated based on your profiles</i>"

        # Add divider
        divider = "━" * 20

        # Format each line with speaker emoji
        lines = conversation.strip().split('\n')
        formatted_lines = []

        for line in lines:
            if not line.strip():
                continue
            # Check which speaker
            if line.startswith(f"{name_a}:"):
                # First speaker (viewer) - blue emoji
                message = line.replace(f"{name_a}:", "").strip()
                formatted_lines.append(f"<b>{name_a}:</b> {message}")
            elif line.startswith(f"{name_b}:"):
                # Second speaker (partner) - green emoji
                message = line.replace(f"{name_b}:", "").strip()
                formatted_lines.append(f"<b>{name_b}:</b> {message}")
            else:
                # Unknown format, keep as is
                formatted_lines.append(line)

        # Combine
        conversation_text = "\n\n".join(formatted_lines)

        return f"{header}\n{divider}\n\n{conversation_text}\n\n{divider}{footer}"
