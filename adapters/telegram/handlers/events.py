"""
Events handler - event creation and joining.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from core.domain.models import MessagePlatform
from config.settings import settings
from adapters.telegram.loader import event_service, matching_service, user_service, bot, event_parser_service
from adapters.telegram.keyboards import (
    get_event_actions_keyboard,
    get_join_event_keyboard,
    get_main_menu_keyboard,
    get_back_to_menu_keyboard,
    get_event_info_keyboard,
)
from adapters.telegram.states import EventStates, EventInfoStates
from core.utils.language import detect_lang

logger = logging.getLogger(__name__)

router = Router(name="events")

# detect_lang works for both Message and CallbackQuery
detect_lang_callback = detect_lang
detect_lang_message = detect_lang


# === JOIN EVENT BY CODE ===

@router.callback_query(F.data == "enter_event_code")
async def enter_event_code_start(callback: CallbackQuery, state: FSMContext):
    """Start entering event code"""
    logger.info(f"[EVENTS] enter_event_code_start triggered for user {callback.from_user.id}")
    lang = detect_lang_callback(callback)

    if lang == "ru":
        text = (
            "📲 <b>Введи код ивента</b>\n\n"
            "Код обычно указан на QR-коде или в приглашении.\n"
            "Например: <code>TEST2024</code>"
        )
    else:
        text = (
            "📲 <b>Enter event code</b>\n\n"
            "The code is usually on the QR or in the invitation.\n"
            "Example: <code>TEST2024</code>"
        )

    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard(lang))
    await state.update_data(lang=lang)
    await state.set_state(EventStates.waiting_event_code)
    logger.info(f"[EVENTS] State set to EventStates.waiting_event_code for user {callback.from_user.id}")
    await callback.answer()


@router.message(EventStates.waiting_event_code, F.text, ~F.text.startswith("/"))
async def process_event_code(message: Message, state: FSMContext):
    """Process entered event code (ignore commands)"""
    logger.info(f"[EVENTS] process_event_code triggered for user {message.from_user.id}, text: {message.text}")

    current_state = await state.get_state()
    logger.info(f"[EVENTS] Current state: {current_state}")

    data = await state.get_data()
    lang = data.get("lang", detect_lang_message(message))

    # Check for cancel
    if message.text.strip().lower() in ["cancel", "отмена", "back", "назад"]:
        await state.clear()
        if lang == "ru":
            await message.answer("Отменено. Возвращаюсь в меню.", reply_markup=get_main_menu_keyboard(lang))
        else:
            await message.answer("Cancelled. Back to menu.", reply_markup=get_main_menu_keyboard(lang))
        return

    event_code = message.text.strip().upper()
    logger.info(f"[EVENTS] Processing event code: {event_code}")

    # Try to join event
    success, msg, event = await event_service.join_event(
        event_code,
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )

    if success and event:
        # Update current_event_id (convert UUID to string for JSON serialization)
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            str(message.from_user.id),
            current_event_id=str(event.id)
        )

        if lang == "ru":
            text = (
                f"🎉 <b>Ты в ивенте {event.name}!</b>\n\n"
                "Система уже ищет для тебя интересных людей.\n"
                "Напишу, когда найду матчи!"
            )
        else:
            text = (
                f"🎉 <b>You're in {event.name}!</b>\n\n"
                "The system is finding interesting people for you.\n"
                "I'll message you when I find matches!"
            )

        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
        await state.clear()
    else:
        # Wrong code — stay in state, let user try again
        if lang == "ru":
            text = (
                f"❌ Код <b>{event_code}</b> не найден.\n\n"
                "Попробуй ввести другой код или напиши <b>отмена</b>."
            )
        else:
            text = (
                f"❌ Code <b>{event_code}</b> not found.\n\n"
                "Try another code or type <b>cancel</b>."
            )

        await message.answer(text)


# === EVENT CREATION (admin only) ===

@router.message(Command("create_event"))
async def create_event_start(message: Message, state: FSMContext):
    """Start event creation (admin only)"""
    if message.from_user.id not in settings.admin_telegram_ids:
        await message.answer("У тебя нет прав для создания ивентов.")
        return

    await message.answer(
        "<b>Создание нового ивента</b>\n\n"
        "Введи название ивента:"
    )
    await state.set_state(EventStates.waiting_name)


@router.message(EventStates.waiting_name)
async def process_event_name(message: Message, state: FSMContext):
    """Process event name"""
    await state.update_data(event_name=message.text.strip())
    await message.answer("Теперь добавь описание (или отправь /skip):")
    await state.set_state(EventStates.waiting_description)


@router.message(EventStates.waiting_description)
async def process_event_description(message: Message, state: FSMContext):
    """Process event description"""
    description = None if message.text == "/skip" else message.text.strip()
    await state.update_data(event_description=description)
    await message.answer("Укажи локацию (или /skip):")
    await state.set_state(EventStates.waiting_location)


@router.message(EventStates.waiting_location)
async def process_event_location(message: Message, state: FSMContext):
    """Process event location and create event"""
    location = None if message.text == "/skip" else message.text.strip()
    data = await state.get_data()

    # Create event
    event = await event_service.create_event(
        name=data['event_name'],
        organizer_platform=MessagePlatform.TELEGRAM,
        organizer_platform_id=str(message.from_user.id),
        description=data.get('event_description'),
        location=location
    )

    # Generate deep link
    bot_info = await bot.me()
    deep_link = event_service.generate_deep_link(event.code, bot_info.username)

    await message.answer(
        f"<b>Ивент создан!</b>\n\n"
        f"<b>Название:</b> {event.name}\n"
        f"<b>Код:</b> <code>{event.code}</code>\n\n"
        f"<b>Ссылка для QR:</b>\n<code>{deep_link}</code>\n\n"
        "Эту ссылку можно превратить в QR-код и разместить на мероприятии!",
        reply_markup=get_event_actions_keyboard(event.code)
    )

    await state.clear()


# === JOIN EVENT ===

@router.callback_query(F.data.startswith("join_event_"))
async def join_event(callback: CallbackQuery):
    """Join event"""
    event_code = callback.data.replace("join_event_", "")

    success, message_text, event = await event_service.join_event(
        event_code,
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if success and event:
        await callback.message.edit_text(
            f"Ты в ивенте <b>{event.name}</b>!\n\n"
            "Система уже анализирует участников и ищет для тебя интересные знакомства. "
            "Я напишу, когда найду подходящего человека!",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer("Добро пожаловать!")
    else:
        await callback.answer(message_text, show_alert=True)


# === EVENT MANAGEMENT (admin) ===

@router.callback_query(F.data.startswith("event_match_"))
async def run_event_matching(callback: CallbackQuery):
    """Run matching for event"""
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Только админ может запустить матчинг", show_alert=True)
        return

    event_code = callback.data.replace("event_match_", "")
    event = await event_service.get_event_by_code(event_code)

    if not event:
        await callback.answer("Ивент не найден", show_alert=True)
        return

    await callback.answer("Запускаю матчинг...")
    await callback.message.edit_text("<b>Матчинг запущен!</b>\n\nЭто может занять пару минут...")

    # Run matching
    matches_count = await matching_service.create_matches_for_event(event.id)

    await callback.message.edit_text(
        f"<b>Матчинг завершён!</b>\n\n"
        f"Создано матчей: {matches_count}\n\n"
        "Участники получат уведомления о своих матчах.",
        reply_markup=get_event_actions_keyboard(event_code)
    )


@router.callback_query(F.data.startswith("event_stats_"))
async def show_event_stats(callback: CallbackQuery):
    """Show event statistics"""
    event_code = callback.data.replace("event_stats_", "")
    event = await event_service.get_event_by_code(event_code)

    if not event:
        await callback.answer("Ивент не найден", show_alert=True)
        return

    participants = await event_service.get_event_participants(event.id)

    await callback.message.edit_text(
        f"<b>Статистика: {event.name}</b>\n\n"
        f"Участников: {len(participants)}\n"
        f"Локация: {event.location or 'Не указана'}\n"
        f"Код: <code>{event.code}</code>",
        reply_markup=get_event_actions_keyboard(event_code)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("event_participants_"))
async def show_event_participants(callback: CallbackQuery):
    """Show event participants"""
    event_code = callback.data.replace("event_participants_", "")
    event = await event_service.get_event_by_code(event_code)

    if not event:
        await callback.answer("Ивент не найден", show_alert=True)
        return

    participants = await event_service.get_event_participants(event.id)

    if not participants:
        text = "Пока нет участников"
    else:
        text = "<b>Участники:</b>\n\n"
        for p in participants[:20]:
            text += f"• {p.display_name or 'Аноним'} ({p.city_current or '?'})\n"

        if len(participants) > 20:
            text += f"\n... и ещё {len(participants) - 20}"

    await callback.message.edit_text(text, reply_markup=get_event_actions_keyboard(event_code))
    await callback.answer()


# === ADMIN COMMANDS ===

@router.message(Command("stats"))
async def admin_stats(message: Message):
    """
    /stats [event_code] - Show event statistics
    Without code - shows current user's event
    """
    if message.from_user.id not in settings.admin_telegram_ids:
        await message.answer("Admin only")
        return

    # Parse event code from command
    parts = message.text.split(maxsplit=1)
    event_code = parts[1].strip() if len(parts) > 1 else None

    # If no code provided, get user's current event
    if not event_code:
        user = await user_service.get_user_by_platform(
            MessagePlatform.TELEGRAM,
            str(message.from_user.id)
        )
        if user and user.current_event_id:
            event = await event_service.get_event_by_id(user.current_event_id)
            event_code = event.code if event else None

    if not event_code:
        await message.answer("Usage: /stats EVENT_CODE\nOr join an event first.")
        return

    event = await event_service.get_event_by_code(event_code)
    if not event:
        await message.answer(f"Event '{event_code}' not found")
        return

    # Get stats
    participants = await event_service.get_event_participants(event.id)

    # Get matches count
    from infrastructure.database.supabase_client import supabase
    matches_resp = supabase.table("matches").select("id, status").eq("event_id", str(event.id)).execute()
    matches = matches_resp.data or []

    # Get feedback count
    feedback_resp = supabase.table("match_feedback").select("feedback_type").execute()
    all_feedback = feedback_resp.data or []
    good_feedback = len([f for f in all_feedback if f['feedback_type'] == 'good'])
    bad_feedback = len([f for f in all_feedback if f['feedback_type'] == 'bad'])

    # Count by status
    pending = len([m for m in matches if m['status'] == 'pending'])
    accepted = len([m for m in matches if m['status'] == 'accepted'])

    text = f"""<b>📊 Stats: {event.name}</b>

