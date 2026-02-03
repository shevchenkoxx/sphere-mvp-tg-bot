"""
Matches handler - viewing and interacting with matches.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from core.domain.models import MessagePlatform, MatchStatus
from core.domain.constants import get_interest_display, get_goal_display
from adapters.telegram.loader import (
    matching_service, user_service, event_service, bot,
    speed_dating_service, speed_dating_repo
)
from adapters.telegram.keyboards import (
    get_match_keyboard,
    get_chat_keyboard,
    get_main_menu_keyboard,
    get_back_to_menu_keyboard,
    get_profile_view_keyboard,
    get_matches_menu_keyboard,
    get_speed_dating_result_keyboard,
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
        # Use vector matching if user has embeddings (faster, more efficient)
        user_has_embeddings = user.profile_embedding is not None

        if user_has_embeddings:
            matches = await matching_service.find_matches_vector(
                user=user,
                event_id=event.id,
                limit=Features.SHOW_TOP_MATCHES
            )
        else:
            # Fallback to old O(n²) method if no embeddings
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
    """Show newly created matches - clean card style"""
    header = (
        f"🎯 <b>Found {len(matches)} matches at {event_name}</b>\n"
        if lang == "en" else
        f"🎯 <b>Найдено {len(matches)} матчей на {event_name}</b>\n"
    )
    header += "─" * 20 + "\n"

    lines = []

    for i, (matched_user, match_result) in enumerate(matches):
        name = matched_user.display_name or matched_user.first_name or "Anonymous"

        # Build clean card for each match
        line = f"\n<b>{i+1}. {name}</b>"
        if matched_user.username:
            line += f"  •  @{matched_user.username}"

        # Hashtags - compact
        if matched_user.interests:
            hashtags = " ".join([f"#{x}" for x in matched_user.interests[:3]])
            line += f"\n{hashtags}"

        # Why matched - brief
        line += f"\n<i>✨ {match_result.explanation[:70]}...</i>"

        lines.append(line)

    text = header + "\n".join(lines)

    # Add icebreaker from first match
    if matches:
        text += "\n\n" + "─" * 20
        icebreaker = matches[0][1].icebreaker
        icebreaker_label = "💬 Start with" if lang == "en" else "💬 Начни с"
        text += f"\n<b>{icebreaker_label}</b>\n<i>{icebreaker}</i>"

    await message.answer(text, reply_markup=get_main_menu_keyboard(lang))


async def list_matches_callback(callback: CallbackQuery, index: int = 0, event_id=None):
    """Show user's matches via callback, optionally filtered by event"""
    lang = detect_lang(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        msg = "Profile not found" if lang == "en" else "Профиль не найден"
        await callback.answer(msg, show_alert=True)
        return

    await show_matches(callback.message, user.id, lang=lang, edit=True, index=index, event_id=event_id)
    await callback.answer()


async def show_matches(message: Message, user_id, lang: str = "en", edit: bool = False, index: int = 0, event_id=None):
    """Display user's matches with detailed profiles and pagination"""
    matches = await matching_service.get_user_matches(user_id, MatchStatus.PENDING)

    # Filter by event if specified
    if event_id:
        matches = [m for m in matches if m.event_id == event_id]

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

    # Ensure index is valid
    total_matches = len(matches)
    if index >= total_matches:
        index = total_matches - 1
    if index < 0:
        index = 0

    # Show match at current index
    match = matches[index]

    # Determine partner
    partner_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
    partner = await user_service.get_user(partner_id)

    if not partner:
        error_msg = "Match partner profile not found" if lang == "en" else "Профиль партнёра не найден"
        if edit:
            await message.edit_text(error_msg, reply_markup=get_back_to_menu_keyboard(lang))
        else:
            await message.answer(error_msg, reply_markup=get_main_menu_keyboard(lang))
        return

    # Build partner profile display - clean card style
    name = partner.display_name or partner.first_name or ("Anonymous" if lang == "en" else "Аноним")
    header = "Match" if lang == "en" else "Матч"

    # Header with match counter
    text = f"<b>💫 {header} {index + 1}/{total_matches}</b>\n\n"

    # Name with username
    text += f"<b>{name}</b>"
    if partner.username:
        text += f"  •  @{partner.username}"
    text += "\n"

    # Bio - main description
    if partner.bio:
        bio_text = partner.bio[:150] + ('...' if len(partner.bio) > 150 else '')
        text += f"\n{bio_text}\n"

    # Interests as hashtags
    if partner.interests:
        hashtags = " ".join([f"#{i}" for i in partner.interests[:5]])
        text += f"\n{hashtags}\n"

    # Divider
    text += "\n" + "─" * 20 + "\n"

    # Looking for
    if partner.looking_for:
        label = "🔍 Looking for" if lang == "en" else "🔍 Ищет"
        looking_text = partner.looking_for[:100] + ('...' if len(partner.looking_for) > 100 else '')
        text += f"\n<b>{label}</b>\n{looking_text}\n"

    # Can help with
    if partner.can_help_with:
        label = "💡 Can help with" if lang == "en" else "💡 Может помочь"
        help_text = partner.can_help_with[:100] + ('...' if len(partner.can_help_with) > 100 else '')
        text += f"\n<b>{label}</b>\n{help_text}\n"

    # Divider before match insights
    text += "\n" + "─" * 20 + "\n"

    # Why match - AI explanation prominently displayed
    why_label = "✨ Why this match" if lang == "en" else "✨ Почему этот матч"
    text += f"\n<b>{why_label}</b>\n<i>{match.ai_explanation}</i>\n"

    # Icebreaker
    icebreaker_label = "💬 Start with" if lang == "en" else "💬 Начни с"
    text += f"\n<b>{icebreaker_label}</b>\n<i>{match.icebreaker}</i>"

    keyboard = get_match_keyboard(
        match_id=str(match.id),
        current_index=index,
        total_matches=total_matches,
        lang=lang
    )

    # Send photo if partner has one
    if partner.photo_url and not edit:
        try:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=partner.photo_url,
                caption=f"📸 {name}"
            )
        except Exception as e:
            # Log photo send failure for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send match partner photo for user {user_id}: {type(e).__name__}: {str(e)[:100]}")

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


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

    # Get partner username for direct contact
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )
    partner_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    partner = await user_service.get_user(partner_id)
    partner_mention = f"@{partner.username}" if partner and partner.username else ""

    if lang == "ru":
        text = (
            "<b>Готово к общению!</b>\n\n"
            f"Напиши напрямую: {partner_mention}\n\n"
            f"<b>Начни с:</b> <i>{match.icebreaker}</i>"
        )
    else:
        text = (
            "<b>Ready to connect!</b>\n\n"
            f"Message directly: {partner_mention}\n\n"
            f"<b>Start with:</b> <i>{match.icebreaker}</i>"
        )

    await callback.message.edit_text(text, reply_markup=get_chat_keyboard(match_id, lang))
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

    # Build detailed profile - clean card style
    name = partner.display_name or partner.first_name or ("Anonymous" if lang == "en" else "Аноним")

    # Header with name and contact
    text = f"<b>{name}</b>"
    if partner.username:
        text += f"  •  @{partner.username}"
    text += "\n"

    # Bio - the main description
    if partner.bio:
        bio_text = partner.bio[:200] + ('...' if len(partner.bio) > 200 else '')
        text += f"\n{bio_text}\n"

    # Interests as hashtags
    if partner.interests:
        hashtags = " ".join([f"#{i}" for i in partner.interests[:5]])
        text += f"\n{hashtags}\n"

    # Divider
    text += "\n" + "─" * 20 + "\n"

    # Looking for
    if partner.looking_for:
        label = "🔍 Looking for" if lang == "en" else "🔍 Ищет"
        looking_text = partner.looking_for[:150] + ('...' if len(partner.looking_for) > 150 else '')
        text += f"\n<b>{label}</b>\n{looking_text}\n"

    # Can help with
    if partner.can_help_with:
        label = "💡 Can help with" if lang == "en" else "💡 Может помочь"
        help_text = partner.can_help_with[:150] + ('...' if len(partner.can_help_with) > 150 else '')
        text += f"\n<b>{label}</b>\n{help_text}\n"

    # Goals - compact at bottom
    if partner.goals:
        goals_display = " • ".join([get_goal_display(g, lang) for g in partner.goals[:3]])
        text += f"\n🎯 {goals_display}\n"

    # Send photo if partner has one, then text
    if partner.photo_url:
        try:
            # Delete old message and send new with photo
            await callback.message.delete()
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=partner.photo_url,
                caption=f"📸 {name}"
            )
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=get_profile_view_keyboard(match_id, lang)
            )
        except Exception:
            # Fallback to just text
            await callback.message.edit_text(text, reply_markup=get_profile_view_keyboard(match_id, lang))
    else:
        await callback.message.edit_text(text, reply_markup=get_profile_view_keyboard(match_id, lang))

    await callback.answer()


