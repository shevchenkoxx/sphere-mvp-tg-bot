"""
OpenAI GPT service implementation.
Handles user analysis and match compatibility using GPT-4.
"""

import json
import re
from typing import Dict, Any
from openai import AsyncOpenAI
from core.domain.models import MatchResult, MatchType
from core.interfaces.ai import IAIService
from config.settings import settings


class OpenAIService(IAIService):
    """OpenAI GPT-based AI service for user analysis and matching"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"  # Fast and cheap, good for MVP

    async def generate_user_summary(self, user_data: Dict[str, Any]) -> str:
        """Generate AI summary of user profile for matching system"""

        # Build context
        name = user_data.get('display_name') or 'Not specified'
        interests = ', '.join(user_data.get('interests', [])) or 'None'
        goals = ', '.join(user_data.get('goals', [])) or 'None'
        bio = user_data.get('bio') or 'Not specified'
        looking_for = user_data.get('looking_for') or ''
        can_help_with = user_data.get('can_help_with') or ''

        prompt = f"""Create a brief, informative profile summary for a networking matching system.

User data:
- Name: {name}
- Interests: {interests}
- Goals: {goals}
- Bio: {bio}
- Looking for: {looking_for}
- Can help with: {can_help_with}

Create a 2-3 sentence summary highlighting:
1. Key personality traits (based on interests)
2. What they're looking for (based on goals)
3. Potential connection points with others

Write in third person, warm but informative. No emojis.
Keep the response in the same language as the bio (detect from bio text)."""

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content

    async def analyze_match(
        self,
        user_a: Dict[str, Any],
        user_b: Dict[str, Any],
        event_context: str = None
    ) -> MatchResult:
        """Analyze compatibility between two users"""

        # Build profiles
        name_a = user_a.get('display_name') or user_a.get('first_name') or 'Anonymous'
        name_b = user_b.get('display_name') or user_b.get('first_name') or 'Anonymous'

        prompt = f"""Analyze compatibility between two people for potential networking connection.

=== PERSON A ===
Name: {name_a}
Interests: {', '.join(user_a.get('interests', []))}
Goals: {', '.join(user_a.get('goals', []))}
Bio: {user_a.get('bio', 'Not specified')}
Looking for: {user_a.get('looking_for', '')}
Can help with: {user_a.get('can_help_with', '')}
AI profile: {user_a.get('ai_summary', 'No data')}

=== PERSON B ===
Name: {name_b}
Interests: {', '.join(user_b.get('interests', []))}
Goals: {', '.join(user_b.get('goals', []))}
Bio: {user_b.get('bio', 'Not specified')}
Looking for: {user_b.get('looking_for', '')}
Can help with: {user_b.get('can_help_with', '')}
AI profile: {user_b.get('ai_summary', 'No data')}

{f'Context: both are at event "{event_context}"' if event_context else ''}

Determine:
1. compatibility_score (0.0-1.0) — how interesting they could be to each other
2. match_type — one of: "friendship", "professional", "romantic", "creative"
3. explanation — why they might be interesting to each other (2-3 sentences, warm and human, WITHOUT mentioning names)
4. icebreaker — one good question to start a conversation

IMPORTANT: Respond with valid JSON only, no markdown:
{{"compatibility_score": 0.75, "match_type": "friendship", "explanation": "...", "icebreaker": "..."}}"""

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

        try:
            data = json.loads(text)
            return MatchResult(
                compatibility_score=data["compatibility_score"],
                match_type=MatchType(data["match_type"]),
                explanation=data["explanation"],
                icebreaker=data["icebreaker"]
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            # Fallback on parse error
            return MatchResult(
                compatibility_score=0.5,
                match_type=MatchType.FRIENDSHIP,
                explanation="У вас есть общие интересы, которые могут стать основой для интересного общения.",
                icebreaker="Что привело тебя на это мероприятие?"
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
