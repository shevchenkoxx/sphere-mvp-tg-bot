"""
Onboarding handler - user registration flow.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from core.domain.models import MessagePlatform, OnboardingData
from core.domain.constants import (
    INTERESTS, GOALS, MAX_INTERESTS, MAX_GOALS,
    get_interest_display, get_goal_display
)
from adapters.telegram.loader import user_service, event_service, voice_service, bot
from adapters.telegram.keyboards import (
    get_skip_keyboard,
    get_interests_keyboard,
    get_goals_keyboard,
    get_confirmation_keyboard,
    get_main_menu_keyboard,
)
from adapters.telegram.states import OnboardingStates

router = Router()


# === NAME ===

@router.message(OnboardingStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    """Process user name input"""
    name = message.text.strip()

    is_valid, error = user_service.validate_name(name)
    if not is_valid:
        await message.answer(f"{error}. Попробуй ещё раз:")
        return

    await state.update_data(display_name=name)

    # Save to DB
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id),
        display_name=name
    )

    await message.answer(
        f"Отлично, {name}!\n\n"
        "Откуда ты родом? Напиши город:"
    )
    await state.set_state(OnboardingStates.waiting_city_born)


# === CITY BORN ===

@router.message(OnboardingStates.waiting_city_born)
async def process_city_born(message: Message, state: FSMContext):
    """Process birth city"""
    city = message.text.strip()
    await state.update_data(city_born=city)

    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id),
        city_born=city
    )

    await message.answer("А где ты живёшь сейчас?")
    await state.set_state(OnboardingStates.waiting_city_current)


# === CURRENT CITY ===

@router.message(OnboardingStates.waiting_city_current)
async def process_city_current(message: Message, state: FSMContext):
    """Process current city"""
    city = message.text.strip()
    await state.update_data(city_current=city)

    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id),
        city_current=city
    )

    await message.answer(
        "Теперь самое интересное!\n\n"
        f"Выбери до {MAX_INTERESTS} интересов, которые тебя увлекают:",
        reply_markup=get_interests_keyboard()
    )
    await state.update_data(selected_interests=[])
    await state.set_state(OnboardingStates.waiting_interests)


# === INTERESTS ===

@router.callback_query(OnboardingStates.waiting_interests, F.data.startswith("interest_"))
async def process_interest_selection(callback: CallbackQuery, state: FSMContext):
    """Toggle interest selection"""
    interest = callback.data.replace("interest_", "")
    data = await state.get_data()
    selected = data.get('selected_interests', [])

    if interest in selected:
        selected.remove(interest)
    elif len(selected) < MAX_INTERESTS:
        selected.append(interest)
    else:
        await callback.answer(f"Максимум {MAX_INTERESTS} интересов!", show_alert=True)
        return

    await state.update_data(selected_interests=selected)
    await callback.message.edit_reply_markup(reply_markup=get_interests_keyboard(selected))
    await callback.answer()


@router.callback_query(OnboardingStates.waiting_interests, F.data == "interests_done")
async def process_interests_done(callback: CallbackQuery, state: FSMContext):
    """Finish interest selection"""
    data = await state.get_data()
    selected = data.get('selected_interests', [])

    is_valid, error = user_service.validate_interests(selected)
    if not is_valid:
        await callback.answer(error, show_alert=True)
        return

    # Save to DB
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id),
        interests=selected
    )

    await callback.message.edit_text(
        f"Отлично! Теперь выбери до {MAX_GOALS} целей — что ты хочешь найти в Sphere?",
        reply_markup=get_goals_keyboard()
    )
    await state.update_data(selected_goals=[])
    await state.set_state(OnboardingStates.waiting_goals)
    await callback.answer()


# === GOALS ===

@router.callback_query(OnboardingStates.waiting_goals, F.data.startswith("goal_"))
async def process_goal_selection(callback: CallbackQuery, state: FSMContext):
    """Toggle goal selection"""
    goal = callback.data.replace("goal_", "")
    data = await state.get_data()
    selected = data.get('selected_goals', [])

    if goal in selected:
        selected.remove(goal)
    elif len(selected) < MAX_GOALS:
        selected.append(goal)
    else:
        await callback.answer(f"Максимум {MAX_GOALS} цели!", show_alert=True)
        return

    await state.update_data(selected_goals=selected)
    await callback.message.edit_reply_markup(reply_markup=get_goals_keyboard(selected))
    await callback.answer()


@router.callback_query(OnboardingStates.waiting_goals, F.data == "goals_done")
async def process_goals_done(callback: CallbackQuery, state: FSMContext):
    """Finish goal selection"""
    data = await state.get_data()
    selected = data.get('selected_goals', [])

    is_valid, error = user_service.validate_goals(selected)
    if not is_valid:
        await callback.answer(error, show_alert=True)
        return

    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id),
        goals=selected
    )

    await callback.message.edit_text(
        "Расскажи немного о себе — что тебя увлекает, чем занимаешься?\n\n"
        "Это поможет найти людей, с которыми у тебя много общего.\n\n"
        "<i>Можешь написать текстом или отправить голосовое сообщение</i>",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(OnboardingStates.waiting_bio)
    await callback.answer()


# === BIO ===

@router.message(OnboardingStates.waiting_bio, F.text)
async def process_bio_text(message: Message, state: FSMContext):
    """Process text bio"""
    bio = message.text.strip()
    await state.update_data(bio=bio)

    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id),
        bio=bio
    )

    await show_profile_confirmation(message, state)


@router.message(OnboardingStates.waiting_bio, F.voice)
async def process_bio_voice(message: Message, state: FSMContext):
    """Process voice bio"""
    await message.answer("Обрабатываю голосовое сообщение...")

    # Get file URL
    file = await bot.get_file(message.voice.file_id)
    file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

    # Transcribe
    text = await voice_service.download_and_transcribe(file_url)

    if text:
        await state.update_data(bio=text)
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            str(message.from_user.id),
            bio=text
        )
        await message.answer(f"Записал: <i>{text}</i>")
        await show_profile_confirmation(message, state)
    else:
        await message.answer(
            "Не удалось распознать голос. Попробуй ещё раз или напиши текстом.",
            reply_markup=get_skip_keyboard()
        )


@router.callback_query(OnboardingStates.waiting_bio, F.data == "skip_step")
async def skip_bio(callback: CallbackQuery, state: FSMContext):
    """Skip bio"""
    await show_profile_confirmation(callback.message, state, edit=True)
    await callback.answer()


# === CONFIRMATION ===

async def show_profile_confirmation(message: Message, state: FSMContext, edit: bool = False):
    """Show profile for confirmation"""
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.chat.id)
    )

    if not user:
        return

    interests_text = ', '.join([get_interest_display(i) for i in user.interests])
    goals_text = ', '.join([get_goal_display(g) for g in user.goals])

    text = (
        "<b>Твой профиль готов!</b>\n\n"
        f"<b>Имя:</b> {user.display_name or 'Не указано'}\n"
        f"<b>Родной город:</b> {user.city_born or 'Не указан'}\n"
        f"<b>Текущий город:</b> {user.city_current or 'Не указан'}\n"
        f"<b>Интересы:</b> {interests_text}\n"
        f"<b>Цели:</b> {goals_text}\n"
        f"<b>О себе:</b> {user.bio or 'Не заполнено'}\n\n"
        "Всё верно?"
    )

    if edit:
        await message.edit_text(text, reply_markup=get_confirmation_keyboard())
    else:
        await message.answer(text, reply_markup=get_confirmation_keyboard())

    await state.set_state(OnboardingStates.confirming_profile)


@router.callback_query(OnboardingStates.confirming_profile, F.data == "confirm_profile")
async def confirm_profile(callback: CallbackQuery, state: FSMContext):
    """Confirm profile and complete onboarding"""
    data = await state.get_data()

    # Build onboarding data
    onboarding_data = OnboardingData(
        display_name=data.get('display_name'),
        city_born=data.get('city_born'),
        city_current=data.get('city_current'),
        selected_interests=data.get('selected_interests', []),
        selected_goals=data.get('selected_goals', []),
        bio=data.get('bio'),
        pending_event_code=data.get('pending_event')
    )

    # Complete onboarding (generates AI summary)
    await user_service.complete_onboarding(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id),
        onboarding_data
    )

    pending_event = data.get('pending_event')

    if pending_event:
        # Join event
        success, message_text, event = await event_service.join_event(
            pending_event,
            MessagePlatform.TELEGRAM,
            str(callback.from_user.id)
        )

        if success and event:
            await callback.message.edit_text(
                f"Профиль создан и ты уже в ивенте <b>{event.name}</b>!\n\n"
                "Система уже ищет для тебя интересные знакомства. "
                "Я напишу, когда найду подходящего человека!",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await callback.message.edit_text(
                "Профиль создан!\n\n"
                "К сожалению, ивент уже недоступен. "
                "Но ты можешь присоединиться к другим!",
                reply_markup=get_main_menu_keyboard()
            )
    else:
        await callback.message.edit_text(
            "<b>Профиль создан!</b>\n\n"
            "Теперь ты можешь:\n"
            "• Сканировать QR-коды на ивентах\n"
            "• Получать персональные матчи\n"
            "• Знакомиться с интересными людьми\n\n"
            "Выбери действие:",
            reply_markup=get_main_menu_keyboard()
        )

    await state.clear()
    await callback.answer("Добро пожаловать в Sphere!")


@router.callback_query(OnboardingStates.confirming_profile, F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    """Restart onboarding"""
    await callback.message.edit_text(
        "Хорошо, давай заново!\n\n"
        "Как тебя зовут?"
    )
    await state.set_state(OnboardingStates.waiting_name)
    await callback.answer()
