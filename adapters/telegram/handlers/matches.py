"""
Matches handler - viewing and interacting with matches.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

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
    get_matches_photo_keyboard,
)
from adapters.telegram.states.onboarding import MatchesPhotoStates, MatchFeedbackStates
from config.features import Features
from core.utils.language import detect_lang
import logging

logger = logging.getLogger(__name__)
router = Router()


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
        logger.error(f"find_matches failed for user {user.id}: {e}", exc_info=True)
        await status.edit_text(
            "Something went wrong. Please try again later." if lang == "en"
            else "Что-то пошло не так. Попробуй позже."
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


async def list_matches_callback(callback: CallbackQuery, index: int = 0, event_id=None, city: str = None, state: FSMContext = None):
    """Show user's matches via callback, optionally filtered by event or city"""
    lang = detect_lang(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        msg = "Profile not found" if lang == "en" else "Профиль не найден"
        await callback.answer(msg, show_alert=True)
        return

    # Store matching context in FSM state for pagination
    if state:
        await state.update_data(
            matching_city=city,
            matching_event_id=str(event_id) if event_id else None,
        )

    # Check if user has no photo - ask for one before showing matches
    if not user.photo_url and state:
        # Store context for after photo
        await state.update_data(
            matches_index=index,
            matches_event_id=str(event_id) if event_id else None,
            matching_city=city,
        )
        await state.set_state(MatchesPhotoStates.waiting_photo)

        if lang == "ru":
            text = (
                "📸 <b>Добавь фото!</b>\n\n"
                "Твои матчи смогут легко найти тебя на ивенте.\n"
                "Отправь своё фото или нажми 'Позже'."
            )
        else:
            text = (
                "📸 <b>Add your photo!</b>\n\n"
                "Your matches will be able to easily find you at the event.\n"
                "Send your photo or tap 'Later'."
            )

        await callback.message.edit_text(text, reply_markup=get_matches_photo_keyboard(lang))
        await callback.answer()
        return

    await callback.answer()  # Answer early to avoid Telegram timeout
    await show_matches(callback.message, user.id, lang=lang, edit=True, index=index, event_id=event_id, city=city)


async def show_matches(message: Message, user_id, lang: str = "en", edit: bool = False, index: int = 0, event_id=None, city: str = None):
    """Display user's matches with detailed profiles and pagination"""
    matches = await matching_service.get_user_matches(user_id, MatchStatus.PENDING)

    # Filter by city (Sphere City mode) or event
    if city:
        matches = [m for m in matches if m.event_id is None and m.city and m.city.lower() == city.lower()]
    elif event_id:
        event_id_str = str(event_id)
        matches = [m for m in matches if str(m.event_id) == event_id_str]

    # If no matches, try to create them automatically
    if not matches:
        user = await user_service.get_user(user_id)

        # City mode: try to find city matches
        if city and user:
            loading_text = (
                "✨ Sphere is finding people in your city..."
            ) if lang == "en" else (
                "✨ Sphere ищет интересных людей в твоём городе..."
            )
            if not edit:
                status_msg = await message.answer(loading_text)

            try:
                new_matches = await matching_service.find_city_matches(
                    user=user,
                    limit=5
                )

                # Re-fetch matches from DB
                matches = await matching_service.get_user_matches(user_id, MatchStatus.PENDING)
                matches = [m for m in matches if m.event_id is None and m.city and m.city.lower() == city.lower()]

            except Exception as e:
                logger.error(f"City matching failed for user {user_id}: {e}")

            if not edit and 'status_msg' in locals():
                try:
                    await status_msg.delete()
                except Exception:
                    pass

        # Event mode: try to find event matches
        elif user and user.current_event_id:
            # Show loading message (only for new messages, not edits to avoid double-flash)
            loading_text = (
                "✨ Sphere is finding your best matches..."
            ) if lang == "en" else (
                "✨ Sphere подбирает для тебя лучшие матчи..."
            )
            if not edit:
                status_msg = await message.answer(loading_text)

            try:
                # Run matching for this user
                from config.features import Features

                if user.profile_embedding:
                    new_matches = await matching_service.find_matches_vector(
                        user=user,
                        event_id=user.current_event_id,
                        limit=Features.SHOW_TOP_MATCHES
                    )
                else:
                    new_matches = await matching_service.find_and_create_matches_for_user(
                        user=user,
                        event_id=user.current_event_id,
                        limit=Features.SHOW_TOP_MATCHES
                    )

                # Notify admin about new matches
                if new_matches:
                    user_name = user.display_name or user.first_name or "Someone"
                    admin_info = [
                        (
                            p.display_name or p.first_name or "?",
                            p.username,
                            r.compatibility_score if hasattr(r, 'compatibility_score') else "?",
                            str(r.match_id)
                        )
                        for p, r in new_matches
                    ]
                    await notify_admin_new_matches(
                        user_name=user_name,
                        user_username=user.username,
                        matches_info=admin_info
                    )

                # Re-fetch matches from DB
                matches = await matching_service.get_user_matches(user_id, MatchStatus.PENDING)
                if event_id:
                    event_id_str = str(event_id)
                    matches = [m for m in matches if str(m.event_id) == event_id_str]

            except Exception as e:
                logger.error(f"Auto-matching failed for user {user_id}: {e}")

            # Clean up loading message if we sent one
            if not edit and 'status_msg' in locals():
                try:
                    await status_msg.delete()
                except Exception:
                    pass

    # Still no matches after trying
    if not matches:
        user = await user_service.get_user(user_id) if not locals().get('user') else user

        if city:
            # City mode - no matches in this city
            if lang == "ru":
                text = (
                    f"🏙️ <b>Sphere City — {city}</b>\n\n"
                    "Пока нет матчей в твоём городе.\n\n"
                    "💡 Как только появятся новые люди — ты получишь уведомление!"
                )
            else:
                text = (
                    f"🏙️ <b>Sphere City — {city}</b>\n\n"
                    "No matches in your city yet.\n\n"
                    "💡 You'll be notified when new people join!"
                )
        else:
            # Event mode - determine specific reason
            has_event = user and user.current_event_id
            has_profile = user and user.bio and user.looking_for
            participant_count = 0
            if has_event:
                try:
                    participants = await event_service.get_event_participants(user.current_event_id)
                    participant_count = len(participants) if participants else 0
                except Exception:
                    pass

            if lang == "ru":
                text = "<b>💫 Твои матчи</b>\n\n"
                if not has_event:
                    text += "Ты ещё не присоединился к ивенту.\nСканируй QR-код или присоединись через ссылку!"
                elif participant_count <= 1:
                    text += "Пока на ивенте мало участников.\nМатчи появятся, когда присоединятся другие!"
                elif not has_profile:
                    text += (
                        "Профиль пока не заполнен до конца.\n\n"
                        "💡 <b>Совет:</b> Добавь информацию — чем ищешь, чем можешь помочь. "
                        "Это поможет найти релевантных людей!"
                    )
                else:
                    text += (
                        "Пока нет подходящих матчей.\n\n"
                        "💡 Попробуй позже — новые участники присоединяются постоянно!"
                    )
            else:
                text = "<b>💫 Your Matches</b>\n\n"
                if not has_event:
                    text += "You haven't joined an event yet.\nScan a QR code or join via link!"
                elif participant_count <= 1:
                    text += "Not many people at this event yet.\nMatches will appear when others join!"
                elif not has_profile:
                    text += (
                        "Your profile isn't complete yet.\n\n"
                        "💡 <b>Tip:</b> Add what you're looking for and how you can help. "
                        "This helps find better matches!"
                    )
                else:
                    text += (
                        "No matches found yet.\n\n"
                        "💡 Try again later — new people are joining all the time!"
                    )

        # Create keyboard with "Add more info" button
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        btn_text = "✏️ Add more info" if lang == "en" else "✏️ Добавить инфо"
        builder.button(text=btn_text, callback_data="edit_my_profile")
        builder.button(text="🔄 Try again", callback_data="retry_matching")
        builder.button(text="◀️ Menu" if lang == "en" else "◀️ Меню", callback_data="back_to_menu")
        builder.adjust(1)

        if edit:
            await message.edit_text(text, reply_markup=builder.as_markup())
        else:
            await message.answer(text, reply_markup=builder.as_markup())
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

    # Get current user for "both here" check
    current_user = await user_service.get_user(user_id)

    # Build partner profile display - rich card style
    name = partner.display_name or partner.first_name or ("Anonymous" if lang == "en" else "Аноним")
    header = "Match" if lang == "en" else "Матч"

    # Header with match counter
    text = f"<b>💫 {header} {index + 1}/{total_matches}</b>"

    # "Both here" badge — same event
    if (current_user and current_user.current_event_id and partner.current_event_id
            and str(current_user.current_event_id) == str(partner.current_event_id)):
        badge = "  📍 Вы оба здесь!" if lang == "ru" else "  📍 You're both here!"
        text += badge
    text += "\n\n"

    # Name with username
    text += f"<b>{name}</b>"
    if partner.username:
        text += f"  •  @{partner.username}"
    text += "\n"

    # Profession + Company as subtitle
    profession = getattr(partner, 'profession', None)
    company = getattr(partner, 'company', None)
    if profession or company:
        subtitle = ""
        if profession:
            subtitle += profession
        if company:
            subtitle += f" @ {company}" if profession else company
        text += f"🏢 {subtitle}\n"

    # City + Experience level
    city = getattr(partner, 'city_current', None)
    exp_level = getattr(partner, 'experience_level', None)
    if city or exp_level:
        location_line = ""
        if city:
            location_line += f"📍 {city}"
        if exp_level:
            exp_labels = {"junior": "Junior", "mid": "Middle", "senior": "Senior", "founder": "Founder", "executive": "Executive"}
            exp_display = exp_labels.get(exp_level, exp_level.title())
            location_line += f"  •  {exp_display}" if city else exp_display
        text += f"{location_line}\n"

    # Bio - main description
    if partner.bio:
        text += f"\n{partner.bio}\n"

    # Interests as hashtags (up to 7)
    all_hashtags = []
    if partner.interests:
        all_hashtags.extend([f"#{i}" for i in partner.interests[:7]])

    # Skills as additional hashtags
    skills = getattr(partner, 'skills', None)
    if skills:
        all_hashtags.extend([f"#{s.replace(' ', '_')}" for s in skills[:5]])

    if all_hashtags:
        # Remove duplicates and limit
        unique_hashtags = list(dict.fromkeys(all_hashtags))[:10]
        text += f"\n{' '.join(unique_hashtags)}\n"

    # Divider
    text += "\n" + "─" * 20 + "\n"

    # Looking for
    if partner.looking_for:
        label = "🔍 Looking for" if lang == "en" else "🔍 Ищет"
        text += f"\n<b>{label}</b>\n{partner.looking_for}\n"

    # Can help with
    if partner.can_help_with:
        label = "💡 Can help with" if lang == "en" else "💡 Может помочь"
        text += f"\n<b>{label}</b>\n{partner.can_help_with}\n"

    # Goals
    if partner.goals:
        goals_labels = {
            "networking": "🤝 Networking",
            "cofounders": "👥 Co-founders",
            "mentorship": "🎓 Mentorship",
            "business": "💼 Business",
            "friends": "👋 Friends",
            "creative": "🎨 Creative",
            "learning": "📚 Learning",
            "hiring": "💼 Hiring",
            "investing": "💰 Investing"
        }
        goals_display = " ".join([goals_labels.get(g, g) for g in partner.goals[:4]])
        text += f"\n🎯 {goals_display}\n"

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
        lang=lang,
        partner_username=partner.username,
    )

    # Send photo with profile as caption (if photo exists)
    if partner.photo_url:
        # Telegram caption limit is 1024 chars - truncate if needed
        caption_text = text
        if len(caption_text) > 1024:
            caption_text = caption_text[:1020] + "..."

        try:
            if edit:
                # For pagination: delete old message, send new with photo
                try:
                    await message.delete()
                except Exception:
                    pass
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=partner.photo_url,
                caption=caption_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return  # Photo sent with caption, no need for separate text
        except Exception as e:
            # If photo fails, fall back to text-only
            logger.warning(f"Failed to send match photo for user {user_id}: {type(e).__name__}: {str(e)[:100]}")

    # Text-only (no photo or photo failed)
    if edit:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except Exception:
            # If edit fails (e.g. was a photo message), delete and send new
            try:
                await message.delete()
            except Exception:
                pass
            await bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode="HTML")
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

    if not user:
        msg = "User not found" if lang == "en" else "Пользователь не найден"
        await callback.answer(msg, show_alert=True)
        return

    partner_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    partner = await user_service.get_user(partner_id)

    if not partner:
        msg = "Partner profile not found" if lang == "en" else "Профиль партнёра не найден"
        await callback.answer(msg, show_alert=True)
        return

    partner_mention = f"@{partner.username}" if partner.username else ""

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

    # Handle photo messages (can't edit_text on a photo) — delete and send new
    if callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await bot.send_message(
            callback.message.chat.id, text,
            reply_markup=get_chat_keyboard(match_id, lang),
            parse_mode="HTML"
        )
    else:
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
        text += f"\n{partner.bio}\n"

    # Interests as hashtags
    if partner.interests:
        hashtags = " ".join([f"#{i}" for i in partner.interests[:5]])
        text += f"\n{hashtags}\n"

    # Divider
    text += "\n" + "─" * 20 + "\n"

    # Looking for
    if partner.looking_for:
        label = "🔍 Looking for" if lang == "en" else "🔍 Ищет"
        text += f"\n<b>{label}</b>\n{partner.looking_for}\n"

    # Can help with
    if partner.can_help_with:
        label = "💡 Can help with" if lang == "en" else "💡 Может помочь"
        text += f"\n<b>{label}</b>\n{partner.can_help_with}\n"

    # Goals - compact at bottom
    if partner.goals:
        goals_display = " • ".join([get_goal_display(g, lang) for g in partner.goals[:3]])
        text += f"\n🎯 {goals_display}\n"

    # Send photo with profile as caption (if photo exists)
    if partner.photo_url:
        # Telegram caption limit is 1024 chars
        caption_text = text
        if len(caption_text) > 1024:
            caption_text = caption_text[:1020] + "..."

        try:
            await callback.message.delete()
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=partner.photo_url,
                caption=caption_text,
                reply_markup=get_profile_view_keyboard(match_id, lang, partner_username=partner.username),
                parse_mode="HTML"
            )
        except Exception:
            # Fallback to just text
            await callback.message.edit_text(text, reply_markup=get_profile_view_keyboard(match_id, lang, partner_username=partner.username))
    else:
        await callback.message.edit_text(text, reply_markup=get_profile_view_keyboard(match_id, lang, partner_username=partner.username))

    await callback.answer()