<b>Participants:</b> {len(participants)}
<b>Total Matches:</b> {len(matches)}
├ Pending: {pending}
└ Accepted: {accepted}

<b>Feedback:</b>
├ 👍 Good: {good_feedback}
└ 👎 Bad: {bad_feedback}

<b>Code:</b> <code>{event.code}</code>
<b>Location:</b> {event.location or 'N/A'}
<b>Active:</b> {'Yes' if event.is_active else 'No'}"""

    await message.answer(text)


@router.message(Command("participants"))
async def admin_participants(message: Message):
    """
    /participants [event_code] - List event participants
    """
    if message.from_user.id not in settings.admin_telegram_ids:
        await message.answer("Admin only")
        return

    parts = message.text.split(maxsplit=1)
    event_code = parts[1].strip() if len(parts) > 1 else None

    if not event_code:
        user = await user_service.get_user_by_platform(
            MessagePlatform.TELEGRAM,
            str(message.from_user.id)
        )
        if user and user.current_event_id:
            event = await event_service.get_event_by_id(user.current_event_id)
            event_code = event.code if event else None

    if not event_code:
        await message.answer("Usage: /participants EVENT_CODE")
        return

    event = await event_service.get_event_by_code(event_code)
    if not event:
        await message.answer(f"Event '{event_code}' not found")
        return

    participants = await event_service.get_event_participants(event.id)

    if not participants:
        await message.answer(f"No participants in {event.name}")
        return

    text = f"<b>👥 Participants: {event.name}</b>\n\n"
    for i, p in enumerate(participants[:30], 1):
        name = p.display_name or p.first_name or "Anonymous"
        username = f"@{p.username}" if p.username else ""
        profession = p.profession or ""
        city = p.city_current or ""

        line = f"{i}. <b>{name}</b>"
        if username:
            line += f" {username}"
        if profession or city:
            details = ", ".join(filter(None, [profession, city]))
            line += f"\n   └ {details}"
        text += line + "\n"

    if len(participants) > 30:
        text += f"\n... and {len(participants) - 30} more"

    await message.answer(text)


@router.message(Command("broadcast"))
async def admin_broadcast(message: Message):
    """
    /broadcast <text> - Send message to all participants of current event
    """
    if message.from_user.id not in settings.admin_telegram_ids:
        await message.answer("Admin only")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /broadcast Your message here")
        return

    broadcast_text = parts[1]

    # Get user's current event
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )

    if not user or not user.current_event_id:
        await message.answer("You're not in any event. Join one first.")
        return

    event = await event_service.get_event_by_id(user.current_event_id)
    if not event:
        await message.answer("Event not found")
        return

    participants = await event_service.get_event_participants(event.id)

    if not participants:
        await message.answer("No participants to broadcast to")
        return

    # Send to all participants
    sent = 0
    failed = 0

    status_msg = await message.answer(f"Broadcasting to {len(participants)} participants...")

    for p in participants:
        try:
            await bot.send_message(
                chat_id=int(p.platform_user_id),
                text=f"📢 <b>Event: {event.name}</b>\n\n{broadcast_text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"<b>Broadcast complete!</b>\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


@router.message(Command("event"))
async def admin_event_info(message: Message):
    """
    /event <code> - Show event details
    """
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        # List all active events
        from infrastructure.database.supabase_client import supabase
        events_resp = supabase.table("events").select("*").eq("is_active", True).execute()
        events = events_resp.data or []

        if not events:
            await message.answer("No active events")
            return

        text = "<b>📋 Active Events:</b>\n\n"
        for e in events:
            text += f"• <code>{e['code']}</code> - {e['name']}\n"

        text += "\nUse /event CODE for details"
        await message.answer(text)
        return

    event_code = parts[1].strip().upper()
    event = await event_service.get_event_by_code(event_code)

    if not event:
        await message.answer(f"Event '{event_code}' not found")
        return

    # Generate deep link
    bot_info = await bot.me()
    deep_link = f"https://t.me/{bot_info.username}?start=event_{event.code}"

    text = f"""<b>📅 {event.name}</b>

