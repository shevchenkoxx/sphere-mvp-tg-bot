"""
Events handler - event creation and joining.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from core.domain.models import MessagePlatform
from config.settings import settings
from adapters.telegram.loader import event_service, matching_service, user_service, bot
from adapters.telegram.keyboards import (
    get_event_actions_keyboard,
    get_join_event_keyboard,
    get_main_menu_keyboard,
)
from adapters.telegram.states import EventStates

router = Router()


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