@router.callback_query(F.data == "back_to_matches")
async def back_to_matches(callback: CallbackQuery, state: FSMContext):
    """Go back to matches list — handle photo messages gracefully"""
    lang = detect_lang(callback)
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM, str(callback.from_user.id)
    )
    if not user:
        await callback.answer("Profile not found", show_alert=True)
        return

    # Restore matching context from state
    city = None
    event_id = user.current_event_id
    if state:
        data = await state.get_data()
        city = data.get("matching_city")
        if city:
            event_id = None  # City mode, no event filter

    # If current message is a photo (from view_profile), delete and send new text
    if callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer()
        await show_matches(callback.message, user.id, lang=lang, edit=False, event_id=event_id, city=city)
    else:
        await callback.answer()
        await show_matches(callback.message, user.id, lang=lang, edit=True, event_id=event_id, city=city)


@router.callback_query(F.data == "retry_matching")
async def retry_matching(callback: CallbackQuery, state: FSMContext):
    """Retry finding matches"""
    lang = detect_lang(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer("Profile not found", show_alert=True)
        return

    # Check matching context from state
    city = None
    if state:
        data = await state.get_data()
        city = data.get("matching_city")

    # City mode or event mode
    if not city and not user.current_event_id:
        msg = "Join an event first!" if lang == "en" else "Сначала присоединись к ивенту!"
        await callback.answer(msg, show_alert=True)
        return

    # Answer callback IMMEDIATELY to avoid Telegram 30s timeout
    await callback.answer()

    # Show loading
    await callback.message.edit_text(
        "🔄 Searching for matches..." if lang == "en" else "🔄 Ищу матчи..."
    )

    try:
        if city:
            # City mode: find city matches
            await matching_service.find_city_matches(user=user, limit=5, force_new=True)
            await show_matches(callback.message, user.id, lang=lang, edit=True, city=city)
        else:
            # Event mode
            from config.features import Features

            if user.profile_embedding:
                matches = await matching_service.find_matches_vector(
                    user=user,
                    event_id=user.current_event_id,
                    limit=Features.SHOW_TOP_MATCHES
                )
            else:
                matches = await matching_service.find_and_create_matches_for_user(
                    user=user,
                    event_id=user.current_event_id,
                    limit=Features.SHOW_TOP_MATCHES
                )

            await show_matches(callback.message, user.id, lang=lang, edit=True, event_id=user.current_event_id)

    except Exception as e:
        logger.error(f"Retry matching failed: {e}", exc_info=True)
        await callback.message.edit_text(
            "Something went wrong. Please try again." if lang == "en"
            else "Что-то пошло не так. Попробуй ещё раз.",
            reply_markup=get_back_to_menu_keyboard(lang)
        )


@router.callback_query(F.data.startswith("match_prev_"))
async def match_prev(callback: CallbackQuery, state: FSMContext):
    """Navigate to previous match"""
    await callback.answer()
    try:
        current_index = int(callback.data.replace("match_prev_", ""))
    except ValueError:
        return
    new_index = max(0, current_index - 1)

    # Restore matching context from state
    city = None
    event_id = None
    if state:
        data = await state.get_data()
        city = data.get("matching_city")
        event_id = data.get("matching_event_id")

    await list_matches_callback(callback, index=new_index, city=city, event_id=event_id, state=state)


@router.callback_query(F.data.startswith("match_next_"))
async def match_next(callback: CallbackQuery, state: FSMContext):
    """Navigate to next match"""
    await callback.answer()
    try:
        current_index = int(callback.data.replace("match_next_", ""))
    except ValueError:
        return
    new_index = current_index + 1

    # Restore matching context from state
    city = None
    event_id = None
    if state:
        data = await state.get_data()
        city = data.get("matching_city")
        event_id = data.get("matching_event_id")

    await list_matches_callback(callback, index=new_index, city=city, event_id=event_id, state=state)


@router.callback_query(F.data == "match_counter")
async def match_counter_click(callback: CallbackQuery):
    """Handle click on counter (no action)"""
    await callback.answer()


# === AI SPEED DATING ===

@router.callback_query(F.data.startswith("speed_dating_"))
async def speed_dating_preview(callback: CallbackQuery):
    """Generate or show AI speed dating conversation preview"""
    lang = detect_lang(callback)

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


# === PHOTO REQUEST IN MATCHES ===

@router.message(MatchesPhotoStates.waiting_photo, F.photo)
async def handle_matches_photo(message: Message, state: FSMContext):
    """Handle photo upload when opening matches"""
    lang = detect_lang(message)
    user_id = str(message.from_user.id)

    try:
        # Get the largest photo
        photo = message.photo[-1]

        # Save photo URL
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            user_id,
            photo_url=photo.file_id
        )

        if lang == "ru":
            await message.answer("✅ Фото сохранено!")
        else:
            await message.answer("✅ Photo saved!")

    except Exception as e:
        logger.error(f"Failed to save photo for user {user_id}: {e}")

    # Continue to show matches
    data = await state.get_data()
    await state.clear()

    user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)
    index = data.get("matches_index", 0)
    event_id = data.get("matches_event_id")

    await show_matches(message, user.id, lang=lang, edit=False, index=index, event_id=event_id)


