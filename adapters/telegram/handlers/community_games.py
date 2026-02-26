"""
Community games handler — inline button responses and game posting.

Callback data format:
  game_{session_id}_{action}
  game_{session_id}_vote_{option_index}
  game_{session_id}_guess_{option_index}
"""

import logging
from typing import Optional
from uuid import UUID

from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from core.domain.models import GameSession

logger = logging.getLogger(__name__)

router = Router()


# -----------------------------------------------------------------
# Post games to group chat (called by game_service / scheduler)
# -----------------------------------------------------------------

async def post_game_to_group(bot: Bot, chat_id: int, session: GameSession,
                              game_data: dict) -> Optional[int]:
    """Post a game message to a group. Returns the message_id."""
    game_type = session.game_type
    session_id = str(session.id)

    if game_type == "mystery_profile":
        return await _post_mystery_profile(bot, chat_id, session_id, game_data)
    elif game_type == "this_or_that":
        return await _post_this_or_that(bot, chat_id, session_id, game_data)
    elif game_type == "vibe_check":
        return await _post_vibe_check(bot, chat_id, session_id, game_data)
    elif game_type == "hot_take":
        return await _post_hot_take(bot, chat_id, session_id, game_data)
    elif game_type == "common_ground":
        return await _post_common_ground(bot, chat_id, session_id, game_data)

    return None


async def _post_mystery_profile(bot: Bot, chat_id: int, session_id: str,
                                 game_data: dict) -> Optional[int]:
    clues = game_data.get("clues", [])
    options = game_data.get("options", [])

    clues_text = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(clues))
    text = (
        f"<b>Mystery Profile</b>\n\n"
        f"Someone in this group matches these clues:\n\n"
        f"{clues_text}\n\n"
        f"Who is it? Vote below!"
    )

    buttons = []
    for i, name in enumerate(options):
        buttons.append([InlineKeyboardButton(
            text=name,
            callback_data=f"game_{session_id}_guess_{i}",
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
        return msg.message_id
    except Exception as e:
        logger.error(f"[GAME] Failed to post mystery_profile: {e}")
        return None


async def _post_this_or_that(bot: Bot, chat_id: int, session_id: str,
                              game_data: dict) -> Optional[int]:
    question = game_data.get("question", "This or That?")
    option_a = game_data.get("option_a", "A")
    option_b = game_data.get("option_b", "B")

    text = (
        f"<b>This or That?</b>\n\n"
        f"{question}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{option_a}", callback_data=f"game_{session_id}_vote_0"),
            InlineKeyboardButton(text=f"{option_b}", callback_data=f"game_{session_id}_vote_1"),
        ],
    ])

    try:
        msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
        return msg.message_id
    except Exception as e:
        logger.error(f"[GAME] Failed to post this_or_that: {e}")
        return None


async def _post_vibe_check(bot: Bot, chat_id: int, session_id: str,
                            game_data: dict) -> Optional[int]:
    question = game_data.get("question", "Vibe check!")
    options = game_data.get("options", [])

    text = (
        f"<b>Vibe Check</b>\n\n"
        f"{question}"
    )

    buttons = []
    for i, opt in enumerate(options):
        buttons.append([InlineKeyboardButton(
            text=opt,
            callback_data=f"game_{session_id}_vote_{i}",
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
        return msg.message_id
    except Exception as e:
        logger.error(f"[GAME] Failed to post vibe_check: {e}")
        return None


async def _post_hot_take(bot: Bot, chat_id: int, session_id: str,
                          game_data: dict) -> Optional[int]:
    statement = game_data.get("statement", "Hot take!")

    text = (
        f"<b>Hot Take</b>\n\n"
        f"<i>\"{statement}\"</i>\n\n"
        f"What do you think?"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Agree", callback_data=f"game_{session_id}_vote_0"),
            InlineKeyboardButton(text="Disagree", callback_data=f"game_{session_id}_vote_1"),
        ],
    ])

    try:
        msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
        return msg.message_id
    except Exception as e:
        logger.error(f"[GAME] Failed to post hot_take: {e}")
        return None


async def _post_common_ground(bot: Bot, chat_id: int, session_id: str,
                               game_data: dict) -> Optional[int]:
    overlaps = game_data.get("overlaps", [])
    user_a_name = game_data.get("user_a_name", "Someone")
    user_b_name = game_data.get("user_b_name", "Someone else")

    # Tease without revealing who
    overlap_text = "\n".join(f"  - {o}" for o in overlaps[:3])
    text = (
        f"<b>Common Ground Detected!</b>\n\n"
        f"Two people in this group have something surprising in common:\n\n"
        f"{overlap_text}\n\n"
        f"Curious who? Tap to reveal!"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Reveal the pair",
            callback_data=f"game_{session_id}_reveal",
        )],
    ])

    try:
        msg = await bot.send_message(chat_id, text, reply_markup=keyboard)
        return msg.message_id
    except Exception as e:
        logger.error(f"[GAME] Failed to post common_ground: {e}")
        return None


