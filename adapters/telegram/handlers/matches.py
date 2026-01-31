"""
Matches handler - viewing and interacting with matches.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from core.domain.models import MessagePlatform, MatchStatus
from core.domain.constants import get_interest_display
from adapters.telegram.loader import matching_service, user_service, event_service, bot
from adapters.telegram.keyboards import (
    get_match_keyboard,
    get_main_menu_keyboard,
    get_back_to_menu_keyboard,
)
from config.features import Features

router = Router()


def detect_lang(message_or_callback) -> str:
    """Detect language from user settings"""
    if hasattr(message_or_callback, 'from_user'):
        lang_code = message_or_callback.from_user.language_code or "en"
    else:
        lang_code = "en"
    return "ru" if lang_code.startswith(("ru", "uk")) else "en"


@router.message(Command("matches"))
async def list_matches_command(message: Message):
    """Show user's matches via command"""
    lang = detect_lang(message)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )

    if not user:
        text = "Complete your profile first! /start" if lang == "en" else "Сначала заполни профиль! /start"
        await message.answer(text)
        return

    await show_matches(message, user.id, lang=lang, edit=False)


@router.message(Command("find_matches"))
async def find_matches_command(message: Message):
    """Manually trigger matching algorithm for current event"""
    lang = detect_lang(message)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )

    if not user:
        text = "Complete your profile first! /start" if lang == "en" else "Сначала заполни профиль! /start"
        await message.answer(text)
        return

    if not user.current_event_id:
        text = "Join an event first! Scan a QR code." if lang == "en" else "Сначала присоединись к ивенту! Сканируй QR."
        await message.answer(text)
        return

    event = await event_service.get_event_by_id(user.current_event_id)
    if not event:
        text = "Event not found." if lang == "en" else "Ивент не найден."
        await message.answer(text)
        return

    status = await message.answer(
        f"🔍 {'Finding matches at' if lang == 'en' else 'Ищу матчи на'} {event.name}..."
    )

    try:
        matches = await matching_service.find_and_create_matches_for_user(
            user=user,
            event_id=event.id,
            limit=Features.SHOW_TOP_MATCHES
        )

        await status.delete()

        if not matches:
            text = (
                "No new matches found. Try again later when more people join!"
                if lang == "en" else
                "Новых матчей не найдено. Попробуй позже, когда будет больше участников!"
            )
            await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
            return

        # Show matches
        await show_new_matches(message, matches, event.name, lang)

    except Exception as e:
        await status.edit_text(
            f"Error: {str(e)[:100]}" if lang == "en" else f"Ошибка: {str(e)[:100]}"
        )


async def show_new_matches(message: Message, matches: list, event_name: str, lang: str):
    """Show newly created matches"""
    header = (
        f"🎯 <b>Found {len(matches)} matches at {event_name}:</b>\n\n"
        if lang == "en" else
        f"🎯 <b>Найдено {len(matches)} матчей на {event_name}:</b>\n\n"
    )

    lines = []
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    for i, (matched_user, match_result) in enumerate(matches):
        emoji = emojis[i] if i < len(emojis) else f"{i+1}."
        name = matched_user.display_name or matched_user.first_name or "Anonymous"

        # Hashtags
        hashtags = " ".join([f"#{x}" for x in matched_user.interests[:3]]) if matched_user.interests else ""

        line = f"{emoji} <b>{name}</b>"
        if hashtags:
            line += f"\n   {hashtags}"
        line += f"\n   💡 {match_result.explanation[:80]}..."
        if matched_user.username:
            line += f"\n   📱 @{matched_user.username}"

        lines.append(line)

    text = header + "\n\n".join(lines)

    # Add icebreaker from first match
    if matches:
        icebreaker = matches[0][1].icebreaker
        text += f"\n\n💬 <b>{'Start with' if lang == 'en' else 'Начни с'}:</b>\n<i>{icebreaker}</i>"

    await message.answer(text, reply_markup=get_main_menu_keyboard(lang))