@router.callback_query(F.data == "skip_matches_photo")
async def skip_matches_photo(callback: CallbackQuery, state: FSMContext):
    """Skip photo and show matches"""
    lang = detect_lang(callback)
    await callback.answer()

    data = await state.get_data()
    await state.clear()

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    index = data.get("matches_index", 0)
    event_id = data.get("matches_event_id")

    await show_matches(callback.message, user.id, lang=lang, edit=True, index=index, event_id=event_id)


@router.message(MatchesPhotoStates.waiting_photo, F.text)
async def handle_matches_photo_text(message: Message, state: FSMContext):
    """Handle text when expecting photo"""
    lang = detect_lang(message)

    text_lower = message.text.lower()
    if text_lower in ["skip", "пропуск", "позже", "later", "нет", "no"]:
        # Skip photo
        data = await state.get_data()
        await state.clear()

        user = await user_service.get_user_by_platform(
            MessagePlatform.TELEGRAM,
            str(message.from_user.id)
        )

        index = data.get("matches_index", 0)
        event_id = data.get("matches_event_id")

        await show_matches(message, user.id, lang=lang, edit=False, index=index, event_id=event_id)
    else:
        if lang == "ru":
            await message.answer("📸 Отправь фото или напиши 'позже'")
        else:
            await message.answer("📸 Send a photo or type 'later'")