<b>Code:</b> <code>{event.code}</code>
<b>Location:</b> {event.location or 'N/A'}
<b>Description:</b> {event.description or 'N/A'}
<b>Active:</b> {'Yes' if event.is_active else 'No'}

<b>Deep Link:</b>
<code>{deep_link}</code>

<b>Settings:</b> {event.settings or '{}'}"""

    await message.answer(text, reply_markup=get_event_actions_keyboard(event.code) if message.from_user.id in settings.admin_telegram_ids else None)


# === EVENT INFO MANAGEMENT ===

@router.callback_query(F.data.startswith("event_info_"))
async def show_event_info(callback: CallbackQuery):
    """Show rich event info card"""
    event_code = callback.data.replace("event_info_", "")
    event = await event_service.get_event_by_code(event_code)

    if not event:
        await callback.answer("Event not found", show_alert=True)
        return

    # Get event_info from database
    from infrastructure.database.supabase_client import supabase
    result = supabase.table("events").select("event_info").eq("code", event_code).execute()
    event_info = result.data[0].get("event_info", {}) if result.data else {}

    if not event_info or event_info == {}:
        text = f"<b>📅 {event.name}</b>\n\n"
        text += f"📍 {event.location or 'Location not set'}\n"
        text += f"📝 {event.description or 'No description'}\n\n"
        text += "<i>No detailed info yet. Use 🔗 Import URL to add info from Luma or event page.</i>"
    else:
        text = event_parser_service.format_event_card(event_info, event.name)

    await callback.message.edit_text(text, reply_markup=get_event_info_keyboard(event_code), disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data.startswith("event_import_"))
async def start_event_import(callback: CallbackQuery, state: FSMContext):
    """Start URL import flow"""
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Admin only", show_alert=True)
        return

    event_code = callback.data.replace("event_import_", "")

    await state.update_data(import_event_code=event_code)
    await state.set_state(EventInfoStates.waiting_import_url)

    await callback.message.edit_text(
        "<b>🔗 Import Event Info</b>\n\n"
        "Send me a URL to the event page (Luma, Eventbrite, or any website).\n\n"
        "I'll extract:\n"
        "• Description\n"
        "• Schedule\n"
        "• Speakers\n"
        "• Topics\n"
        "• Organizer info\n\n"
        "Send /cancel to abort."
    )
    await callback.answer()


@router.message(EventInfoStates.waiting_import_url, F.text)
async def process_import_url(message: Message, state: FSMContext):
    """Process URL for import"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Import cancelled.", reply_markup=get_back_to_menu_keyboard())
        return

    url = message.text.strip()

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        await message.answer("Please send a valid URL starting with http:// or https://")
        return

    data = await state.get_data()
    event_code = data.get("import_event_code")

    status_msg = await message.answer("🔄 Fetching and parsing event page...")

    # Parse URL
    event_info = await event_parser_service.parse_event_url(url)

    if not event_info:
        await status_msg.edit_text(
            "❌ Failed to parse event page.\n\n"
            "Try a different URL or check if the page is accessible."
        )
        return

    # Save to database
    from infrastructure.database.supabase_client import supabase
    supabase.table("events").update({"event_info": event_info}).eq("code", event_code).execute()

    # Get event for display
    event = await event_service.get_event_by_code(event_code)

    # Show result
    text = f"✅ <b>Import successful!</b>\n\n"
    text += event_parser_service.format_event_card(event_info, event.name if event else event_code)

    await status_msg.edit_text(text, reply_markup=get_event_info_keyboard(event_code), disable_web_page_preview=True)
    await state.clear()


