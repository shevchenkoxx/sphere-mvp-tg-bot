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

    def __init__(self, community_repo, bot, game_service=None,
                 observation_service=None, pulse_service=None):
        self.community_repo = community_repo
        self.bot = bot
        self.game_service = game_service
        self.observation_service = observation_service
        self.pulse_service = pulse_service
        self._running = False
        self._tick_count = 0

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
        """One scheduler cycle: check all communities for due reminders and games."""
        self._tick_count += 1
        communities = await self.community_repo.get_all_active()
        now = datetime.now(timezone.utc)

        # --- Process observation queue (every tick = every hour) ---
        if self.observation_service:
            try:
                from adapters.telegram.handlers.community_group import drain_observation_queue
                queue = drain_observation_queue()
                if queue:
                    stored = await self.observation_service.process_queue(queue)
                    logger.info(f"[SCHEDULER] Processed {stored} observations from {len(queue)} queued messages")
            except Exception as e:
                logger.error(f"[SCHEDULER] Observation processing failed: {e}", exc_info=True)

        for community in communities:
            settings = community.settings or {}

            # --- Games: check if a game is due ---
            if self.game_service and settings.get("games_enabled", True):
                await self._maybe_launch_game(community, settings, now)

            # --- Weekly pulse (every 168 ticks ≈ 7 days, or check last_pulse_at) ---
            if self.pulse_service:
                await self._maybe_send_pulse(community, settings, now)

            # --- Reminders ---
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

    async def _maybe_launch_game(self, community, settings: dict, now: datetime):
        """Check if it's time to launch a game in this community."""
        game_hours = settings.get("game_hours", 24)  # Default: 1 game per day
        last_game_str = settings.get("last_game_at")

        if last_game_str:
            try:
                last_game = datetime.fromisoformat(last_game_str)
                if last_game.tzinfo is None:
                    last_game = last_game.replace(tzinfo=timezone.utc)
                hours_since = (now - last_game).total_seconds() / 3600
                if hours_since < game_hours:
                    return
            except (ValueError, TypeError):
                pass

        # Need at least 3 members for games
        if community.member_count < 3:
            return

        try:
            game_type = await self.game_service.schedule_next_game(
                community.id, self.bot, community.telegram_group_id,
            )
            if game_type:
                logger.info(f"[SCHEDULER] Launched {game_type} game in {community.name}")
                updated = dict(settings)
                updated["last_game_at"] = now.isoformat()
                await self.community_repo.update_settings(community.id, updated)
        except Exception as e:
            logger.warning(f"[SCHEDULER] Failed to launch game for {community.id}: {e}")

    async def _maybe_send_pulse(self, community, settings: dict, now: datetime):
        """Check if it's time to send a weekly pulse digest."""
        pulse_days = settings.get("pulse_days", 7)
        last_pulse_str = settings.get("last_pulse_at")

        if last_pulse_str:
            try:
                last_pulse = datetime.fromisoformat(last_pulse_str)
                if last_pulse.tzinfo is None:
                    last_pulse = last_pulse.replace(tzinfo=timezone.utc)
                days_since = (now - last_pulse).total_seconds() / 86400
                if days_since < pulse_days:
                    return
            except (ValueError, TypeError):
                pass

        if community.member_count < 3:
            return

        try:
            posted = await self.pulse_service.generate_and_post(
                community.id, self.bot, community.telegram_group_id,
            )
            if posted:
                logger.info(f"[SCHEDULER] Posted weekly pulse to {community.name}")
                updated = dict(settings)
                updated["last_pulse_at"] = now.isoformat()
                await self.community_repo.update_settings(community.id, updated)
        except Exception as e:
            logger.warning(f"[SCHEDULER] Failed to send pulse for {community.id}: {e}")