# === FEEDBACK ===

@router.callback_query(F.data.startswith("feedback_"))
async def handle_feedback(callback: CallbackQuery, state: FSMContext):
    """Handle match feedback (good/bad) - saves to database, asks for voice feedback"""
    from infrastructure.database.supabase_client import supabase
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    lang = detect_lang(callback)

    # Guard: prevent double-click race condition
    current_state = await state.get_state()
    if current_state == MatchFeedbackStates.waiting_voice_feedback.state:
        await callback.answer("Already recorded!" if lang == "en" else "Уже записано!")
        return

    # Parse callback: feedback_good_{match_id} or feedback_bad_{match_id}
    parts = callback.data.split("_")
    feedback_type = parts[1]  # "good" or "bad"
    match_id = "_".join(parts[2:])  # match UUID

    # Get user
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer("Error", show_alert=True)
        return

    try:
        # Save feedback to database (upsert - update if exists)
        supabase.table("match_feedback").upsert({
            "match_id": match_id,
            "user_id": str(user.id),
            "feedback_type": feedback_type
        }, on_conflict="match_id,user_id").execute()

        logger.info(f"Feedback saved: user={user.id}, match={match_id}, type={feedback_type}")

        await callback.answer()

        # DON'T remove buttons from match card — keep them for navigation
        # Instead, send auto-deleting thank-you message

        # Ask for voice feedback (auto-deletes after 3 seconds)
        if lang == "ru":
            voice_ask = (
                "Спасибо за оценку! 🙏\n\n"
                "Хочешь рассказать подробнее? Просто запиши голосовое 🎤\n"
                "Или нажми кнопку ниже чтобы пропустить"
            )
        else:
            voice_ask = (
                "Thanks for the feedback! 🙏\n\n"
                "Want to share more? Just record a voice message 🎤\n"
                "Or tap the button below to skip"
            )

        skip_kb = InlineKeyboardBuilder()
        skip_kb.button(
            text="⏭ Skip" if lang == "en" else "⏭ Пропустить",
            callback_data="skip_voice_feedback"
        )

        voice_ask_msg = await callback.message.answer(voice_ask, reply_markup=skip_kb.as_markup())

        # Set state for voice feedback
        await state.set_state(MatchFeedbackStates.waiting_voice_feedback)
        await state.update_data(
            feedback_match_id=match_id,
            feedback_type=feedback_type,
            feedback_lang=lang,
            voice_ask_msg_id=voice_ask_msg.message_id,
            voice_ask_chat_id=voice_ask_msg.chat.id
        )

    except Exception as e:
        logger.error(f"Feedback save error: {e}")
        await callback.answer("Thanks for feedback!" if lang == "en" else "Спасибо за отзыв!")


