"""
OpenAI GPT service implementation.
Handles user analysis and match compatibility using GPT-4.
"""

import json
import re
import logging
from typing import Dict, Any
from openai import AsyncOpenAI
from core.domain.models import MatchResult, MatchType
from core.interfaces.ai import IAIService
from config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIService(IAIService):
    """OpenAI GPT-based AI service for user analysis and matching"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
        self.model = "gpt-4o-mini"  # Fast and cheap, good for MVP

    async def generate_user_summary(self, user_data: Dict[str, Any]) -> str:
        """Generate AI summary of user profile for matching system"""

        # Build context from ACTUAL user data only
        name = user_data.get('display_name') or 'Someone'
        bio = user_data.get('bio') or ''
        looking_for = user_data.get('looking_for') or ''
        can_help_with = user_data.get('can_help_with') or ''

        # Only include interests that were explicitly set
        interests = user_data.get('interests', [])
        interests_str = ', '.join(interests) if interests else ''

        prompt = f"""Create a brief profile summary based ONLY on what the user actually stated.

ACTUAL USER DATA:
- Bio: {bio if bio else 'Not provided'}
- Looking for: {looking_for if looking_for else 'Not specified'}
- Can help with: {can_help_with if can_help_with else 'Not specified'}
- Interests: {interests_str if interests_str else 'None listed'}

RULES:
1. ONLY summarize information that is explicitly stated above
2. Do NOT infer or add interests/skills not mentioned
3. If bio mentions "AI creator", do NOT assume crypto/web3 interests
4. Keep it factual - describe what they said, not what you think
5. If data is minimal, keep summary short

Create a 1-2 sentence summary. Third person, no emojis.
Language: same as bio text."""

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content

    def _detect_language(self, *texts) -> str:
        """Detect language from text content - checks for Cyrillic characters"""
        combined = " ".join(t for t in texts if t)
        cyrillic_count = sum(1 for c in combined if '\u0400' <= c <= '\u04FF')
        return "ru" if cyrillic_count > len(combined) * 0.1 else "en"

    async def analyze_match(
        self,
        user_a: Dict[str, Any],
        user_b: Dict[str, Any],
        event_context: str = None,
        language: str = None
    ) -> MatchResult:
        """Analyze compatibility between two users"""

        # Build profiles with safe defaults
        name_a = user_a.get('display_name') or user_a.get('first_name') or 'Anonymous'
        name_b = user_b.get('display_name') or user_b.get('first_name') or 'Anonymous'

        # Extract ACTUAL user-stated data - these are PRIMARY for matching
        bio_a = user_a.get('bio') or ""
        bio_b = user_b.get('bio') or ""
        looking_for_a = user_a.get('looking_for') or ""
        can_help_a = user_a.get('can_help_with') or ""
        looking_for_b = user_b.get('looking_for') or ""
        can_help_b = user_b.get('can_help_with') or ""
        interests_a = user_a.get('interests', [])
        interests_b = user_b.get('interests', [])

        # Additional context fields
        profession_a = user_a.get('profession') or ""
        profession_b = user_b.get('profession') or ""
        company_a = user_a.get('company') or ""
        company_b = user_b.get('company') or ""
        skills_a = user_a.get('skills', [])
        skills_b = user_b.get('skills', [])

        # Personalization context (post-onboarding)
        passion_a = user_a.get('passion_text') or ""
        passion_b = user_b.get('passion_text') or ""
        passion_themes_a = user_a.get('passion_themes', [])
        passion_themes_b = user_b.get('passion_themes', [])
        conn_mode_a = user_a.get('connection_mode') or ""
        conn_mode_b = user_b.get('connection_mode') or ""
        ideal_a = user_a.get('ideal_connection') or ""
        ideal_b = user_b.get('ideal_connection') or ""

        # Detect language from user content if not provided
        if not language:
            language = self._detect_language(bio_a, bio_b, looking_for_a, looking_for_b, can_help_a, can_help_b)

        lang_instruction = "Russian" if language == "ru" else "English"

        # Build personalization context section
        personalization_context = ""
        if passion_a or passion_b or conn_mode_a or conn_mode_b:
            personalization_context = "\n=== PERSONALIZATION CONTEXT ===\n"
            if passion_themes_a or passion_themes_b:
                themes_overlap = set(passion_themes_a) & set(passion_themes_b) if passion_themes_a and passion_themes_b else set()
                personalization_context += f"A's current passion themes: {', '.join(passion_themes_a) if passion_themes_a else 'None'}\n"
                personalization_context += f"B's current passion themes: {', '.join(passion_themes_b) if passion_themes_b else 'None'}\n"
                if themes_overlap:
                    personalization_context += f"THEME OVERLAP: {', '.join(themes_overlap)} ✓\n"

            if conn_mode_a and conn_mode_b:
                # Check for complementary modes (give_help <-> receive_help)
                complementary = (
                    (conn_mode_a == "give_help" and conn_mode_b == "receive_help") or
                    (conn_mode_a == "receive_help" and conn_mode_b == "give_help")
                )
                personalization_context += f"A's connection mode: {conn_mode_a}\n"
                personalization_context += f"B's connection mode: {conn_mode_b}\n"
                if complementary:
                    personalization_context += "COMPLEMENTARY MODES: One wants to help, other wants to receive ✓\n"

            if ideal_a:
                personalization_context += f"A's ideal connection description: {ideal_a[:150]}\n"
            if ideal_b:
                personalization_context += f"B's ideal connection description: {ideal_b[:150]}\n"

        prompt = f"""Analyze compatibility between two people for networking at an event.