@router.callback_query(F.data.startswith("event_edit_"))
async def show_event_edit_menu(callback: CallbackQuery):
    """Show edit options for event info"""
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Admin only", show_alert=True)
        return

    event_code = callback.data.replace("event_edit_", "")

    # For now, suggest using import or direct DB edit
    text = (
        "<b>✏️ Edit Event Info</b>\n\n"
        "Options:\n"
        "• Use 🔗 Import URL to replace all info from a webpage\n"
        "• Or edit directly in database (events.event_info JSONB field)\n\n"
        "<i>Manual edit UI coming soon!</i>"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Import from URL", callback_data=f"event_import_{event_code}")
    builder.button(text="◀️ Back", callback_data=f"event_back_{event_code}")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("event_schedule_"))
async def show_full_schedule(callback: CallbackQuery):
    """Show full event schedule"""
    event_code = callback.data.replace("event_schedule_", "")

    from infrastructure.database.supabase_client import supabase
    result = supabase.table("events").select("event_info, name").eq("code", event_code).execute()

    if not result.data:
        await callback.answer("Event not found", show_alert=True)
        return

    event_data = result.data[0]
    event_info = event_data.get("event_info", {})
    event_name = event_data.get("name", event_code)
    schedule = event_info.get("schedule", [])

    if not schedule:
        await callback.answer("No schedule available", show_alert=True)
        return

    text = f"<b>📋 Full Schedule: {event_name}</b>\n\n"
    for item in schedule:
        time_str = item.get("time", "")
        title = item.get("title", "")
        speaker = item.get("speaker")
        desc = item.get("description")

        text += f"<b>{time_str}</b> — {title}\n"
        if speaker:
            text += f"   🎤 {speaker}\n"
        if desc:
            text += f"   <i>{desc[:100]}</i>\n"
        text += "\n"

    await callback.message.edit_text(text, reply_markup=get_event_info_keyboard(event_code))
    await callback.answer()


