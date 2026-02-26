"""
Community group handler — manages bot lifecycle in Telegram groups.
Handles: bot added/removed, passive message observation, welcome messages.
"""

import logging
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated, Message, InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

router = Router()

# In-memory queue for batch observation processing
_observation_queue: list = []


@router.my_chat_member(F.new_chat_member.status.in_({"member", "administrator"}))
async def on_bot_added(event: ChatMemberUpdated):
    """Bot was added to a group — register community, sync admins, send welcome."""
    from adapters.telegram.loader import community_service, bot

    chat = event.chat
    adder = event.from_user

    logger.info(f"[GROUP] Bot added to group {chat.id} ({chat.title}) by {adder.id} ({adder.username})")

    try:
        community = await community_service.on_bot_added_to_group(
            chat_id=chat.id,
            chat_title=chat.title,
            adder_user_id=adder.id,
        )
    except Exception as e:
        logger.error(f"[GROUP] Failed to register community for {chat.id}: {e}", exc_info=True)
        return

    # Generate deep link for DM onboarding
    bot_info = await bot.get_me()
    deep_link = community_service.generate_deep_link(community.id, bot_info.username)

    # Send welcome message to the group
    welcome_text = (
        f"Hi everyone! I'm <b>Sphere</b> — your community matching assistant.\n\n"
        f"I help members of <b>{chat.title}</b> discover meaningful connections "
        f"with each other based on shared interests, goals, and vibes.\n\n"
        f"Here's how it works:\n"
        f"1. Tap the button below to start a quick chat with me in DM\n"
        f"2. I'll learn about you in a fun 2-minute conversation\n"
        f"3. I'll match you with the most interesting people in this group\n\n"
        f"I'll also pop in from time to time with fun games and insights about your community."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Start matching", url=deep_link)],
    ])

    try:
        await event.answer(welcome_text, reply_markup=keyboard)
    except Exception:
        # answer() on ChatMemberUpdated doesn't work — use bot.send_message
        try:
            await bot.send_message(chat.id, welcome_text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"[GROUP] Failed to send welcome to {chat.id}: {e}")


@router.my_chat_member(F.new_chat_member.status.in_({"left", "kicked"}))
async def on_bot_removed(event: ChatMemberUpdated):
    """Bot was removed from a group — deactivate community."""
    from adapters.telegram.loader import community_service

    chat = event.chat
    logger.info(f"[GROUP] Bot removed from group {chat.id} ({chat.title})")

    try:
        await community_service.on_bot_removed_from_group(chat.id)
    except Exception as e:
        logger.error(f"[GROUP] Failed to deactivate community for {chat.id}: {e}", exc_info=True)


@router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def on_group_message(message: Message):
    """Passively observe text messages in groups for later batch analysis."""
    # Skip very short messages, bot messages, commands
    if not message.text or len(message.text.split()) < 5:
        return
    if message.from_user and message.from_user.is_bot:
        return
    if message.text.startswith("/"):
        return

    from adapters.telegram.loader import community_service

    # Get community for this group
    community = await community_service.get_community_for_group(message.chat.id)
    if not community:
        return

    # Queue for batch processing (observation_service will process periodically)
    _observation_queue.append({
        "community_id": str(community.id),
        "user_tg_id": str(message.from_user.id),
        "text": message.text[:500],  # Cap snippet length
        "chat_id": message.chat.id,
    })

    # Keep queue bounded
    if len(_observation_queue) > 1000:
        _observation_queue.pop(0)


def drain_observation_queue() -> list:
    """Drain and return all queued observations. Called by scheduler."""
    global _observation_queue
    items = list(_observation_queue)
    _observation_queue = []
    return items