async def list_matches_callback(callback: CallbackQuery):
    """Show user's matches via callback"""
    lang = detect_lang(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        msg = "Profile not found" if lang == "en" else "Профиль не найден"
        await callback.answer(msg, show_alert=True)
        return

    await show_matches(callback.message, user.id, lang=lang, edit=True)
    await callback.answer()


async def show_matches(message: Message, user_id, lang: str = "en", edit: bool = False):
    """Display user's matches with detailed profiles"""
    matches = await matching_service.get_user_matches(user_id, MatchStatus.PENDING)

    if not matches:
        if lang == "ru":
            text = (
                "<b>💫 Твои матчи</b>\n\n"
                "Пока нет активных матчей.\n"
                "Присоединяйся к ивентам, чтобы найти интересных людей!"
            )
        else:
            text = (
                "<b>💫 Your Matches</b>\n\n"
                "No active matches yet.\n"
                "Join events to find interesting people!"
            )

        if edit:
            await message.edit_text(text, reply_markup=get_back_to_menu_keyboard(lang))
        else:
            await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
        return

    # Show first match with full details
    match = matches[0]

    # Determine partner
    partner_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
    partner = await user_service.get_user(partner_id)

    if not partner:
        return

    # Build partner profile display
    name = partner.display_name or partner.first_name or ("Anonymous" if lang == "en" else "Аноним")
    text = f"<b>{'Match!' if lang == 'en' else 'Матч!'}</b>\n\n"
    text += f"👤 <b>{name}</b>\n"

    # Hashtag interests
    if partner.interests:
        hashtags = " ".join([f"#{i}" for i in partner.interests[:4]])
        text += f"{hashtags}\n"

    # Bio
    if partner.bio:
        text += f"\n{partner.bio[:120]}{'...' if len(partner.bio) > 120 else ''}\n"

    # Looking for
    if partner.looking_for:
        label = "Looking for" if lang == "en" else "Ищет"
        text += f"\n🔍 <b>{label}:</b> {partner.looking_for[:100]}{'...' if len(partner.looking_for) > 100 else ''}\n"

    # Can help with
    if partner.can_help_with:
        label = "Can help with" if lang == "en" else "Может помочь"
        text += f"\n💪 <b>{label}:</b> {partner.can_help_with[:100]}{'...' if len(partner.can_help_with) > 100 else ''}\n"

    # Why match
    text += f"\n💡 <i>{match.ai_explanation}</i>\n"

    # Icebreaker
    text += f"\n💬 <b>{'Start with' if lang == 'en' else 'Начни с'}:</b>\n<i>{match.icebreaker}</i>"

    # Contact
    if partner.username:
        text += f"\n\n📱 @{partner.username}"

    # More matches count
    if len(matches) > 1:
        more = f"And {len(matches) - 1} more matches" if lang == "en" else f"И ещё {len(matches) - 1} матчей"
        text += f"\n\n<i>{more}</i>"

    if edit:
        await message.edit_text(text, reply_markup=get_match_keyboard(str(match.id)))
    else:
        await message.answer(text, reply_markup=get_match_keyboard(str(match.id)))


@router.callback_query(F.data.startswith("chat_match_"))
async def start_chat_with_match(callback: CallbackQuery):
    """Start chat with match"""
    lang = detect_lang(callback)
    match_id = callback.data.replace("chat_match_", "")
    match = await matching_service.get_match(match_id)

    if not match:
        msg = "Match not found" if lang == "en" else "Матч не найден"
        await callback.answer(msg, show_alert=True)
        return

    # Update status to accepted
    if match.status == MatchStatus.PENDING:
        await matching_service.accept_match(match.id)

    if lang == "ru":
        text = (
            "<b>Чат открыт!</b>\n\n"
            "Напиши сообщение, и я передам его твоему матчу.\n"
            f"Начни с: <i>{match.icebreaker}</i>"
        )
    else:
        text = (
            "<b>Chat started!</b>\n\n"
            "Send a message and I'll forward it to your match.\n"
            f"Start with: <i>{match.icebreaker}</i>"
        )

    await callback.message.edit_text(text, reply_markup=get_match_keyboard(match_id))
    await callback.answer()


@router.callback_query(F.data.startswith("view_profile_"))
async def view_match_profile(callback: CallbackQuery):
    """View match partner's full profile"""
    lang = detect_lang(callback)
    match_id = callback.data.replace("view_profile_", "")
    match = await matching_service.get_match(match_id)

    if not match:
        msg = "Match not found" if lang == "en" else "Матч не найден"
        await callback.answer(msg, show_alert=True)
        return

    # Get current user
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        msg = "User not found" if lang == "en" else "Пользователь не найден"
        await callback.answer(msg, show_alert=True)
        return

    # Determine partner
    partner_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    partner = await user_service.get_user(partner_id)

    if not partner:
        msg = "Profile not found" if lang == "en" else "Профиль не найден"
        await callback.answer(msg, show_alert=True)
        return

    # Build detailed profile
    name = partner.display_name or partner.first_name or ("Anonymous" if lang == "en" else "Аноним")
    text = f"👤 <b>{name}</b>\n"

    # Hashtags
    if partner.interests:
        hashtags = " ".join([f"#{i}" for i in partner.interests[:5]])
        text += f"\n{hashtags}\n"

    # Bio
    if partner.bio:
        label = "About" if lang == "en" else "О себе"
        text += f"\n📝 <b>{label}:</b>\n{partner.bio[:250]}{'...' if len(partner.bio) > 250 else ''}\n"

    # Looking for
    if partner.looking_for:
        label = "Looking for" if lang == "en" else "Ищет"
        text += f"\n🔍 <b>{label}:</b>\n{partner.looking_for[:200]}{'...' if len(partner.looking_for) > 200 else ''}\n"

    # Can help with
    if partner.can_help_with:
        label = "Can help with" if lang == "en" else "Может помочь"
        text += f"\n💪 <b>{label}:</b>\n{partner.can_help_with[:200]}{'...' if len(partner.can_help_with) > 200 else ''}\n"

    # Goals
    if partner.goals:
        label = "Goals" if lang == "en" else "Цели"
        goals_display = ", ".join([get_interest_display(g) for g in partner.goals[:3]])
        text += f"\n🎯 <b>{label}:</b> {goals_display}\n"

    # Contact
    if partner.username:
        text += f"\n📱 @{partner.username}"

    await callback.message.edit_text(text, reply_markup=get_match_keyboard(match_id))
    await callback.answer()


@router.callback_query(F.data == "back_to_matches")
async def back_to_matches(callback: CallbackQuery):
    """Go back to matches list"""
    await list_matches_callback(callback)


# === NOTIFICATIONS ===

async def notify_about_match(
    user_telegram_id: int,
    partner_name: str,
    explanation: str,
    icebreaker: str,
    match_id: str,
    lang: str = "en"
):
    """Send notification about new match"""
    try:
        if lang == "ru":
            text = (
                f"<b>У тебя новый матч!</b>\n\n"
                f"Познакомься с <b>{partner_name}</b>\n\n"
                f"<i>{explanation}</i>\n\n"
                f"<b>Начни с:</b> {icebreaker}"
            )
        else:
            text = (
                f"<b>You have a new match!</b>\n\n"
                f"Meet <b>{partner_name}</b>\n\n"
                f"<i>{explanation}</i>\n\n"
                f"<b>Start with:</b> {icebreaker}"
            )

        await bot.send_message(
            user_telegram_id,
            text,
            reply_markup=get_match_keyboard(match_id)
        )
    except Exception as e:
        print(f"Failed to notify user {user_telegram_id}: {e}")
