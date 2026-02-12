"""
Post-Onboarding Personalization Handler.

4-step flow to capture user's current focus and preferences:
1. Passion Question: "What are you excited about right now?"
2. Connection Mode: receive_help / give_help / exchange
3. Adaptive Buttons: LLM-generated based on user context
4. Open-Ended Question: Describe ideal person to meet

Goal: Better matching by understanding TODAY's needs, not just static profile.
"""

import json
import re
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from openai import AsyncOpenAI

from core.domain.models import MessagePlatform
from core.prompts.templates import (
    PASSION_EXTRACTION_PROMPT,
    PERSONALIZED_ADAPTIVE_BUTTONS_PROMPT,
    IDEAL_CONNECTION_QUESTION_PROMPT,
)
from adapters.telegram.loader import user_service, bot, voice_service
from adapters.telegram.states import PersonalizationStates
from adapters.telegram.keyboards import (
    get_connection_mode_keyboard,
    get_adaptive_buttons_keyboard,
    get_skip_personalization_keyboard,
    get_main_menu_keyboard,
)
from config.settings import settings
from core.utils.language import detect_lang

logger = logging.getLogger(__name__)

router = Router(name="personalization")


# === Entry Point ===

async def start_personalization(
    message: Message,
    state: FSMContext,
    event_name: str = None,
    event_id: str = None,
    lang: str = None
):
    """
    Start personalization flow after onboarding completion.
    Called from onboarding handlers after profile is saved.
    """
    if lang is None:
        lang = detect_lang(message)

    # Save context
    await state.update_data(
        personalization_event_name=event_name,
        personalization_event_id=event_id,
        personalization_lang=lang
    )

    # Step 1: Ask passion question
    if lang == "ru":
        text = (
            "🔥 <b>Последний штрих!</b>\n\n"
            "Чем ты горишь прямо сейчас? Какой проект, идея или тема тебя увлекает?\n\n"
            "<i>Это поможет найти людей, которые сейчас на одной волне с тобой.</i>\n\n"
            "Напиши текстом или запиши голосовое 🎤"
        )
    else:
        text = (
            "🔥 <b>One more thing!</b>\n\n"
            "What are you passionate about right now? What project, idea or topic excites you?\n\n"
            "<i>This helps us find people who are on the same wavelength today.</i>\n\n"
            "Type or send a voice message 🎤"
        )

    await message.answer(text, reply_markup=get_skip_personalization_keyboard(lang))
    await state.set_state(PersonalizationStates.waiting_passion)


# === Step 1: Passion Question ===

@router.message(PersonalizationStates.waiting_passion, F.text)
async def process_passion_text(message: Message, state: FSMContext):
    """Process text answer to passion question."""
    data = await state.get_data()
    lang = data.get("personalization_lang", "en")

    passion_text = message.text.strip()

    if len(passion_text) < 10:
        if lang == "ru":
            await message.answer("Расскажи чуть подробнее! Хотя бы пару предложений 😊")
        else:
            await message.answer("Tell me a bit more! At least a couple of sentences 😊")
        return

    # Extract themes from passion
    themes_data = await extract_passion_themes(passion_text, message.from_user.id, lang)

    await state.update_data(
        passion_text=passion_text,
        passion_themes=themes_data.get("themes", []),
        passion_summary=themes_data.get("summary", ""),
        matching_signals=themes_data.get("matching_signals", [])
    )

    # Move to Step 2: Connection Mode
    await show_connection_mode_step(message, state, lang)


