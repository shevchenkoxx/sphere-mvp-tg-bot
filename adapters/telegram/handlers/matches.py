"""
Matches handler - viewing and interacting with matches.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from core.domain.models import MessagePlatform, MatchStatus
from core.domain.constants import get_interest_display
from adapters.telegram.loader import matching_service, user_service, bot
from adapters.telegram.keyboards import (
    get_match_keyboard,
    get_main_menu_keyboard,
    get_back_to_menu_keyboard,
)

router = Router()


@router.message(Command("matches"))
async def list_matches_command(message: Message):
    """Show user's matches via command"""
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )

    if not user:
        await message.answer("Сначала заполни профиль! /start")
        return

    await show_matches(message, user.id, edit=False)


async def list_matches_callback(callback: CallbackQuery):
    """Show user's matches via callback"""
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer("Профиль не найден", show_alert=True)
        return

    await show_matches(callback.message, user.id, edit=True)
    await callback.answer()


async def show_matches(message: Message, user_id, edit: bool = False):
    """Display user's matches"""
    matches = await matching_service.get_user_matches(user_id, MatchStatus.PENDING)

    if not matches:
        text = (
            "<b>Твои матчи</b>\n\n"
            "У тебя пока нет активных матчей.\n"
            "Присоединяйся к ивентам, чтобы найти интересных людей!"
        )
        if edit:
            await message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
        else:
            await message.answer(text, reply_markup=get_main_menu_keyboard())
        return

    # Show first match
    match = matches[0]

    # Determine partner
    partner_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
    partner = await user_service.get_user(partner_id)

    if not partner:
        return

    partner_interests = ', '.join([get_interest_display(i) for i in partner.interests[:3]])

    text = (
        f"<b>Матч!</b>\n\n"
        f"<b>{partner.display_name or 'Аноним'}</b>\n"
        f"{partner.city_current or 'Не указан'}\n"
        f"{partner_interests}\n\n"
        f"<i>{match.ai_explanation}</i>\n\n"
        f"<b>Icebreaker:</b> {match.icebreaker}"
    )

    if len(matches) > 1:
        text += f"\n\n<i>И ещё {len(matches) - 1} матчей</i>"

    if edit:
        await message.edit_text(text, reply_markup=get_match_keyboard(str(match.id)))
    else:
        await message.answer(text, reply_markup=get_match_keyboard(str(match.id)))


@router.callback_query(F.data.startswith("chat_match_"))
async def start_chat_with_match(callback: CallbackQuery):
    """Start chat with match"""
    match_id = callback.data.replace("chat_match_", "")
    match = await matching_service.get_match(match_id)

    if not match:
        await callback.answer("Матч не найден", show_alert=True)
        return

    # Update status to accepted
    if match.status == MatchStatus.PENDING:
        await matching_service.accept_match(match.id)

    await callback.message.edit_text(
        "<b>Чат открыт!</b>\n\n"
        "Напиши сообщение, и я передам его твоему матчу.\n"
        f"Можешь начать с icebreaker: <i>{match.icebreaker}</i>",
        reply_markup=get_match_keyboard(match_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_profile_"))
async def view_match_profile(callback: CallbackQuery):
    """View match partner's profile"""
    match_id = callback.data.replace("view_profile_", "")
    match = await matching_service.get_match(match_id)

    if not match:
        await callback.answer("Матч не найден", show_alert=True)
        return

    # Get current user
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    # Determine partner
    partner_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    partner = await user_service.get_user(partner_id)

    if not partner:
        await callback.answer("Профиль не найден", show_alert=True)
        return

    interests = ', '.join([get_interest_display(i) for i in partner.interests])

    await callback.message.edit_text(
        f"<b>{partner.display_name or 'Аноним'}</b>\n\n"
        f"<b>Город:</b> {partner.city_current or 'Не указан'}\n"
        f"<b>Интересы:</b> {interests}\n"
        f"<b>О себе:</b> {partner.bio or 'Не заполнено'}",
        reply_markup=get_match_keyboard(match_id)
    )
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
    match_id: str
):
    """Send notification about new match"""
    try:
        await bot.send_message(
            user_telegram_id,
            f"<b>У тебя новый матч!</b>\n\n"
            f"Познакомься с <b>{partner_name}</b>\n\n"
            f"<i>{explanation}</i>\n\n"
            f"<b>Icebreaker:</b> {icebreaker}",
            reply_markup=get_match_keyboard(match_id)
        )
    except Exception as e:
        print(f"Failed to notify user {user_telegram_id}: {e}")