@router.callback_query(F.data == "skip_voice_feedback")
async def skip_voice_feedback(callback: CallbackQuery, state: FSMContext):
    """Skip voice feedback — auto-delete the ask message after 3s"""
    import asyncio
    lang = detect_lang(callback)
    await state.clear()

    skip_text = "Got it! 👍" if lang == "en" else "Принято! 👍"
    try:
        await callback.message.edit_text(skip_text)
    except Exception:
        pass

    await callback.answer()

    # Auto-delete after 3 seconds
    async def _auto_delete():
        await asyncio.sleep(3)
        try:
            await callback.message.delete()
        except Exception:
            pass

    asyncio.create_task(_auto_delete())


@router.message(MatchFeedbackStates.waiting_voice_feedback, F.voice)
async def handle_voice_feedback(message: Message, state: FSMContext):
    """Handle voice feedback after match rating — transcribe and save"""
    from infrastructure.database.supabase_client import supabase
    from adapters.telegram.loader import voice_service

    data = await state.get_data()
    match_id = data.get("feedback_match_id")
    lang = data.get("feedback_lang", "en")

    if not match_id:
        await state.clear()
        await message.answer("Something went wrong. Please try again." if lang == "en" else "Что-то пошло не так. Попробуй ещё раз.")
        return

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )
    if not user:
        await state.clear()
        return

    voice_file_id = message.voice.file_id

    # Transcribe the voice message
    transcription = None
    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcription = await voice_service.download_and_transcribe(file_url)
        logger.info(f"Voice feedback transcribed: user={user.id}, match={match_id}, text={transcription[:100] if transcription else 'empty'}")
    except Exception as e:
        logger.error(f"Voice feedback transcription error: {e}", exc_info=True)

    # Save voice feedback to DB
    try:
        update_data = {
            "voice_file_id": voice_file_id,
        }
        if transcription:
            update_data["voice_transcription"] = transcription

        supabase.table("match_feedback").update(update_data).eq(
            "match_id", match_id
        ).eq(
            "user_id", str(user.id)
        ).execute()

        logger.info(f"Voice feedback saved: user={user.id}, match={match_id}")
    except Exception as e:
        logger.error(f"Voice feedback save error: {e}", exc_info=True)

    # Delete the voice ask message
    voice_ask_msg_id = data.get("voice_ask_msg_id")
    voice_ask_chat_id = data.get("voice_ask_chat_id")
    if voice_ask_msg_id and voice_ask_chat_id:
        try:
            await bot.delete_message(voice_ask_chat_id, voice_ask_msg_id)
        except Exception:
            pass

    await state.clear()

    import asyncio
    thank_text = "Записали! Спасибо за подробный фидбэк 🙏" if lang == "ru" else "Got it! Thanks for the detailed feedback 🙏"
    thank_msg = await message.answer(thank_text)

    # Auto-delete thank-you after 3 seconds
    async def _auto_delete():
        await asyncio.sleep(3)
        try:
            await thank_msg.delete()
        except Exception:
            pass

    asyncio.create_task(_auto_delete())