@router.message(PersonalizationStates.waiting_passion, F.voice)
async def process_passion_voice(message: Message, state: FSMContext):
    """Process voice answer to passion question."""
    data = await state.get_data()
    lang = data.get("personalization_lang", "en")

    status = await message.answer("🎤 Слушаю..." if lang == "ru" else "🎤 Listening...")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcription = await voice_service.download_and_transcribe(file_url)

        if transcription and len(transcription) >= 10:
            await status.delete()

            # Extract themes
            themes_data = await extract_passion_themes(transcription, message.from_user.id, lang)

            await state.update_data(
                passion_text=transcription,
                passion_themes=themes_data.get("themes", []),
                passion_summary=themes_data.get("summary", ""),
                matching_signals=themes_data.get("matching_signals", [])
            )

            # Move to Step 2
            await show_connection_mode_step(message, state, lang)
        else:
            await status.edit_text(
                "Не расслышал 😅 Попробуй ещё раз или напиши текстом" if lang == "ru"
                else "Couldn't hear that 😅 Try again or type it out"
            )
    except Exception as e:
        logger.error(f"Passion voice processing error: {e}")
        await status.edit_text(
            "Что-то пошло не так. Напиши текстом" if lang == "ru"
            else "Something went wrong. Please type instead"
        )


@router.callback_query(PersonalizationStates.waiting_passion, F.data == "skip_personalization_step")
async def skip_passion_step(callback: CallbackQuery, state: FSMContext):
    """Skip passion question."""
    data = await state.get_data()
    lang = data.get("personalization_lang", "en")

    await callback.message.edit_text(
        "👌 Пропускаем!" if lang == "ru" else "👌 Skipping!"
    )

    # Move directly to connection mode without passion context
    await state.update_data(passion_text=None, passion_themes=[])
    await show_connection_mode_step(callback.message, state, lang)
    await callback.answer()


# === Step 2: Connection Mode ===

async def show_connection_mode_step(message: Message, state: FSMContext, lang: str):
    """Show connection mode selection."""
    if lang == "ru":
        text = (
            "🤝 <b>Какой тип связей тебе важнее сейчас?</b>\n\n"
            "Это поможет найти людей, которые дополняют тебя."
        )
    else:
        text = (
            "🤝 <b>What type of connections matter to you right now?</b>\n\n"
            "This helps find people who complement you."
        )

    await message.answer(text, reply_markup=get_connection_mode_keyboard(lang))
    await state.set_state(PersonalizationStates.choosing_connection_mode)


@router.callback_query(PersonalizationStates.choosing_connection_mode, F.data.startswith("conn_mode_"))
async def process_connection_mode(callback: CallbackQuery, state: FSMContext):
    """Process connection mode selection."""
    mode = callback.data.replace("conn_mode_", "")  # receive_help, give_help, exchange
    data = await state.get_data()
    lang = data.get("personalization_lang", "en")

    await state.update_data(connection_mode=mode)

    # Show loading
    await callback.message.edit_text(
        "✨ Готовлю персональные варианты..." if lang == "ru"
        else "✨ Preparing personalized options..."
    )

    # Generate adaptive buttons based on context
    await show_adaptive_buttons_step(callback.message, state, lang)
    await callback.answer()


# === Step 3: Adaptive Buttons ===

async def show_adaptive_buttons_step(message: Message, state: FSMContext, lang: str):
    """Generate and show LLM-based adaptive buttons."""
    data = await state.get_data()
    user_id = str(message.chat.id)

    # Get user profile for context
    user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)

    if not user:
        logger.error(f"User not found for personalization: {user_id}")
        await finish_personalization(message, state, lang)
        return

    # Generate personalized buttons
    buttons_data = await generate_adaptive_buttons(
        user=user,
        passion_text=data.get("passion_text", ""),
        passion_themes=data.get("passion_themes", []),
        connection_mode=data.get("connection_mode", "exchange"),
        lang=lang
    )

    buttons = buttons_data.get("buttons", [])
    header = buttons_data.get("header", "")

    if not buttons or len(buttons) < 2:
        # Fallback: skip to save if button generation failed
        # (Step 4 ideal connection question temporarily disabled)
        logger.warning(f"Adaptive buttons generation failed for user {user_id}")
        # await show_ideal_connection_step(message, state, lang)
        await save_personalization_data(message, state, lang)
        return

    # Save buttons and header for later reference
    await state.update_data(adaptive_buttons=buttons, adaptive_header=header, adaptive_selected=[])

    # Show buttons with multi-select hint
    hint = " <i>(выбери несколько)</i>" if lang == "ru" else " <i>(pick multiple)</i>"
    text = f"🎯 <b>{header}</b>{hint}" if header else (
        f"🎯 <b>Что тебе ближе сегодня?</b>{hint}" if lang == "ru"
        else f"🎯 <b>What resonates with you today?</b>{hint}"
    )

    await message.edit_text(text, reply_markup=get_adaptive_buttons_keyboard(buttons, lang))
    await state.set_state(PersonalizationStates.choosing_adaptive_option)


