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
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
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

        # Detect language from user content if not provided
        if not language:
            language = self._detect_language(bio_a, bio_b, looking_for_a, looking_for_b, can_help_a, can_help_b)

        lang_instruction = "Russian" if language == "ru" else "English"

        prompt = f"""Analyze compatibility between two people for networking.

CRITICAL: Base your analysis ONLY on what users ACTUALLY stated. Do NOT invent or assume interests/skills not mentioned.

=== PERSON A: {name_a} ===
Bio (their words): {bio_a or 'Not provided'}
Looking for: {looking_for_a or 'Not specified'}
Can help with: {can_help_a or 'Not specified'}
Interests: {', '.join(interests_a) if interests_a else 'None listed'}

=== PERSON B: {name_b} ===
Bio (their words): {bio_b or 'Not provided'}
Looking for: {looking_for_b or 'Not specified'}
Can help with: {can_help_b or 'Not specified'}
Interests: {', '.join(interests_b) if interests_b else 'None listed'}

{f'Event context: "{event_context}"' if event_context else ''}

MATCHING RULES:
1. PRIMARY: Match "can_help_with" of one person to "looking_for" of another (mutual value exchange)
2. SECONDARY: Shared interests ONLY if explicitly listed by BOTH users
3. Use ONLY information explicitly stated in bio/looking_for/can_help_with
4. Do NOT mention interests that only one person has
5. If data is sparse, focus on general networking potential at the event

LANGUAGE: Write explanation and icebreaker in {lang_instruction}.

Return JSON:
{{
  "compatibility_score": 0.0-1.0,
  "match_type": "friendship" | "professional" | "creative" | "romantic",
  "explanation": "2-3 sentences in {lang_instruction} about why they could benefit from meeting. Reference ONLY what they actually stated. Do NOT use names.",
  "icebreaker": "One conversation starter in {lang_instruction} based on their actual shared interests or complementary needs"
}}

IMPORTANT: If someone's bio mentions 'AI' but NOT 'crypto', do NOT mention crypto in explanation.
Respond with valid JSON only, no markdown."""

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
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse match analysis JSON: {text[:300] if 'text' in dir() else 'no response'} Error: {e}")
        except KeyError as e:
            logger.error(f"Missing key in match analysis response: {e}")
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
