"""
Community Pulse — weekly AI-generated digest posted to groups.

Summarizes: top topics, most active members, shared interests, trending conversations.
Generates via gpt-4o-mini and posts with CTA button.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from openai import AsyncOpenAI
from config.settings import settings

logger = logging.getLogger(__name__)


class CommunityPulseService:
    """Generates and posts weekly community digests."""

    def __init__(self, observation_service, community_repo, user_repo):
        self.observation_service = observation_service
        self.community_repo = community_repo
        self.user_repo = user_repo
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)

    async def generate_pulse(self, community_id: UUID, community_name: str) -> Optional[str]:
        """Generate a weekly pulse digest for a community. Returns formatted text."""
        analytics = await self.observation_service.get_community_analytics(str(community_id), days=7)

        if analytics["total"] < 5:
            return None  # Not enough data

        # Get member count
        community = await self.community_repo.get_by_id(community_id)
        member_count = community.member_count if community else 0

        # Format topics for LLM
        topics_str = ", ".join(f"{t['topic']} ({t['count']})" for t in analytics["topics"][:8])
        sentiment = analytics.get("sentiment", "neutral")
        active_users = analytics.get("active_users", 0)

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "You write engaging weekly community digests for a Telegram group. "
                        "Be concise, warm, and data-driven. Use emojis sparingly. "
                        "Format as a short post (max 150 words). Include:\n"
                        "- A catchy headline\n"
                        "- Top 3 trending topics with brief context\n"
                        "- An insight about the community vibe\n"
                        "- A teaser encouraging engagement\n"
                        "End with a call to action."
                    )},
                    {"role": "user", "content": (
                        f"Community: {community_name}\n"
                        f"Members: {member_count}\n"
                        f"Active this week: {active_users}\n"
                        f"Top topics: {topics_str}\n"
                        f"Overall sentiment: {sentiment}\n"
                        f"Total messages analyzed: {analytics['total']}\n"
                    )},
                ],
                max_tokens=300,
                temperature=0.8,
            )
            return response.choices[0].message.content or None
        except Exception as e:
            logger.error(f"[PULSE] Failed to generate digest: {e}")
            return None

    async def generate_and_post(self, community_id: UUID, bot, group_chat_id: int) -> bool:
        """Generate a pulse and post it to the group. Returns True if posted."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        community = await self.community_repo.get_by_id(community_id)
        if not community:
            return False

        text = await self.generate_pulse(community_id, community.name or "this group")
        if not text:
            logger.debug(f"[PULSE] Not enough data for community {community_id}")
            return False

        bot_info = await bot.get_me()
        deep_link = f"https://t.me/{bot_info.username}?start=community_{community_id}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Find your match", url=deep_link)],
        ])

        try:
            await bot.send_message(
                group_chat_id,
                f"<b>Weekly Pulse</b>\n\n{text}",
                reply_markup=keyboard,
            )
            logger.info(f"[PULSE] Posted weekly digest to {community.name}")
            return True
        except Exception as e:
            logger.error(f"[PULSE] Failed to post to {group_chat_id}: {e}")
            return False