@router.callback_query(F.data.startswith("event_speakers_"))
async def show_all_speakers(callback: CallbackQuery):
    """Show all speakers"""
    event_code = callback.data.replace("event_speakers_", "")

    from infrastructure.database.supabase_client import supabase
    result = supabase.table("events").select("event_info, name").eq("code", event_code).execute()

    if not result.data:
        await callback.answer("Event not found", show_alert=True)
        return

    event_data = result.data[0]
    event_info = event_data.get("event_info", {})
    event_name = event_data.get("name", event_code)
    speakers = event_info.get("speakers", [])

    if not speakers:
        await callback.answer("No speakers listed", show_alert=True)
        return

    text = f"<b>🎤 Speakers: {event_name}</b>\n\n"
    for s in speakers:
        name = s.get("name", "Unknown")
        bio = s.get("bio", "")
        social = s.get("social", "")
        topics = s.get("topics", [])

        text += f"<b>{name}</b>"
        if social:
            text += f" {social}"
        text += "\n"
        if bio:
            text += f"   {bio}\n"
        if topics:
            text += f"   Topics: {', '.join(topics)}\n"
        text += "\n"

    await callback.message.edit_text(text, reply_markup=get_event_info_keyboard(event_code))
    await callback.answer()


@router.callback_query(F.data.startswith("event_back_"))
async def back_to_event_actions(callback: CallbackQuery):
    """Back to event actions menu"""
    event_code = callback.data.replace("event_back_", "")
    event = await event_service.get_event_by_code(event_code)

    if not event:
        await callback.answer("Event not found", show_alert=True)
        return

    # Generate deep link
    bot_info = await bot.me()
    deep_link = f"https://t.me/{bot_info.username}?start=event_{event.code}"

    text = f"""<b>📅 {event.name}</b>

<b>Code:</b> <code>{event.code}</code>
<b>Location:</b> {event.location or 'N/A'}

<b>Deep Link:</b>
<code>{deep_link}</code>"""

    await callback.message.edit_text(text, reply_markup=get_event_actions_keyboard(event_code))
    await callback.answer()