# -----------------------------------------------------------------
# Callback handlers — user interactions with games
# -----------------------------------------------------------------

@router.callback_query(F.data.startswith("game_"))
async def handle_game_callback(callback: CallbackQuery):
    """Route all game callbacks to the appropriate handler."""
    from adapters.telegram.loader import game_service, game_repo, user_repo, community_service, bot

    data = callback.data
    parts = data.split("_", 2)  # game_{uuid part}_{action...}

    # Parse: game_{session_id}_{action}_{param}
    # Session IDs are UUIDs so they contain hyphens, not underscores
    # Format: game_<uuid>_<action>_<param>
    # We need to extract UUID which is 36 chars
    prefix = "game_"
    rest = data[len(prefix):]

    # Find the action part — UUID is 36 chars (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
    if len(rest) < 37:
        await callback.answer("Invalid game data")
        return

    session_id_str = rest[:36]
    action_str = rest[37:]  # skip the underscore after UUID

    try:
        session_id = UUID(session_id_str)
    except ValueError:
        await callback.answer("Invalid game session")
        return

    session = await game_repo.get_session(session_id)
    if not session:
        await callback.answer("Game not found")
        return

    if session.status != "active" and not action_str.startswith("reveal"):
        await callback.answer("This game has ended!")
        return

    # Get the user's internal ID
    user = await user_repo.get_by_platform_id("telegram", str(callback.from_user.id))
    if not user:
        # User not registered — prompt to onboard
        bot_info = await bot.get_me()
        community = await community_service.get_community_for_group(callback.message.chat.id) if callback.message else None
        if community:
            deep_link = community_service.generate_deep_link(community.id, bot_info.username)
        else:
            deep_link = f"https://t.me/{bot_info.username}?start=organic"

        await callback.answer(
            "Join Sphere first! Tap the link below.",
            show_alert=True,
        )
        return

    game_data = session.game_data or {}

    if action_str.startswith("guess_"):
        await _handle_mystery_guess(callback, session, game_data, user, action_str)
    elif action_str.startswith("vote_"):
        await _handle_vote(callback, session, game_data, user, action_str)
    elif action_str == "reveal":
        await _handle_reveal(callback, session, game_data)
    else:
        await callback.answer("Unknown action")