@router.callback_query(F.data == "back_to_matches")
async def back_to_matches(callback: CallbackQuery):
    """Go back to matches list"""
    await list_matches_callback(callback)


@router.callback_query(F.data.startswith("match_prev_"))
async def match_prev(callback: CallbackQuery):
    """Navigate to previous match"""
    current_index = int(callback.data.replace("match_prev_", ""))
    new_index = max(0, current_index - 1)
    await list_matches_callback(callback, index=new_index)


@router.callback_query(F.data.startswith("match_next_"))
async def match_next(callback: CallbackQuery):
    """Navigate to next match"""
    current_index = int(callback.data.replace("match_next_", ""))
    new_index = current_index + 1
    await list_matches_callback(callback, index=new_index)


@router.callback_query(F.data == "match_counter")
async def match_counter_click(callback: CallbackQuery):
    """Handle click on counter (no action)"""
    await callback.answer()


# === AI SPEED DATING ===

@router.callback_query(F.data.startswith("speed_dating_"))
async def speed_dating_preview(callback: CallbackQuery):
    """Generate or show AI speed dating conversation preview"""
    lang = detect_lang(callback)
    import logging
    logger = logging.getLogger(__name__)

    # Parse callback data: speed_dating_{id} or speed_dating_regen_{id}
    data = callback.data
    regenerate = "regen" in data
    match_id = data.replace("speed_dating_regen_", "").replace("speed_dating_", "")

    # Get current user
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        msg = "User not found" if lang == "en" else "Пользователь не найден"
        await callback.answer(msg, show_alert=True)
        return

    # Get match
    match = await matching_service.get_match(match_id)
    if not match:
        msg = "Match not found" if lang == "en" else "Матч не найден"
        await callback.answer(msg, show_alert=True)
        return

    # Determine partner
    partner_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    partner = await user_service.get_user(partner_id)

    if not partner:
        msg = "Partner profile not found" if lang == "en" else "Профиль партнёра не найден"
        await callback.answer(msg, show_alert=True)
        return

    # Check cache (skip if regenerating)
    if not regenerate:
        try:
            cached = await speed_dating_repo.get_conversation(match.id, user.id)
            if cached:
                # Show cached conversation
                name_a = user.display_name or user.first_name or "You"
                name_b = partner.display_name or partner.first_name or "Partner"
                formatted = speed_dating_service.format_for_telegram(
                    cached.conversation_text, name_a, name_b, lang
                )
                await callback.message.edit_text(
                    formatted,
                    reply_markup=get_speed_dating_result_keyboard(match_id, lang)
                )
                await callback.answer()
                return
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            # Continue to generate new conversation

    # Show loading message
    loading_text = "Generating conversation preview..." if lang == "en" else "Генерирую превью разговора..."
    try:
        await callback.message.edit_text(f"🤖 {loading_text}")
    except Exception:
        pass  # Message might not be editable

    await callback.answer()

    try:
        # Generate conversation
        conversation = await speed_dating_service.generate_conversation(
            user_a=user,
            user_b=partner,
            match_context=None,  # Could add event name here if available
            language=lang
        )

        # Cache the conversation
        try:
            await speed_dating_repo.save_conversation(
                match_id=match.id,
                viewer_user_id=user.id,
                conversation_text=conversation,
                language=lang
            )
        except Exception as e:
            logger.warning(f"Failed to cache conversation: {e}")
            # Continue even if caching fails

        # Format and show result
        name_a = user.display_name or user.first_name or "You"
        name_b = partner.display_name or partner.first_name or "Partner"
        formatted = speed_dating_service.format_for_telegram(conversation, name_a, name_b, lang)

        await callback.message.edit_text(
            formatted,
            reply_markup=get_speed_dating_result_keyboard(match_id, lang)
        )

    except Exception as e:
        logger.error(f"Speed dating generation failed: {e}")
        error_text = (
            "Failed to generate preview. Please try again."
            if lang == "en" else
            "Не удалось создать превью. Попробуйте ещё раз."
        )
        await callback.message.edit_text(
            f"❌ {error_text}",
            reply_markup=get_speed_dating_result_keyboard(match_id, lang)
        )


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