@router.callback_query(PersonalizationStates.choosing_adaptive_option, F.data.startswith("adaptive_btn_"))
async def process_adaptive_choice(callback: CallbackQuery, state: FSMContext):
    """Toggle adaptive button selection (multi-select)."""
    btn_index = int(callback.data.replace("adaptive_btn_", ""))
    data = await state.get_data()
    lang = data.get("personalization_lang", "en")

    buttons = data.get("adaptive_buttons", [])
    selected_indices = data.get("adaptive_selected", [])

    # Toggle selection
    if btn_index in selected_indices:
        selected_indices.remove(btn_index)
    else:
        selected_indices.append(btn_index)

    await state.update_data(adaptive_selected=selected_indices)

    # Rebuild header
    header = data.get("adaptive_header", "")
    text = f"🎯 <b>{header}</b>" if header else (
        "🎯 <b>Что тебе ближе сегодня?</b> <i>(выбери несколько)</i>" if lang == "ru"
        else "🎯 <b>What resonates with you today?</b> <i>(pick multiple)</i>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_adaptive_buttons_keyboard(buttons, lang, selected=selected_indices)
    )
    await callback.answer()


@router.callback_query(PersonalizationStates.choosing_adaptive_option, F.data == "adaptive_done")
async def process_adaptive_done(callback: CallbackQuery, state: FSMContext):
    """Finalize multi-select adaptive choices."""
    data = await state.get_data()
    lang = data.get("personalization_lang", "en")

    buttons = data.get("adaptive_buttons", [])
    selected_indices = data.get("adaptive_selected", [])

    # Collect selected button texts
    selected_texts = [buttons[i] for i in selected_indices if i < len(buttons)]
    preference = " | ".join(selected_texts) if selected_texts else ""
    await state.update_data(personalization_preference=preference)

    await callback.message.edit_text(
        "✓ Отлично!" if lang == "ru" else "✓ Great!"
    )
    await save_personalization_data(callback.message, state, lang)
    await callback.answer()


# === Step 4: Open-Ended Question (TEMPORARILY DISABLED) ===
# Uncomment below to re-enable the "Last question!" step.