async def _handle_mystery_guess(callback: CallbackQuery, session: GameSession,
                                 game_data: dict, user, action_str: str):
    """Handle a mystery profile guess."""
    from adapters.telegram.loader import game_service, bot

    try:
        guess_index = int(action_str.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid guess")
        return

    correct_index = game_data.get("correct_index", -1)
    is_correct = guess_index == correct_index

    # Check if already guessed
    existing = await game_service.game_repo.get_user_response(session.id, user.id)
    if existing:
        await callback.answer("You already guessed!")
        return

    # Record response
    await game_service.submit_response(
        session.id, user.id,
        response={"guess_index": guess_index, "is_correct": is_correct},
        is_correct=is_correct,
    )

    if is_correct:
        mystery_name = game_data.get("mystery_name", "???")
        await callback.answer(f"Correct! It's {mystery_name}!", show_alert=True)
    else:
        await callback.answer("Not quite! Try to figure it out...", show_alert=False)


async def _handle_vote(callback: CallbackQuery, session: GameSession,
                        game_data: dict, user, action_str: str):
    """Handle votes for This or That, Vibe Check, Hot Take."""
    from adapters.telegram.loader import game_service, game_repo, bot

    try:
        vote_index = int(action_str.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid vote")
        return

    # Check if already voted
    existing = await game_repo.get_user_response(session.id, user.id)
    if existing:
        await callback.answer("You already voted!")
        return

    user_id_str = str(user.id)
    user_name = user.display_name or user.first_name or "Someone"

    # Record response
    await game_service.submit_response(
        session.id, user.id,
        response={"vote_index": vote_index},
    )

    # Update vote counts in game_data
    if session.game_type == "this_or_that":
        key = "votes_a" if vote_index == 0 else "votes_b"
        votes = game_data.get(key, [])
        votes.append(user_id_str)
        game_data[key] = votes
        count_a = len(game_data.get("votes_a", []))
        count_b = len(game_data.get("votes_b", []))
        total = count_a + count_b
        await game_repo.update_session(session.id, game_data=game_data)
        option = game_data.get("option_a") if vote_index == 0 else game_data.get("option_b")
        await callback.answer(f"You voted: {option} ({total} votes so far)")

    elif session.game_type == "hot_take":
        key = "agree" if vote_index == 0 else "disagree"
        votes = game_data.get(key, [])
        votes.append(user_id_str)
        game_data[key] = votes
        total = len(game_data.get("agree", [])) + len(game_data.get("disagree", []))
        await game_repo.update_session(session.id, game_data=game_data)
        stance = "Agree" if vote_index == 0 else "Disagree"
        await callback.answer(f"You said: {stance} ({total} votes)")

    elif session.game_type == "vibe_check":
        options = game_data.get("options", [])
        if vote_index < len(options):
            chosen = options[vote_index]
            votes = game_data.get("votes", {})
            vote_list = votes.get(chosen, [])
            vote_list.append(user_id_str)
            votes[chosen] = vote_list
            game_data["votes"] = votes
            total = sum(len(v) for v in votes.values())
            await game_repo.update_session(session.id, game_data=game_data)
            await callback.answer(f"You picked: {chosen} ({total} votes)")
        else:
            await callback.answer("Invalid option")


async def _handle_reveal(callback: CallbackQuery, session: GameSession, game_data: dict):
    """Handle the reveal button for Common Ground."""
    from adapters.telegram.loader import game_repo

    user_a_name = game_data.get("user_a_name", "Someone")
    user_b_name = game_data.get("user_b_name", "Someone else")
    overlaps = game_data.get("overlaps", [])

    overlap_text = "\n".join(f"  - {o}" for o in overlaps)
    text = (
        f"<b>Common Ground Revealed!</b>\n\n"
        f"<b>{user_a_name}</b> and <b>{user_b_name}</b>:\n\n"
        f"{overlap_text}\n\n"
        f"Small world, right?"
    )

    await callback.answer()
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=None)
        except Exception:
            pass  # Message already edited or deleted
    # End the session after reveal
    try:
        await game_repo.end_session(session.id)
    except Exception:
        pass


# -----------------------------------------------------------------
# Game results posting (called when game ends)
# -----------------------------------------------------------------

async def post_game_results(bot: Bot, chat_id: int, session: GameSession,
                             game_data: dict, responses: list):
    """Post game results summary to the group."""
    game_type = session.game_type
    bot_info = await bot.get_me()
    deep_link = f"https://t.me/{bot_info.username}"

    if game_type == "this_or_that":
        count_a = len(game_data.get("votes_a", []))
        count_b = len(game_data.get("votes_b", []))
        total = count_a + count_b
        if total == 0:
            return
        pct_a = round(count_a / total * 100)
        pct_b = round(count_b / total * 100)
        text = (
            f"<b>This or That — Results!</b>\n\n"
            f"{game_data.get('option_a', 'A')}: {pct_a}% ({count_a} votes)\n"
            f"{game_data.get('option_b', 'B')}: {pct_b}% ({count_b} votes)\n\n"
            f"Total: {total} votes"
        )
    elif game_type == "hot_take":
        agree = len(game_data.get("agree", []))
        disagree = len(game_data.get("disagree", []))
        total = agree + disagree
        if total == 0:
            return
        text = (
            f"<b>Hot Take — Results!</b>\n\n"
            f"<i>\"{game_data.get('statement', '')}\"</i>\n\n"
            f"Agree: {agree} | Disagree: {disagree}\n\n"
            f"{'The group agrees!' if agree > disagree else 'Controversial!' if agree == disagree else 'The group disagrees!'}"
        )
    elif game_type == "vibe_check":
        votes = game_data.get("votes", {})
        total = sum(len(v) for v in votes.values())
        if total == 0:
            return
        lines = []
        for opt, voters in sorted(votes.items(), key=lambda x: -len(x[1])):
            pct = round(len(voters) / total * 100)
            lines.append(f"  {opt}: {pct}% ({len(voters)})")
        text = (
            f"<b>Vibe Check — Results!</b>\n\n"
            f"{game_data.get('question', '')}\n\n"
            + "\n".join(lines) +
            f"\n\nTotal: {total} votes"
        )
    elif game_type == "mystery_profile":
        correct_count = sum(1 for r in responses if r.is_correct)
        total = len(responses)
        mystery_name = game_data.get("mystery_name", "???")
        text = (
            f"<b>Mystery Profile — Revealed!</b>\n\n"
            f"It was <b>{mystery_name}</b>!\n\n"
            f"{correct_count}/{total} guessed correctly."
        )
    else:
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Find your match", url=deep_link)],
    ])

    try:
        await bot.send_message(chat_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"[GAME] Failed to post results: {e}")
