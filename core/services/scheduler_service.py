"""
Periodic scheduler — sends reminders and triggers games in communities.
Runs as an asyncio background task alongside the bot polling loop.
"""

import asyncio
import logging
import random
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Varied reminder templates — bot personality, not robotic
REMINDER_TEMPLATES = [
    "Hey {community_name}! Just a friendly nudge — there are {member_count} people here who might be your next favorite person. Tap the button to find out who.",
    "Quick question for {community_name}: When was the last time you met someone truly interesting? Let me fix that.",
    "{member_count} people in {community_name} and you haven't found your match yet? Let's change that.",
    "Sphere update for {community_name}: I've been observing and I have some ideas about who you should meet. Come say hi in DM.",
    "Reminder: I'm still here, still matching, and still better at introductions than your friends. — Sphere",
]


class SchedulerService:
    """Manages periodic community reminders and game scheduling."""

    def __init__(self, community_repo, bot):
        self.community_repo = community_repo
        self.bot = bot
        self._running = False

    async def run(self):
        """Main scheduler loop. Check communities every hour."""
        self._running = True
        logger.info("[SCHEDULER] Started — checking communities every hour")

        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"[SCHEDULER] Tick failed: {e}", exc_info=True)

            # Sleep 1 hour between checks
            await asyncio.sleep(3600)

    async def stop(self):
        self._running = False

    async def _tick(self):
        """One scheduler cycle: check all communities for due reminders."""
        communities = await self.community_repo.get_all_active()
        now = datetime.now(timezone.utc)

        for community in communities:
            settings = community.settings or {}
            if not settings.get("reminder_enabled", True):
                continue

            reminder_hours = settings.get("reminder_hours", 48)
            last_reminder_str = settings.get("last_reminder_at")

            # Parse last reminder time
            if last_reminder_str:
                try:
                    last_reminder = datetime.fromisoformat(last_reminder_str)
                    if last_reminder.tzinfo is None:
                        last_reminder = last_reminder.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    last_reminder = None
            else:
                last_reminder = None

            # Check if reminder is due
            if last_reminder:
                hours_since = (now - last_reminder).total_seconds() / 3600
                if hours_since < reminder_hours:
                    continue

            # Skip communities with very few members
            if community.member_count < 2:
                continue

            # Send reminder
            await self._send_reminder(community)

            # Update last_reminder_at in settings
            updated_settings = dict(settings)
            updated_settings["last_reminder_at"] = now.isoformat()
            try:
                await self.community_repo.update_settings(community.id, updated_settings)
            except Exception as e:
                logger.warning(f"[SCHEDULER] Failed to update reminder timestamp for {community.id}: {e}")

    async def _send_reminder(self, community):
        """Send a varied reminder message to a community group."""
        template = random.choice(REMINDER_TEMPLATES)
        text = template.format(
            community_name=community.name or "this group",
            member_count=community.member_count,
        )

        # Add deep link button
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        bot_info = await self.bot.get_me()
        deep_link = f"https://t.me/{bot_info.username}?start=community_{community.id}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Find your match", url=deep_link)],
        ])

        try:
            await self.bot.send_message(
                community.telegram_group_id,
                text,
                reply_markup=keyboard,
            )
            logger.info(f"[SCHEDULER] Sent reminder to {community.name} ({community.telegram_group_id})")
        except Exception as e:
            logger.warning(f"[SCHEDULER] Failed to send reminder to {community.telegram_group_id}: {e}")