# async def show_ideal_connection_step(message: Message, state: FSMContext, lang: str):
#     """Show open-ended question about ideal connection."""
#     data = await state.get_data()
#
#     # Generate personalized question based on mode
#     question = await generate_ideal_connection_question(
#         connection_mode=data.get("connection_mode", "exchange"),
#         passion_themes=data.get("passion_themes", []),
#         personalization_preference=data.get("personalization_preference", ""),
#         lang=lang
#     )
#
#     if lang == "ru":
#         text = f"💭 <b>Последний вопрос!</b>\n\n{question}\n\n<i>Напиши текстом или голосовым</i>"
#     else:
#         text = f"💭 <b>Last question!</b>\n\n{question}\n\n<i>Type or send a voice message</i>"
#
#     await message.answer(text, reply_markup=get_skip_personalization_keyboard(lang))
#     await state.set_state(PersonalizationStates.waiting_ideal_connection)
#
#
# @router.message(PersonalizationStates.waiting_ideal_connection, F.text)
# async def process_ideal_connection_text(message: Message, state: FSMContext):
#     """Process text answer about ideal connection."""
#     data = await state.get_data()
#     lang = data.get("personalization_lang", "en")
#
#     ideal_text = message.text.strip()
#
#     await state.update_data(ideal_connection=ideal_text)
#
#     # Save and finish
#     await save_personalization_data(message, state, lang)
#
#
# @router.message(PersonalizationStates.waiting_ideal_connection, F.voice)
# async def process_ideal_connection_voice(message: Message, state: FSMContext):
#     """Process voice answer about ideal connection."""
#     data = await state.get_data()
#     lang = data.get("personalization_lang", "en")
#
#     status = await message.answer("🎤 Слушаю..." if lang == "ru" else "🎤 Listening...")
#
#     try:
#         file = await bot.get_file(message.voice.file_id)
#         file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
#         transcription = await voice_service.download_and_transcribe(file_url)
#
#         if transcription:
#             await status.delete()
#             await state.update_data(ideal_connection=transcription)
#             await save_personalization_data(message, state, lang)
#         else:
#             await status.edit_text(
#                 "Не расслышал. Напиши текстом?" if lang == "ru"
#                 else "Couldn't hear that. Type it out?"
#             )
#     except Exception as e:
#         logger.error(f"Ideal connection voice error: {e}")
#         await status.edit_text(
#             "Напиши текстом" if lang == "ru" else "Please type instead"
#         )
#
#
# @router.callback_query(PersonalizationStates.waiting_ideal_connection, F.data == "skip_personalization_step")
# async def skip_ideal_connection_step(callback: CallbackQuery, state: FSMContext):
#     """Skip ideal connection question."""
#     data = await state.get_data()
#     lang = data.get("personalization_lang", "en")
#
#     await callback.message.edit_text("👌")
#     await save_personalization_data(callback.message, state, lang)
#     await callback.answer()


# === Save & Finish ===

async def save_personalization_data(message: Message, state: FSMContext, lang: str):
    """Save all personalization data to user profile."""
    data = await state.get_data()
    user_id = str(message.chat.id)

    try:
        # Update user with personalization data
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            user_id,
            passion_text=data.get("passion_text"),
            passion_themes=data.get("passion_themes"),
            connection_mode=data.get("connection_mode"),
            personalization_preference=data.get("personalization_preference"),
            ideal_connection=data.get("ideal_connection")
        )

        logger.info(f"Personalization data saved for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to save personalization data: {e}")

    # Finish personalization
    await finish_personalization(message, state, lang)


async def finish_personalization(message: Message, state: FSMContext, lang: str):
    """Complete personalization and proceed to matches."""
    data = await state.get_data()
    event_id = data.get("personalization_event_id")
    event_name = data.get("personalization_event_name")

    # Clear personalization state but keep event context for matches
    await state.update_data(
        # Clear personalization temp data
        passion_text=None,
        passion_themes=None,
        passion_summary=None,
        matching_signals=None,
        connection_mode=None,
        adaptive_buttons=None,
        personalization_preference=None,
        ideal_connection=None,
    )

    if lang == "ru":
        text = "🎉 <b>Отлично! Твой профиль готов!</b>\n\n🔍 Sphere ищет лучшие матчи для тебя!"
    else:
        text = "🎉 <b>Great! Your profile is ready!</b>\n\n🔍 Sphere is searching for the best possible matches for you!"

    await message.answer(text)

    # Show matches
    if event_id:
        from adapters.telegram.handlers.onboarding_audio import show_top_matches

        user_id = str(message.chat.id)
        user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)

        if user:
            from uuid import UUID

            class EventWrapper:
                def __init__(self, id, name):
                    self.id = UUID(id)
                    self.name = name

            event = EventWrapper(event_id, event_name)
            await show_top_matches(message, user, event, lang, user.username)
        else:
            await message.answer(
                "Готово!" if lang == "ru" else "Done!",
                reply_markup=get_main_menu_keyboard(lang)
            )
    else:
        await message.answer(
            "Сканируй QR-код на ивенте чтобы получить матчи!" if lang == "ru"
            else "Scan a QR code at an event to get matches!",
            reply_markup=get_main_menu_keyboard(lang)
        )

    await state.clear()


# === LLM Functions ===

