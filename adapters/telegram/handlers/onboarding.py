"""
Onboarding handler - fast, friendly, conversational flow.
Goal: Complete onboarding in 60 seconds or less.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from core.domain.models import MessagePlatform, OnboardingData
from core.domain.constants import INTERESTS, GOALS, MAX_INTERESTS, MAX_GOALS
from adapters.telegram.loader import user_service, event_service, voice_service, bot
from adapters.telegram.keyboards import (
    get_interests_keyboard,
    get_goals_keyboard,
    get_quick_confirm_keyboard,
    get_main_menu_keyboard,
    get_skip_or_voice_keyboard,
)
from adapters.telegram.states import OnboardingStates

router = Router()


# === STEP 1: NAME (required) ===

@router.message(OnboardingStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    """Get user's name - friendly and quick"""
    name = message.text.strip()

    if len(name) < 2:
        await message.answer("Хм, слишком короткое имя. Как тебя зовут? 😊")
        return

    if len(name) > 50:
        await message.answer("Ого, длинное имя! Может, покороче? 😄")
        return

    await state.update_data(display_name=name)
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id),
        display_name=name
    )

    # Skip cities, go straight to interests
    await message.answer(
        f"Привет, {name}! 👋\n\n"
        "Выбери 2-5 интересов — это поможет найти близких по духу людей:",
        reply_markup=get_interests_keyboard()
    )
    await state.update_data(selected_interests=[])
    await state.set_state(OnboardingStates.waiting_interests)


# === STEP 2: INTERESTS (multi-select) ===

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
        await callback.answer(f"Максимум {MAX_INTERESTS}! Убери что-то, чтобы добавить новое", show_alert=True)
        return

    await state.update_data(selected_interests=selected)
    await callback.message.edit_reply_markup(reply_markup=get_interests_keyboard(selected))
    await callback.answer()


@router.callback_query(OnboardingStates.waiting_interests, F.data == "interests_done")
async def process_interests_done(callback: CallbackQuery, state: FSMContext):
    """Finish interest selection, move to goals"""
    data = await state.get_data()
    selected = data.get('selected_interests', [])

    if len(selected) < 1:
        await callback.answer("Выбери хотя бы один интерес!", show_alert=True)
        return

    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id),
        interests=selected
    )

    await callback.message.edit_text(
        "Отлично! Теперь выбери, зачем ты здесь (1-3):",
        reply_markup=get_goals_keyboard()
    )
    await state.update_data(selected_goals=[])
    await state.set_state(OnboardingStates.waiting_goals)
    await callback.answer()


# === STEP 3: GOALS (multi-select) ===

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
        await callback.answer(f"Максимум {MAX_GOALS}!", show_alert=True)
        return

    await state.update_data(selected_goals=selected)
    await callback.message.edit_reply_markup(reply_markup=get_goals_keyboard(selected))
    await callback.answer()


@router.callback_query(OnboardingStates.waiting_goals, F.data == "goals_done")
async def process_goals_done(callback: CallbackQuery, state: FSMContext):
    """Finish goals, move to bio (optional)"""
    data = await state.get_data()
    selected = data.get('selected_goals', [])

    if len(selected) < 1:
        await callback.answer("Выбери хотя бы одну цель!", show_alert=True)
        return

    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id),
        goals=selected
    )

    await callback.message.edit_text(
        "Последний шаг! Расскажи о себе в 1-2 предложениях.\n\n"
        "Или отправь голосовое — так даже интереснее! 🎤\n\n"
        "<i>Можешь пропустить, если хочешь</i>",
        reply_markup=get_skip_or_voice_keyboard()
    )
    await state.set_state(OnboardingStates.waiting_bio)
    await callback.answer()


# === STEP 4: BIO (optional, text or voice) ===

@router.message(OnboardingStates.waiting_bio, F.text)
async def process_bio_text(message: Message, state: FSMContext):
    """Process text bio"""
    bio = message.text.strip()

    if len(bio) > 500:
        await message.answer("Слишком длинно! Уложись в пару предложений 😊")
        return

    await state.update_data(bio=bio)
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id),
        bio=bio
    )
    await complete_onboarding(message, state)


@router.message(OnboardingStates.waiting_bio, F.voice)
async def process_bio_voice(message: Message, state: FSMContext):
    """Process voice bio - transcribe and save"""
    status_msg = await message.answer("🎤 Слушаю...")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        text = await voice_service.download_and_transcribe(file_url)

        if text:
            await state.update_data(bio=text)
            await user_service.update_user(
                MessagePlatform.TELEGRAM,
                str(message.from_user.id),
                bio=text
            )
            await status_msg.edit_text(f"✓ Записал: <i>{text[:100]}{'...' if len(text) > 100 else ''}</i>")
            await complete_onboarding(message, state)
        else:
            await status_msg.edit_text(
                "Не расслышал 😅 Попробуй ещё раз или напиши текстом",
                reply_markup=get_skip_or_voice_keyboard()
            )
    except Exception as e:
        await status_msg.edit_text(
            "Что-то пошло не так. Напиши текстом или пропусти",
            reply_markup=get_skip_or_voice_keyboard()
        )


@router.callback_query(OnboardingStates.waiting_bio, F.data == "skip_bio")
async def skip_bio(callback: CallbackQuery, state: FSMContext):
    """Skip bio step"""
    await callback.message.edit_text("Окей, пропускаем! ⏭")
    await complete_onboarding(callback.message, state, from_callback=True)
    await callback.answer()


# === COMPLETE ONBOARDING ===

async def complete_onboarding(message: Message, state: FSMContext, from_callback: bool = False):
    """Finish onboarding and show success"""
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
    user_id = str(message.chat.id)
    await user_service.complete_onboarding(
        MessagePlatform.TELEGRAM,
        user_id,
        onboarding_data
    )

    pending_event = data.get('pending_event')

    if pending_event:
        # Join event automatically
        success, msg, event = await event_service.join_event(
            pending_event,
            MessagePlatform.TELEGRAM,
            user_id
        )

        if success and event:
            text = (
                f"🎉 Готово! Ты в ивенте <b>{event.name}</b>\n\n"
                "Система уже ищет для тебя интересных людей. Напишу, когда найду!"
            )
        else:
            text = (
                "✓ Профиль готов!\n\n"
                "Ивент уже недоступен, но ты можешь присоединиться к другим."
            )
    else:
        text = (
            "🎉 <b>Профиль готов!</b>\n\n"
            "Теперь сканируй QR-коды на ивентах, чтобы находить интересных людей!"
        )

    await message.answer(text, reply_markup=get_main_menu_keyboard())
    await state.clear()