@router.callback_query(F.data.startswith("event_broadcast_"))
async def start_event_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast flow from button"""
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Admin only", show_alert=True)
        return

    event_code = callback.data.replace("event_broadcast_", "")
    event = await event_service.get_event_by_code(event_code)

    if not event:
        await callback.answer("Event not found", show_alert=True)
        return

    participants = await event_service.get_event_participants(event.id)

    await state.update_data(broadcast_event_code=event_code, broadcast_event_name=event.name)
    await state.set_state(EventInfoStates.waiting_broadcast_text)

    await callback.message.edit_text(
        f"<b>📢 Broadcast to {event.name}</b>\n\n"
        f"Recipients: {len(participants)} participants\n\n"
        "Send the message you want to broadcast.\n"
        "Send /cancel to abort."
    )
    await callback.answer()


@router.message(EventInfoStates.waiting_broadcast_text, F.text)
async def process_broadcast_text(message: Message, state: FSMContext):
    """Process and send broadcast"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Broadcast cancelled.", reply_markup=get_back_to_menu_keyboard())
        return

    data = await state.get_data()
    event_code = data.get("broadcast_event_code")
    event_name = data.get("broadcast_event_name", "Event")

    event = await event_service.get_event_by_code(event_code)
    if not event:
        await message.answer("Event not found")
        await state.clear()
        return

    participants = await event_service.get_event_participants(event.id)

    if not participants:
        await message.answer("No participants to broadcast to")
        await state.clear()
        return

    broadcast_text = message.text
    status_msg = await message.answer(f"📢 Broadcasting to {len(participants)} participants...")

    sent = 0
    failed = 0

    for p in participants:
        try:
            await bot.send_message(
                chat_id=int(p.platform_user_id),
                text=f"📢 <b>{event_name}</b>\n\n{broadcast_text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"<b>✅ Broadcast complete!</b>\n\n"
        f"Sent: {sent}\n"
        f"Failed: {failed}",
        reply_markup=get_event_actions_keyboard(event_code)
    )

    await state.clear()


@router.message(Command("followup"))
async def admin_followup(message: Message):
    """
    /followup [event_code] - Send follow-up check-in to all event participants who have matches
    """
    if message.from_user.id not in settings.admin_telegram_ids:
        await message.answer("Admin only")
        return

    parts = message.text.split(maxsplit=1)
    event_code = parts[1].strip() if len(parts) > 1 else None

    if not event_code:
        user = await user_service.get_user_by_platform(
            MessagePlatform.TELEGRAM,
            str(message.from_user.id)
        )
        if user and user.current_event_id:
            event = await event_service.get_event_by_id(user.current_event_id)
            event_code = event.code if event else None

    if not event_code:
        await message.answer("Usage: /followup EVENT_CODE")
        return

    event = await event_service.get_event_by_code(event_code)
    if not event:
        await message.answer(f"Event '{event_code}' not found")
        return

    participants = await event_service.get_event_participants(event.id)
    if not participants:
        await message.answer("No participants in this event")
        return

    await message.answer(f"Sending follow-up to {len(participants)} participants...")

    from adapters.telegram.handlers.matches import send_followup_checkin

    sent = 0
    skipped = 0
    for p in participants:
        if not p.platform_user_id:
            skipped += 1
            continue
        matches = await matching_service.get_user_matches(p.id)
        if not matches:
            skipped += 1
            continue
        lang = "ru"  # most users are RU for now
        name = p.display_name or p.first_name or "there"
        await send_followup_checkin(
            user_telegram_id=int(p.platform_user_id),
            user_name=name,
            match_count=len(matches),
            event_name=event.name or event_code,
            lang=lang
        )
        sent += 1

    await message.answer(f"✅ Follow-up sent: {sent}, skipped: {skipped} (no matches or no TG ID)")