CRITICAL: Base analysis ONLY on what users ACTUALLY stated. Do NOT invent or assume.

=== PERSON A: {name_a} ===
Bio: {bio_a or 'Not provided'}
Profession: {profession_a or 'Not specified'}
Company: {company_a or 'Not specified'}
Skills: {', '.join(skills_a) if skills_a else 'None'}
Looking for: {looking_for_a or 'Not specified'}
Can help with: {can_help_a or 'Not specified'}
Interests: {', '.join(interests_a) if interests_a else 'None'}
{f'Current passion: {passion_a[:150]}' if passion_a else ''}

=== PERSON B: {name_b} ===
Bio: {bio_b or 'Not provided'}
Profession: {profession_b or 'Not specified'}
Company: {company_b or 'Not specified'}
Skills: {', '.join(skills_b) if skills_b else 'None'}
Looking for: {looking_for_b or 'Not specified'}
Can help with: {can_help_b or 'Not specified'}
Interests: {', '.join(interests_b) if interests_b else 'None'}
{f'Current passion: {passion_b[:150]}' if passion_b else ''}
{personalization_context}
{f'Event: "{event_context}"' if event_context else ''}

SCORING CRITERIA (in order of importance):
1. VALUE EXCHANGE (0.4 weight): Does A's "can_help" match B's "looking_for" or vice versa?
   - Direct match: +0.4 | Partial: +0.2 | None: 0
2. PROFESSIONAL SYNERGY (0.3 weight): Could they collaborate based on profession/skills?
   - Same industry + complementary skills: +0.3 | Same industry: +0.15 | None: 0
3. INTERESTS OVERLAP (0.2 weight): Shared explicit interests?
   - 2+ shared: +0.2 | 1 shared: +0.1 | None: 0
4. GOALS ALIGNMENT (0.1 weight): Similar networking goals?
   - Both looking for same type of connection: +0.1

ONLY MATCH IF:
- There is at least ONE concrete reason they should meet
- Score >= 0.5 means they have real potential value for each other
- Score < 0.4 = don't waste their time

LANGUAGE: {lang_instruction}

Return JSON:
{{
  "compatibility_score": 0.0-1.0,
  "match_type": "professional" | "friendship" | "creative" | "romantic",
  "explanation": "1-2 sentences in {lang_instruction}. Be SPECIFIC about WHY they should meet. Example: 'Ты ищешь инвестора, а он работает в фонде' NOT 'У вас общие интересы'",
  "icebreaker": "Direct actionable opener in {lang_instruction}. Example: 'Расскажи про свой стартап - могу помочь с фандрейзингом'"
}}

IMPORTANT:
- Be SPECIFIC in explanation - mention actual skills/needs
- Icebreaker should be ACTION-oriented, not small talk
- Score honestly - bad matches hurt user trust
Respond with valid JSON only."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON from response
            text = response.choices[0].message.content

            # Remove possible markdown blocks
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()

            data = json.loads(text)
            return MatchResult(
                compatibility_score=data["compatibility_score"],
                match_type=MatchType(data["match_type"]),
                explanation=data["explanation"],
                icebreaker=data["icebreaker"]
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse match analysis: {type(e).__name__}: {e} | raw={text[:200] if 'text' in locals() else 'N/A'}")
        except Exception as e:
            logger.error(f"Match analysis failed: {e}")

        # Fallback with proper language
        if language == "ru":
            return MatchResult(
                compatibility_score=0.5,
                match_type=MatchType.FRIENDSHIP,
                explanation="У вас есть потенциал для интересного знакомства и обмена опытом.",
                icebreaker="Что привело тебя на это мероприятие?"
            )
        else:
            return MatchResult(
                compatibility_score=0.5,
                match_type=MatchType.FRIENDSHIP,
                explanation="You have potential for an interesting connection and knowledge exchange.",
                icebreaker="What brings you to this event?"
            )

    async def generate_icebreaker(
        self,
        user_a: Dict[str, Any],
        user_b: Dict[str, Any],
        match_type: str
    ) -> str:
        """Generate conversation starter"""

        prompt = f"""Generate one interesting question to start a conversation between two people.

Person A is interested in: {', '.join(user_a.get('interests', []))}
Person B is interested in: {', '.join(user_b.get('interests', []))}
Type of connection: {match_type}

The question should be:
- Open-ended (not yes/no)
- Related to shared interests
- Light and friendly
- No clichés like "tell me about yourself"

Respond with ONLY the question, no preamble."""

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content.strip()

    async def chat(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1000
    ) -> str:
        """Generic chat completion for any prompt"""
        response = await self.client.chat.completions.create(
            model=model or self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