@router.message(MatchFeedbackStates.waiting_voice_feedback, F.text)
async def handle_text_in_voice_feedback(message: Message, state: FSMContext):
    """Text sent while waiting for voice feedback — save as text feedback and clear state"""
    from infrastructure.database.supabase_client import supabase

    data = await state.get_data()
    match_id = data.get("feedback_match_id")
    lang = data.get("feedback_lang", "en")

    if not match_id:
        await state.clear()
        await message.answer("Something went wrong. Please try again." if lang == "en" else "Что-то пошло не так. Попробуй ещё раз.")
        return

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )
    if not user:
        await state.clear()
        return

    # Save text feedback to DB
    try:
        supabase.table("match_feedback").update({
            "feedback_text": message.text
        }).eq(
            "match_id", match_id
        ).eq(
            "user_id", str(user.id)
        ).execute()
        logger.info(f"Text feedback saved: user={user.id}, match={match_id}")
    except Exception as e:
        logger.error(f"Text feedback save error: {e}", exc_info=True)

    # Delete the voice ask message
    voice_ask_msg_id = data.get("voice_ask_msg_id")
    voice_ask_chat_id = data.get("voice_ask_chat_id")
    if voice_ask_msg_id and voice_ask_chat_id:
        try:
            await bot.delete_message(voice_ask_chat_id, voice_ask_msg_id)
        except Exception:
            pass

    await state.clear()

    import asyncio
    thank_text = "Записали! Спасибо за фидбэк 🙏" if lang == "ru" else "Got it! Thanks for the feedback 🙏"
    thank_msg = await message.answer(thank_text)

    # Auto-delete thank-you after 3 seconds
    async def _auto_delete():
        await asyncio.sleep(3)
        try:
            await thank_msg.delete()
        except Exception:
            pass

    asyncio.create_task(_auto_delete())