async def extract_passion_themes(passion_text: str, user_id: int, lang: str) -> dict:
    """Extract themes from passion statement using LLM."""
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Get user profile for context
        user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, str(user_id))

        prompt = PASSION_EXTRACTION_PROMPT.format(
            passion_text=passion_text,
            profession=user.bio if user else "Not specified",
            interests=", ".join(user.interests) if user and user.interests else "Not specified",
            looking_for=user.looking_for if user else "Not specified",
            can_help_with=user.can_help_with if user else "Not specified"
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        return json.loads(text)

    except Exception as e:
        logger.error(f"Passion extraction error: {e}")
        # Fallback: simple keyword extraction
        words = passion_text.lower().split()
        themes = [w for w in words if len(w) > 5][:3]
        return {
            "themes": themes if themes else ["general"],
            "summary": passion_text[:100],
            "matching_signals": []
        }


async def generate_adaptive_buttons(
    user,
    passion_text: str,
    passion_themes: list,
    connection_mode: str,
    lang: str
) -> dict:
    """Generate personalized adaptive buttons using LLM."""
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        language_name = "Russian" if lang == "ru" else "English"

        prompt = PERSONALIZED_ADAPTIVE_BUTTONS_PROMPT.format(
            display_name=user.display_name or user.first_name or "User",
            profession=user.bio or "Not specified",
            bio=user.bio or "",
            interests=", ".join(user.interests) if user.interests else "Not specified",
            looking_for=user.looking_for or "Not specified",
            can_help_with=user.can_help_with or "Not specified",
            passion_text=passion_text or "Not provided",
            passion_themes=", ".join(passion_themes) if passion_themes else "None",
            connection_mode=connection_mode,
            language=language_name
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.7
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        return json.loads(text)

    except Exception as e:
        logger.error(f"Adaptive buttons generation error: {e}")
        # Fallback buttons based on mode
        if lang == "ru":
            if connection_mode == "receive_help":
                return {
                    "header": "Какая помощь тебе нужна?",
                    "buttons": ["Найти ментора", "Получить фидбек", "Найти партнёра"]
                }
            elif connection_mode == "give_help":
                return {
                    "header": "Кому ты хочешь помочь?",
                    "buttons": ["Начинающим", "Командам", "Фаундерам"]
                }
            else:
                return {
                    "header": "Чем хочешь обменяться?",
                    "buttons": ["Опытом в продукте", "Идеями для роста", "Контактами"]
                }
        else:
            if connection_mode == "receive_help":
                return {
                    "header": "What kind of help do you need?",
                    "buttons": ["Find a mentor", "Get feedback", "Find a partner"]
                }
            elif connection_mode == "give_help":
                return {
                    "header": "Who do you want to help?",
                    "buttons": ["Beginners", "Teams", "Founders"]
                }
            else:
                return {
                    "header": "What do you want to exchange?",
                    "buttons": ["Product experience", "Growth ideas", "Connections"]
                }


async def generate_ideal_connection_question(
    connection_mode: str,
    passion_themes: list,
    personalization_preference: str,
    lang: str
) -> str:
    """Generate personalized question about ideal connection."""
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        language_name = "Russian" if lang == "ru" else "English"

        prompt = IDEAL_CONNECTION_QUESTION_PROMPT.format(
            connection_mode=connection_mode,
            passion_themes=", ".join(passion_themes) if passion_themes else "general networking",
            personalization_preference=personalization_preference or "not specified",
            language=language_name
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Ideal connection question generation error: {e}")
        # Fallback questions
        if lang == "ru":
            if connection_mode == "receive_help":
                return "Какой совет был бы для тебя самым ценным прямо сейчас?"
            elif connection_mode == "give_help":
                return "Кому ты мог бы помочь больше всего и как?"
            else:
                return "Опиши идеального человека для обмена опытом сегодня."
        else:
            if connection_mode == "receive_help":
                return "What advice would be most valuable for you right now?"
            elif connection_mode == "give_help":
                return "Who could you help the most and how?"
            else:
                return "Describe your ideal person to exchange experience with today."
