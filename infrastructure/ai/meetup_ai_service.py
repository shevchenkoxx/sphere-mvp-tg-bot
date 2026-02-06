"""
Meetup AI Service - generates personalized "why meet" and discussion topics
for meetup proposals between matched users.
"""

import json
import logging
from typing import Optional, Tuple, List

from openai import AsyncOpenAI
from core.domain.models import User
from config.settings import settings

logger = logging.getLogger(__name__)


class MeetupAIService:

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"

    def _build_persona(self, user: User) -> str:
        parts = [f"Name: {user.display_name or user.first_name or 'Anonymous'}"]
        if user.bio:
            parts.append(f"About: {user.bio[:200]}")
        profession = getattr(user, "profession", None)
        company = getattr(user, "company", None)
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

    async def generate_meetup_content(
        self,
        proposer: User,
        receiver: User,
        match_explanation: Optional[str] = None,
    ) -> Tuple[str, List[str]]:
        """
        Generate why_meet text and 3 discussion topics.

        Returns:
            (why_meet, [topic1, topic2, topic3])
        """
        persona_a = self._build_persona(proposer)
        persona_b = self._build_persona(receiver)

        prompt = f"""Two people matched at a networking event. Generate a short meetup invitation.

=== PROPOSER ===
{persona_a}

=== RECEIVER ===
{persona_b}

{f"Match context: {match_explanation}" if match_explanation else ""}

Return ONLY valid JSON (no markdown fences):
{{
  "why_meet": "2-3 sentences explaining why these two should meet. Be specific to their profiles. Mention concrete overlap or complementary skills.",
  "topics": [
    "First discussion topic (5-12 words, specific to their overlap)",
    "Second discussion topic (5-12 words, actionable)",
    "Third discussion topic (5-12 words, forward-looking)"
  ]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=400,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            data = json.loads(raw)
            why_meet = data.get("why_meet", "")
            topics = data.get("topics", [])[:3]

            if why_meet and topics:
                logger.info("Generated meetup AI content successfully")
                return why_meet, topics

        except Exception as e:
            logger.error(f"Meetup AI generation failed: {e}", exc_info=True)

        # Fallback
        return self._fallback_content(proposer, receiver, match_explanation)

    def _fallback_content(
        self,
        proposer: User,
        receiver: User,
        match_explanation: Optional[str],
    ) -> Tuple[str, List[str]]:
        name_a = proposer.display_name or proposer.first_name or "They"
        name_b = receiver.display_name or receiver.first_name or "You"

        if match_explanation:
            why_meet = match_explanation
        else:
            why_meet = f"{name_a} and {name_b} share overlapping interests and goals. Meeting in person could unlock collaboration opportunities."

        # Build topics from shared interests
        shared = set(proposer.interests or []) & set(receiver.interests or [])
        topics = []
        if shared:
            topics.append(f"Discuss shared interest in {list(shared)[0]}")
        if proposer.looking_for:
            topics.append(f"Explore: {proposer.looking_for[:40]}")
        if proposer.can_help_with:
            topics.append(f"Exchange expertise on {proposer.can_help_with[:30]}")

        # Pad to 3
        defaults = [
            "Share current projects and find synergies",
            "Discuss industry trends and opportunities",
            "Plan potential collaboration next steps",
        ]
        while len(topics) < 3:
            topics.append(defaults[len(topics)])

        return why_meet, topics[:3]