@router.message(MatchFeedbackStates.waiting_voice_feedback)
async def handle_unexpected_in_voice_feedback(message: Message, state: FSMContext):
    """Catch non-voice, non-text messages (photo/sticker/etc) in feedback state"""
    lang = detect_lang(message)
    if lang == "ru":
        await message.answer("🎤 Запиши голосовое сообщение или напиши текст")
    else:
        await message.answer("🎤 Send a voice message or type your feedback")


# === NOTIFICATIONS ===

async def notify_about_match(
    user_telegram_id: int,
    partner_name: str,
    explanation: str,
    icebreaker: str,
    match_id: str,
    lang: str = "en",
    partner_username: str = None
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
            parse_mode="HTML",
            reply_markup=get_match_keyboard(
                match_id, lang=lang, partner_username=partner_username
            )
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_telegram_id}: {e}")


async def send_followup_checkin(
    user_telegram_id: int,
    user_name: str,
    match_count: int,
    event_name: str,
    lang: str = "en"
):
    """Send follow-up check-in message after matches were delivered (always English)"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    text = (
        f"👋 <b>{user_name}, how's {event_name} going?</b>\n\n"
        f"You got {match_count} match{'es' if match_count != 1 else ''}. Met anyone yet?\n\n"
        "• Already met? Rate the match 👍/👎 on the card\n"
        "• Want more? Update your profile and I'll find even better matches!\n"
        "\n🎁 <i>Remember: successful matches enter the draw for a free dinner from Sphere!</i>"
    )
    builder.button(text="💫 My Matches", callback_data="my_matches")
    builder.button(text="✏️ Update Profile", callback_data="my_profile")
    builder.button(text="🔄 Find More", callback_data="retry_matching")
    builder.adjust(1)

    try:
        await bot.send_message(
            user_telegram_id,
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Failed to send follow-up to {user_telegram_id}: {e}")


async def notify_admin_new_matches(
    user_name: str,
    user_username: str,
    matches_info: list,
    event_name: str = None
):
    """Notify admin about every new match created.
    matches_info: list of (partner_name, partner_username, score, match_id)
    """
    from config.settings import settings as app_settings

    if not app_settings.admin_telegram_ids:
        return

    for admin_id in app_settings.admin_telegram_ids:
        try:
            lines = [f"🔔 <b>New matches for {user_name}</b> (@{user_username or '?'})"]
            if event_name:
                lines.append(f"📍 Event: {event_name}")
            lines.append("")

            for i, (p_name, p_username, score, m_id) in enumerate(matches_info, 1):
                score_str = f"{score:.0%}" if isinstance(score, float) else str(score)
                lines.append(f"{i}. <b>{p_name}</b> (@{p_username or '?'}) — {score_str}")

            lines.append(f"\n📊 Total: {len(matches_info)} matches")

            await bot.send_message(
                admin_id,
                "\n".join(lines),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id} about matches: {e}")
