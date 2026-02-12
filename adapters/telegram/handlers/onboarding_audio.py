"""
Audio Onboarding Handler - 60-second voice message flow.
User speaks naturally, we extract structured profile data.

Flow:
1. Detect language from Telegram settings (default: English)
2. LLM generates personalized intro explaining what to say
3. User records voice message
4. AI extracts profile data
5. Validate completeness - if missing key info, ask follow-up
6. Show confirmation and save
"""

import asyncio
import json
import re
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command

from core.domain.models import MessagePlatform
from core.prompts.audio_onboarding import (
    AUDIO_GUIDE_PROMPT_RU,
    AUDIO_GUIDE_PROMPT,
    AUDIO_INTRO_PROMPT,
    AUDIO_WELCOME_EN,
    AUDIO_WELCOME_RU,
    AUDIO_EXTRACTION_PROMPT,
    AUDIO_VALIDATION_PROMPT,
    AUDIO_CONFIRMATION_HEADER,
    AUDIO_CONFIRMATION_HEADER_RU,
    AUDIO_CONFIRMATION_FOOTER,
    AUDIO_CONFIRMATION_FOOTER_RU,
    WHISPER_PROMPT_EN,
    WHISPER_PROMPT_RU,
    TRANSCRIPT_CORRECTION_PROMPT,
)
from adapters.telegram.loader import user_service, event_service, voice_service, matching_service, bot, embedding_service
from infrastructure.database.user_repository import SupabaseUserRepository
from adapters.telegram.keyboards import get_main_menu_keyboard
from config.settings import settings
from config.features import Features
from core.utils.language import detect_lang, get_language_name

logger = logging.getLogger(__name__)


def _whisper_prompt(lang: str) -> str:
    """Get Whisper domain-vocabulary prompt for the given language."""
    return WHISPER_PROMPT_RU if lang == "ru" else WHISPER_PROMPT_EN


async def _correct_transcription(text: str) -> str:
    """Quick LLM pass to fix Whisper transcription errors."""
    from openai import AsyncOpenAI
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=15.0)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": TRANSCRIPT_CORRECTION_PROMPT.format(transcription=text)}],
            max_tokens=len(text) + 200,
            temperature=0.1,
        )
        corrected = response.choices[0].message.content.strip()
        if corrected and len(corrected) > 10:
            if corrected != text:
                logger.info(f"Transcript corrected: '{text[:80]}...' → '{corrected[:80]}...'")
            return corrected
    except Exception as e:
        logger.warning(f"Transcript correction failed, using raw: {e}")
    return text


def _on_background_task_done(task: asyncio.Task, user_id: str = "unknown"):
    """Callback for background tasks — logs unhandled exceptions."""
    if task.cancelled():
        logger.warning(f"Background task cancelled for user {user_id}")
        return
    exc = task.exception()
    if exc:
        logger.error(
            f"Background task failed for user {user_id}: {exc}",
            exc_info=exc,
        )

router = Router(name="onboarding_audio")


# Language detection imported from core.utils.language
# detect_lang() and get_language_name() are centralized there


# === FSM States ===

class AudioOnboarding(StatesGroup):
    """States for audio onboarding"""
    waiting_audio = State()      # Waiting for voice message
    waiting_followup = State()   # Waiting for follow-up answer
    confirming = State()         # Confirming extracted profile
    adding_details = State()     # Adding more details to profile
    waiting_selfie = State()     # Waiting for selfie photo


class QuickTextOnboarding(StatesGroup):
    """States for quick 3-step text onboarding (noisy events)"""
    step_about = State()         # "Who are you? What do you do?"
    step_looking = State()       # "Who do you want to meet?"
    step_help = State()          # "How can you help others?"


# === Keyboards ===

def get_audio_start_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Keyboard to start audio recording"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="🎤 Готов записать", callback_data="audio_ready")
        builder.button(text="⌨️ Лучше текстом", callback_data="switch_to_text")
    else:
        builder.button(text="🎤 Ready to record", callback_data="audio_ready")
        builder.button(text="⌨️ Prefer typing", callback_data="switch_to_text")
    builder.adjust(1)
    return builder.as_markup()


def get_audio_confirm_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Keyboard for confirming profile"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="✅ Всё верно!", callback_data="audio_confirm")
        builder.button(text="➕ Добавить детали", callback_data="audio_add_details")
    else:
        builder.button(text="✅ Looks good!", callback_data="audio_confirm")
        builder.button(text="➕ Add details", callback_data="audio_add_details")
    builder.adjust(2)
    return builder.as_markup()


def get_selfie_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Keyboard for selfie request"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="⏩ Пропустить", callback_data="skip_selfie")
    else:
        builder.button(text="⏩ Skip", callback_data="skip_selfie")
    return builder.as_markup()


# === Entry Point ===

async def start_audio_onboarding(
    message: Message,
    state: FSMContext,
    event_name: str = None,
    event_code: str = None,
    lang: str = None  # Auto-detect if not provided
):
    """
    Start audio onboarding flow.
    Called from start handler.
    """
    # Auto-detect language from Telegram if not provided
    if lang is None:
        lang = detect_lang(message)

    # Save context
    await state.update_data(
        event_name=event_name,
        pending_event=event_code,
        language=lang,
        user_first_name=message.from_user.first_name
    )

    # Generate personalized intro with LLM
    intro_text = await generate_onboarding_intro(
        event_name=event_name,
        first_name=message.from_user.first_name,
        lang=lang
    )

    await message.answer(
        intro_text,
        reply_markup=get_audio_start_keyboard(lang)
    )
    await state.set_state(AudioOnboarding.waiting_audio)


async def generate_onboarding_intro(
    event_name: str = None,
    first_name: str = None,
    lang: str = "en"
) -> str:
    """Generate personalized intro using rich static templates (faster + consistent)."""
    name_part = f", {first_name}" if first_name else ""

    if lang == "ru":
        return AUDIO_WELCOME_RU.format(name_part=name_part)
    else:
        return AUDIO_WELCOME_EN.format(name_part=name_part)


# === Handlers ===

@router.callback_query(AudioOnboarding.waiting_audio, F.data == "audio_ready")
async def audio_ready(callback: CallbackQuery, state: FSMContext):
    """User is ready to record"""
    data = await state.get_data()
    lang = data.get("language", "ru")

    if lang == "ru":
        text = "🎤 Отлично! Записывай голосовое сообщение.\n\nГовори свободно 30-60 секунд о себе."
    else:
        text = "🎤 Great! Record your voice message.\n\nSpeak freely for 30-60 seconds about yourself."

    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(AudioOnboarding.waiting_audio, F.data == "switch_to_text")
async def switch_to_text(callback: CallbackQuery, state: FSMContext):
    """Switch to quick 3-step text onboarding"""
    data = await state.get_data()
    lang = data.get("language", "en")

    try:
        await callback.message.delete()
    except Exception:
        pass

    if lang == "ru":
        text = (
            "⌨️ <b>Быстрый текстовый онбординг</b>\n\n"
            "<b>Шаг 1/3:</b> Кто ты и чем занимаешься?\n\n"
            "<i>Например: «Продакт-менеджер в AI стартапе, 5 лет опыта»</i>"
        )
    else:
        text = (
            "⌨️ <b>Quick Text Onboarding</b>\n\n"
            "<b>Step 1/3:</b> Who are you and what do you do?\n\n"
            "<i>E.g.: \"Product manager at an AI startup, 5 years experience\"</i>"
        )

    await state.set_state(QuickTextOnboarding.step_about)
    await callback.message.answer(text)
    await callback.answer()


@router.message(QuickTextOnboarding.step_about, F.text)
async def quick_text_step_about(message: Message, state: FSMContext):
    """Step 1: Who are you"""
    data = await state.get_data()
    lang = data.get("language", "en")
    await state.update_data(qt_about=message.text.strip())

    if lang == "ru":
        text = (
            "<b>Шаг 2/3:</b> Кого хочешь встретить?\n\n"
            "<i>Например: «Ищу технического кофаундера или инвесторов в AI»</i>"
        )
    else:
        text = (
            "<b>Step 2/3:</b> Who do you want to meet?\n\n"
            "<i>E.g.: \"Looking for a technical co-founder or AI investors\"</i>"
        )

    await state.set_state(QuickTextOnboarding.step_looking)
    await message.answer(text)


@router.message(QuickTextOnboarding.step_looking, F.text)
async def quick_text_step_looking(message: Message, state: FSMContext):
    """Step 2: Who to meet"""
    data = await state.get_data()
    lang = data.get("language", "en")
    await state.update_data(qt_looking=message.text.strip())

    if lang == "ru":
        text = (
            "<b>Шаг 3/3:</b> Чем можешь помочь другим?\n\n"
            "<i>Например: «Могу помочь с продуктовой стратегией, UX и фандрайзингом»</i>"
        )
    else:
        text = (
            "<b>Step 3/3:</b> How can you help others?\n\n"
            "<i>E.g.: \"Can help with product strategy, UX, and fundraising\"</i>"
        )

    await state.set_state(QuickTextOnboarding.step_help)
    await message.answer(text)


@router.message(QuickTextOnboarding.step_help, F.text)
async def quick_text_step_done(message: Message, state: FSMContext):
    """Step 3: Save and finish"""
    data = await state.get_data()
    lang = data.get("language", "en")

    about = data.get("qt_about", "")
    looking = data.get("qt_looking", "")
    can_help = message.text.strip()

    # Build profile_data to reuse save_audio_profile
    profile_data = {
        "display_name": message.from_user.first_name,
        "about": about,
        "looking_for": looking,
        "can_help_with": can_help,
        "interests": [],
        "goals": [],
    }

    # Save to state so confirm handler can read it
    await state.update_data(profile_data=profile_data)

    # Show confirmation
    await show_profile_confirmation(message, state, profile_data, lang)


@router.message(AudioOnboarding.waiting_audio, F.voice)
async def process_audio(message: Message, state: FSMContext):
    """Process voice message and extract profile"""
    data = await state.get_data()
    lang = data.get("language", "en")

    # Validate voice duration
    if message.voice.duration > Features.MAX_VOICE_DURATION:
        max_dur = Features.MAX_VOICE_DURATION
        if lang == "ru":
            await message.answer(f"Голосовое слишком длинное (максимум {max_dur} сек). Попробуй покороче!")
        else:
            await message.answer(f"Voice message too long (max {max_dur}s). Please try a shorter one!")
        return

    # Status message with progress updates
    status = await message.answer("🎤 Transcribing..." if lang == "en" else "🎤 Расшифровываю...")

    try:
        # Get voice file
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

        # Transcribe with language hint + domain vocabulary
        transcription = await voice_service.download_and_transcribe(
            file_url, language=lang, prompt=_whisper_prompt(lang)
        )

        if not transcription or len(transcription) < 20:
            await status.edit_text(
                "Couldn't hear that clearly 😅 Please try again, speak clearly." if lang == "en"
                else "Не расслышал 😅 Попробуй ещё раз, говори чётче."
            )
            return

        # LLM correction pass — fix Whisper mishearings
        transcription = await _correct_transcription(transcription)

        # Update progress
        try:
            await status.edit_text(
                "✨ Building your profile..." if lang == "en" else "✨ Создаю профиль..."
            )
        except Exception:
            pass

        # Extract profile data
        profile_data = await extract_profile_from_transcription(
            transcription,
            event_name=data.get("event_name"),
            detected_lang=lang
        )

        # Save to state
        await state.update_data(
            transcription=transcription,
            profile_data=profile_data
        )

        await status.delete()

        # Skip LLM validation — check completeness locally (faster)
        has_about = bool(profile_data.get("about"))
        has_looking = bool(profile_data.get("looking_for"))
        has_help = bool(profile_data.get("can_help_with"))

        if has_about and (has_looking or has_help):
            await show_profile_confirmation(message, state, profile_data, lang)
        else:
            # Missing important info — ask a simple follow-up (no LLM call)
            missing = []
            if not has_looking:
                missing.append("looking_for")
            if not has_help:
                missing.append("can_help_with")
            await state.update_data(missing_fields=missing)

            if lang == "ru":
                question = "Отлично! А кого ты хотел бы встретить здесь и чем можешь помочь другим?"
            else:
                question = "Great intro! Who would you like to meet here, and how can you help others?"
            await message.answer(question)
            await state.set_state(AudioOnboarding.waiting_followup)

    except Exception as e:
        logger.error(f"Audio processing error: {e}", exc_info=True)
        await status.edit_text(
            "Something went wrong. Please try again." if lang == "en"
            else "Что-то пошло не так. Попробуй ещё раз."
        )


async def validate_profile_completeness(profile_data: dict, lang: str) -> dict:
    """Validate if profile has enough info for matching, generate follow-up if needed."""
    from openai import AsyncOpenAI

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        prompt = AUDIO_VALIDATION_PROMPT.format(
            display_name=profile_data.get("display_name") or "Not provided",
            about=profile_data.get("about") or "Not provided",
            looking_for=profile_data.get("looking_for") or "Not provided",
            can_help_with=profile_data.get("can_help_with") or "Not provided",
            interests=", ".join(profile_data.get("interests", [])) or "None",
            language=get_language_name(lang)
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        return json.loads(text)

    except Exception as e:
        logger.error(f"Profile validation error: {e}")
        # Fallback: check manually
        has_about = bool(profile_data.get("about"))
        has_looking = bool(profile_data.get("looking_for"))
        has_help = bool(profile_data.get("can_help_with"))

        if has_about and (has_looking or has_help):
            return {"is_complete": True, "missing_fields": []}

        missing = []
        if not has_looking:
            missing.append("looking_for")
        if not has_help:
            missing.append("can_help_with")

        # Generate simple follow-up
        if lang == "ru":
            question = "Отлично! А кого ты хотел бы встретить здесь и чем можешь помочь другим?"
        else:
            question = "Great intro! Who would you like to meet here, and how can you help others?"

        return {
            "is_complete": False,
            "missing_fields": missing,
            "follow_up_question": question
        }


# === Follow-up Handler ===

@router.message(AudioOnboarding.waiting_followup, F.text)
async def process_followup_text(message: Message, state: FSMContext):
    """Process text answer to follow-up question"""
    data = await state.get_data()
    profile_data = data.get("profile_data", {})
    missing_fields = data.get("missing_fields", [])
    lang = data.get("language", "en")

    # Parse the follow-up answer and merge into profile
    updated_profile = await merge_followup_into_profile(
        profile_data,
        message.text,
        missing_fields,
        lang
    )

    await state.update_data(profile_data=updated_profile)
    await show_profile_confirmation(message, state, updated_profile, lang)


@router.message(AudioOnboarding.waiting_followup, F.voice)
async def process_followup_voice(message: Message, state: FSMContext):
    """Process voice answer to follow-up question"""
    data = await state.get_data()
    profile_data = data.get("profile_data", {})
    missing_fields = data.get("missing_fields", [])
    lang = data.get("language", "en")

    if message.voice.duration > Features.MAX_VOICE_DURATION:
        await message.answer("Voice too long. Please try shorter!" if lang == "en" else "Слишком длинное. Покороче!")
        return

    status = await message.answer("🎤 Processing..." if lang == "en" else "🎤 Обрабатываю...")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcription = await voice_service.download_and_transcribe(
            file_url, language=lang, prompt=_whisper_prompt(lang)
        )
        if transcription:
            transcription = await _correct_transcription(transcription)

        if transcription:
            updated_profile = await merge_followup_into_profile(
                profile_data,
                transcription,
                missing_fields,
                lang
            )
            await state.update_data(profile_data=updated_profile)
            await status.delete()
            await show_profile_confirmation(message, state, updated_profile, lang)
        else:
            await status.edit_text(
                "Couldn't hear that. Please type your answer." if lang == "en"
                else "Не расслышал. Напиши текстом."
            )
    except Exception as e:
        logger.error(f"Follow-up voice error: {e}")
        await status.edit_text(
            "Please type your answer." if lang == "en"
            else "Напиши текстом."
        )


async def merge_followup_into_profile(
    profile_data: dict,
    answer_text: str,
    missing_fields: list,
    lang: str
) -> dict:
    """Merge follow-up answer into existing profile data."""
    from openai import AsyncOpenAI

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        prompt = f"""Update this profile with new information from the user's follow-up answer.

CURRENT PROFILE:
- About: {profile_data.get("about") or "N/A"}
- Looking for: {profile_data.get("looking_for") or "N/A"}
- Can help with: {profile_data.get("can_help_with") or "N/A"}

MISSING FIELDS TO FILL: {", ".join(missing_fields)}

USER'S ANSWER:
{answer_text}

Extract and return JSON with ONLY the fields that should be updated:
{{
  "looking_for": "extracted info about who they want to meet",
  "can_help_with": "extracted info about their expertise/how they help"
}}

Return ONLY valid JSON with the fields to update. Keep existing values if not mentioned."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        updates = json.loads(text)

        # Merge updates into profile
        updated = profile_data.copy()
        for key, value in updates.items():
            if value and value not in ["N/A", "null", "None", ""]:
                updated[key] = value

        return updated

    except Exception as e:
        logger.error(f"Merge followup error: {e}")
        # Fallback: just add the raw answer
        updated = profile_data.copy()
        if "looking_for" in missing_fields:
            updated["looking_for"] = answer_text[:200]
        elif "can_help_with" in missing_fields:
            updated["can_help_with"] = answer_text[:200]
        return updated


@router.message(AudioOnboarding.waiting_audio, F.text)
async def handle_text_in_audio_mode(message: Message, state: FSMContext):
    """Handle text when expecting audio"""
    data = await state.get_data()
    lang = data.get("language", "ru")

    # Check if user wants to switch
    text_lower = message.text.lower()
    if text_lower in ["текст", "text", "type", "печатать"]:
        from adapters.telegram.handlers.onboarding_v2 import start_conversational_onboarding
        await state.clear()
        await start_conversational_onboarding(
            message, state,
            event_name=data.get("event_name"),
            event_code=data.get("pending_event")
        )
        return

    await message.answer(
        "🎤 Жду голосовое сообщение!\n\nИли напиши 'текст' для текстового онбординга." if lang == "ru"
        else "🎤 Waiting for voice message!\n\nOr type 'text' for text-based onboarding."
    )


# === Confirmation ===

async def show_profile_confirmation(
    message: Message,
    state: FSMContext,
    profile_data: dict,
    lang: str
):
    """Show extracted profile for confirmation with rich formatting"""

    is_ru = lang == "ru"
    header = AUDIO_CONFIRMATION_HEADER_RU if is_ru else AUDIO_CONFIRMATION_HEADER
    footer = AUDIO_CONFIRMATION_FOOTER_RU if is_ru else AUDIO_CONFIRMATION_FOOTER

    display_name = profile_data.get("display_name") or message.from_user.first_name
    profession = profile_data.get("profession")
    company = profile_data.get("company")
    location = profile_data.get("location")
    about = profile_data.get("about")
    looking_for = profile_data.get("looking_for")
    can_help_with = profile_data.get("can_help_with")
    interests = profile_data.get("interests", [])
    skills = profile_data.get("skills", [])

    lines = [header]

    # Name
    lines.append(f"👤 **{display_name}**")

    # Role @ Company
    if profession and company:
        lines.append(f"💼 {profession} @ {company}")
    elif profession:
        lines.append(f"💼 {profession}")
    elif company:
        lines.append(f"💼 {company}")

    # City
    if location:
        city = location.split(",")[0].strip()
        lines.append(f"📍 {city}")

    # About
    if about:
        lines.append(f"\n📝 {about}")

    # Looking for
    if looking_for:
        label = "Ищу" if is_ru else "Looking for"
        lines.append(f"\n🔍 **{label}:** {looking_for}")

    # Can help with
    if can_help_with:
        label = "Могу помочь" if is_ru else "Can help with"
        lines.append(f"💪 **{label}:** {can_help_with}")

    # Hashtags: merge interests + skills
    tags = []
    for i in interests[:5]:
        tags.append(f"#{i}")
    for s in skills[:5]:
        tag = s.replace(" ", "_").lower()
        if f"#{tag}" not in tags:
            tags.append(f"#{tag}")
    if tags:
        lines.append(f"\n🏷 {' '.join(tags[:8])}")

    lines.append(footer)

    text = "\n".join(lines)

    await message.answer(text, reply_markup=get_audio_confirm_keyboard(lang))
    await state.set_state(AudioOnboarding.confirming)


@router.callback_query(AudioOnboarding.confirming, F.data == "audio_confirm")
async def confirm_profile(callback: CallbackQuery, state: FSMContext):
    """User confirmed profile"""
    data = await state.get_data()
    profile_data = data.get("profile_data", {})
    lang = data.get("language", "ru")

    await callback.message.edit_text(
        "✨ Сохраняю профиль..." if lang == "ru" else "✨ Saving profile..."
    )

    # Save to database
    await save_audio_profile(callback, state, profile_data)


@router.callback_query(AudioOnboarding.confirming, F.data == "audio_add_details")
async def add_details(callback: CallbackQuery, state: FSMContext):
    """User wants to add more details to profile"""
    data = await state.get_data()
    lang = data.get("language", "ru")

    if lang == "ru":
        text = (
            "📝 Расскажи, что хочешь добавить или уточнить!\n\n"
            "Можешь записать голосовое или написать текстом."
        )
    else:
        text = (
            "📝 Tell me what you'd like to add or clarify!\n\n"
            "You can send a voice message or type."
        )

    await callback.message.edit_text(text)
    await state.set_state(AudioOnboarding.adding_details)
    await callback.answer()


@router.message(AudioOnboarding.confirming, F.text)
async def handle_confirmation_text(message: Message, state: FSMContext):
    """Handle text in confirmation - either confirm or treat as additional details"""
    data = await state.get_data()
    lang = data.get("language", "ru")
    text_lower = message.text.lower().strip()

    # Check for confirmation
    confirmations = ["да", "yes", "ок", "ok", "верно", "correct", "подтверждаю", "confirm", "good", "хорошо"]
    if text_lower in confirmations:
        profile_data = data.get("profile_data", {})
        await save_audio_profile(message, state, profile_data)
        return

    # If longer text - treat as additional details and merge into profile
    if len(message.text) > 10:
        await merge_additional_details(message, state, message.text)
        return

    # Short text that's not confirmation - ask to clarify
    if lang == "ru":
        text = "Скажи 'да' чтобы сохранить, или расскажи что добавить/изменить."
    else:
        text = "Say 'yes' to save, or tell me what to add/change."
    await message.answer(text)


@router.message(AudioOnboarding.confirming, F.voice)
async def handle_new_voice_in_confirmation(message: Message, state: FSMContext):
    """User recorded new voice - merge as additional details"""
    data = await state.get_data()
    lang = data.get("language", "en")

    status = await message.answer("🎤 Processing..." if lang == "en" else "🎤 Обрабатываю...")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcription = await voice_service.download_and_transcribe(
            file_url, language=lang, prompt=_whisper_prompt(lang)
        )
        if transcription:
            transcription = await _correct_transcription(transcription)

        if transcription:
            await status.delete()
            await merge_additional_details(message, state, transcription)
        else:
            await status.edit_text(
                "Couldn't hear that. Try again or type." if lang == "en"
                else "Не расслышал. Попробуй ещё раз или напиши."
            )
    except Exception as e:
        logger.error(f"Voice in confirmation error: {e}")
        await status.edit_text("Please try again." if lang == "en" else "Попробуй ещё раз.")


# === Adding Details State Handlers ===

@router.message(AudioOnboarding.adding_details, F.text)
async def handle_adding_details_text(message: Message, state: FSMContext):
    """Handle text when adding details"""
    await merge_additional_details(message, state, message.text)


@router.message(AudioOnboarding.adding_details, F.voice)
async def handle_adding_details_voice(message: Message, state: FSMContext):
    """Handle voice when adding details"""
    data = await state.get_data()
    lang = data.get("language", "en")

    status = await message.answer("🎤 Processing..." if lang == "en" else "🎤 Обрабатываю...")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcription = await voice_service.download_and_transcribe(
            file_url, language=lang, prompt=_whisper_prompt(lang)
        )
        if transcription:
            transcription = await _correct_transcription(transcription)

        if transcription:
            await status.delete()
            await merge_additional_details(message, state, transcription)
        else:
            await status.edit_text(
                "Couldn't hear that. Please type instead." if lang == "en"
                else "Не расслышал. Напиши текстом."
            )
    except Exception as e:
        logger.error(f"Adding details voice error: {e}")
        await status.edit_text("Please type instead." if lang == "en" else "Напиши текстом.")


async def merge_additional_details(message: Message, state: FSMContext, new_text: str):
    """Merge additional details into existing profile using LLM"""
    from openai import AsyncOpenAI

    data = await state.get_data()
    profile_data = data.get("profile_data", {})
    lang = data.get("language", "en")

    status = await message.answer("✨ Updating profile..." if lang == "en" else "✨ Обновляю профиль...")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        prompt = f"""Update this profile with NEW information from the user's message.
MERGE new info into existing fields - don't replace unless the new info is clearly a correction.

CURRENT PROFILE:
- Name: {profile_data.get("display_name") or "N/A"}
- About: {profile_data.get("about") or "N/A"}
- Looking for: {profile_data.get("looking_for") or "N/A"}
- Can help with: {profile_data.get("can_help_with") or "N/A"}
- Interests: {", ".join(profile_data.get("interests", [])) or "N/A"}
- Profession: {profile_data.get("profession") or "N/A"}
- Company: {profile_data.get("company") or "N/A"}

USER'S NEW MESSAGE:
{new_text}

Return JSON with ALL profile fields (keep existing values if not updated):
{{
  "display_name": "updated or existing name",
  "about": "merged about text",
  "looking_for": "merged looking_for text",
  "can_help_with": "merged can_help_with text",
  "interests": ["merged list of interests"],
  "goals": ["merged list of goals"],
  "profession": "updated or existing",
  "company": "updated or existing"
}}

RULES:
- If user corrects something, use the correction
- If user adds new info, append/merge it
- Keep the same language as existing content
- For interests/goals, add new ones but keep existing relevant ones

Return ONLY valid JSON."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.2
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        updates = json.loads(text)

        # Merge updates
        updated_profile = profile_data.copy()
        for key, value in updates.items():
            if value and value not in ["N/A", "null", "None", ""]:
                if key == "interests":
                    updated_profile[key] = list(set(value))[:5]
                elif key == "goals":
                    updated_profile[key] = list(set(value))[:3]
                else:
                    updated_profile[key] = value

        await state.update_data(profile_data=updated_profile)
        await status.delete()
        await show_profile_confirmation(message, state, updated_profile, lang)

    except Exception as e:
        logger.error(f"Merge additional details error: {e}")
        await status.edit_text(
            "Couldn't process that. Try again?" if lang == "en"
            else "Не получилось обработать. Попробуй ещё раз?"
        )
        await state.set_state(AudioOnboarding.confirming)


# === Save Profile ===

async def save_audio_profile(message_or_callback, state: FSMContext, profile_data: dict):
    """Save extracted profile to database"""
    # Get message object
    if hasattr(message_or_callback, 'message'):
        message = message_or_callback.message
        user_id = str(message_or_callback.from_user.id)
        tg_username = message_or_callback.from_user.username
    else:
        message = message_or_callback
        user_id = str(message.from_user.id)
        tg_username = message.from_user.username

    data = await state.get_data()
    lang = data.get("language", "ru")

    # Build bio from extracted data (clean newline-separated format)
    bio_lines = []
    if profile_data.get("about"):
        bio_lines.append(profile_data["about"])
    if profile_data.get("profession") and profile_data.get("company"):
        bio_lines.append(f"💼 {profile_data['profession']} @ {profile_data['company']}")
    elif profile_data.get("profession"):
        bio_lines.append(f"💼 {profile_data['profession']}")
    elif profile_data.get("company"):
        bio_lines.append(f"💼 {profile_data['company']}")
    if profile_data.get("location"):
        city = profile_data["location"].split(",")[0].strip()
        bio_lines.append(f"📍 {city}")

    bio = "\n".join(bio_lines)[:500] if bio_lines else ""

    # Extract city from location
    city = profile_data.get("location")
    if city:
        # Clean up location - take first part if comma-separated
        city = city.split(",")[0].strip()[:100]

    # Update user with all extracted data (including new fields)
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        user_id,
        display_name=profile_data.get("display_name") or data.get("user_first_name"),
        interests=profile_data.get("interests", [])[:5],
        goals=profile_data.get("goals", [])[:3],
        bio=bio,
        looking_for=profile_data.get("looking_for", "")[:300] or None,
        can_help_with=profile_data.get("can_help_with", "")[:300] or None,
        # New fields from enhanced extraction
        profession=profile_data.get("profession"),
        company=profile_data.get("company"),
        skills=profile_data.get("skills", [])[:10],
        city_current=city,
        onboarding_completed=True
    )

    # Generate AI summary
    user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)
    if user:
        from infrastructure.ai.openai_service import OpenAIService
        ai_service = OpenAIService()
        summary = await ai_service.generate_user_summary(user.model_dump())
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            user_id,
            ai_summary=summary
        )

        # Generate vector embeddings and run matching in background (non-blocking)
        async def generate_embeddings_and_match(user_obj, event_code, chat_id):
            try:
                # Step 1: Generate embeddings
                result = await embedding_service.generate_embeddings(user_obj)
                if result:
                    profile_emb, interests_emb, expertise_emb = result
                    user_repo = SupabaseUserRepository()
                    await user_repo.update_embeddings(
                        user_obj.id,
                        profile_embedding=profile_emb,
                        interests_embedding=interests_emb,
                        expertise_embedding=expertise_emb
                    )
                    logger.info(f"Generated embeddings for user {user_obj.id}")

                    # Step 2: Run matching if user is in an event
                    if event_code:
                        try:
                            updated_user = await user_repo.get_by_id(user_obj.id)
                            if updated_user and updated_user.current_event_id:
                                matches = await matching_service.find_matches_vector(
                                    user=updated_user,
                                    event_id=updated_user.current_event_id,
                                    limit=5
                                )
                                match_count = len(matches) if matches else 0
                                logger.info(f"Auto-created {match_count} matches for user {user_obj.id}")

                                # Send notifications for each match
                                if matches and chat_id:
                                    from adapters.telegram.handlers.matches import notify_about_match
                                    for partner, result_with_id in matches[:3]:
                                        partner_name = partner.display_name or partner.first_name or "Someone"
                                        await notify_about_match(
                                            user_telegram_id=chat_id,
                                            partner_name=partner_name,
                                            explanation=result_with_id.explanation,
                                            icebreaker=result_with_id.icebreaker,
                                            match_id=str(result_with_id.match_id),
                                            lang=lang,
                                            partner_username=partner.username
                                        )
                        except Exception as me:
                            logger.error(f"Background matching failed for user {user_obj.id}: {me}", exc_info=True)
                else:
                    logger.warning(f"Embeddings returned None for user {user_obj.id}")
                    if chat_id:
                        try:
                            await bot.send_message(
                                chat_id,
                                "Your profile is saved, but matching optimization is still loading. "
                                "Try /find_matches in a minute for best results."
                            )
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Background embedding generation failed for user {user_obj.id}: {e}", exc_info=True)
                if chat_id:
                    try:
                        await bot.send_message(
                            chat_id,
                            "Profile saved! Matching is temporarily slower — try /find_matches in a minute."
                        )
                    except Exception:
                        pass

        # Fire and forget with error tracking
        import asyncio
        pending_event_code = data.get("pending_event")
        chat_id = message_or_callback.message.chat.id if hasattr(message_or_callback, 'message') else message_or_callback.chat.id
        task = asyncio.create_task(
            generate_embeddings_and_match(user, pending_event_code, chat_id)
        )
        task.add_done_callback(
            lambda t: _on_background_task_done(t, user_id=str(user.id))
        )

    # Handle event join
    pending_event = data.get("pending_event")
    event = None

    if pending_event:
        success, msg, event = await event_service.join_event(
            pending_event,
            MessagePlatform.TELEGRAM,
            user_id
        )
        # Note: event_service.join_event() already updates current_event_id
        # No need to update again here

    # Save event context for personalization
    await state.update_data(
        pending_event=pending_event,
        event_id=str(event.id) if event else None,
        event_name=event.name if event else None
    )

    # Skip selfie request during onboarding - will ask when user opens Matches tab
    # Go directly to personalization flow
    await finish_onboarding_after_selfie(message, state)


async def show_top_matches(message, user, event, lang: str, tg_username: str = None):
    """Show top 3 matches after onboarding and notify matched users"""
    from config.features import Features
    from adapters.telegram.handlers.matches import notify_about_match

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
            # Fallback to old method if no embeddings
            matches = await matching_service.find_and_create_matches_for_user(
                user=user,
                event_id=event.id,
                limit=Features.SHOW_TOP_MATCHES
            )

        if not matches:
            text = (
                "👀 Пока мало участников для матчинга.\n"
                "Как только появятся — напишу тебе!"
            ) if lang == "ru" else (
                "👀 Not enough participants yet.\n"
                "I'll notify you when matches are found!"
            )
            await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
            return

        # Notify matched users about new match (the other person)
        new_user_name = user.display_name or user.first_name or "Someone"
        for matched_user, match_result in matches:
            if matched_user.platform_user_id:
                try:
                    # Detect matched user's language (default to ru for now)
                    matched_lang = "ru"

                    await notify_about_match(
                        user_telegram_id=int(matched_user.platform_user_id),
                        partner_name=new_user_name,
                        explanation=match_result.explanation,
                        icebreaker=match_result.icebreaker,
                        match_id=str(match_result.match_id),
                        lang=matched_lang
                    )
                    logger.info(f"Notified user {matched_user.platform_user_id} about new match with {user.id}")
                except Exception as e:
                    logger.error(f"Failed to notify user {matched_user.platform_user_id}: {e}")

        # Format top matches message
        if lang == "ru":
            header = f"🎯 <b>Топ-{len(matches)} людей на {event.name}:</b>\n\n"
        else:
            header = f"🎯 <b>Top {len(matches)} people to meet at {event.name}:</b>\n\n"

        lines = []
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        for i, (matched_user, match_result) in enumerate(matches):
            emoji = emojis[i] if i < len(emojis) else f"{i+1}."

            # Name and role
            name = matched_user.display_name or matched_user.first_name or "Unknown"
            role_line = matched_user.bio[:50] if matched_user.bio else ""

            # Why match
            why = match_result.explanation[:100] if match_result.explanation else ""

            # Contact
            contact = ""
            if matched_user.username:
                contact = f"📱 @{matched_user.username}"

            line = f"{emoji} <b>{name}</b>"
            if role_line:
                line += f"\n   {role_line}"
            if why:
                line += f"\n   💡 {why}"
            if contact:
                line += f"\n   {contact}"

            lines.append(line)

        text = header + "\n\n".join(lines)

        # Add icebreaker tip
        if matches:
            first_match = matches[0][1]
            if first_match.icebreaker:
                if lang == "ru":
                    text += f"\n\n💬 <i>Начни разговор: {first_match.icebreaker}</i>"
                else:
                    text += f"\n\n💬 <i>Start with: {first_match.icebreaker}</i>"

        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))

    except Exception as e:
        logger.error(f"Error showing top matches: {e}")
        text = (
            "✓ Профиль сохранён! Напишу когда найду матчи."
        ) if lang == "ru" else (
            "✓ Profile saved! I'll notify you about matches."
        )
        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))


# === Selfie Handlers ===

@router.message(AudioOnboarding.waiting_selfie, F.photo)
async def handle_selfie_photo(message: Message, state: FSMContext):
    """Handle selfie photo upload"""
    data = await state.get_data()
    lang = data.get("language", "ru")
    user_id = str(message.from_user.id)

    try:
        # Get the largest photo
        photo = message.photo[-1]

        # Save photo URL (Telegram file_id can be used to retrieve later)
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            user_id,
            photo_url=photo.file_id  # Store file_id for later retrieval
        )

        if lang == "ru":
            text = "✅ Фото сохранено! Теперь тебя легко найти на ивенте."
        else:
            text = "✅ Photo saved! Now you're easy to spot at the event."

        await message.answer(text)
    except Exception as e:
        logger.error(f"Failed to save photo for user {user_id}: {e}")
        # Continue anyway - photo is optional

    # Continue to show matches
    await finish_onboarding_after_selfie(message, state)


@router.callback_query(AudioOnboarding.waiting_selfie, F.data == "skip_selfie")
async def skip_selfie(callback: CallbackQuery, state: FSMContext):
    """Skip selfie upload"""
    # Answer callback immediately to prevent Telegram retry
    await callback.answer()

    data = await state.get_data()
    lang = data.get("language", "ru")

    if lang == "ru":
        text = "👌 Хорошо, можешь добавить фото позже в профиле."
    else:
        text = "👌 No problem, you can add a photo later in your profile."

    try:
        await callback.message.edit_text(text)
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")

    # Continue to show matches
    await finish_onboarding_after_selfie(callback.message, state, callback.from_user.id)


@router.message(AudioOnboarding.waiting_selfie, F.text)
async def handle_selfie_text(message: Message, state: FSMContext):
    """Handle text when expecting selfie"""
    data = await state.get_data()
    lang = data.get("language", "ru")

    text_lower = message.text.lower()
    if text_lower in ["skip", "пропустить", "нет", "no", "позже", "later"]:
        # Skip selfie
        if lang == "ru":
            text = "👌 Хорошо, можешь добавить фото позже в профиле."
        else:
            text = "👌 No problem, you can add a photo later in your profile."
        await message.answer(text)
        await finish_onboarding_after_selfie(message, state)
    else:
        if lang == "ru":
            text = "📸 Отправь фото или нажми 'Пропустить'"
        else:
            text = "📸 Send a photo or tap 'Skip'"
        await message.answer(text, reply_markup=get_selfie_keyboard(lang))


async def finish_onboarding_after_selfie(message: Message, state: FSMContext, user_tg_id: int = None):
    """Complete onboarding after selfie step - start personalization flow"""
    try:
        data = await state.get_data()
        lang = data.get("language", "ru")
        event_id = data.get("event_id")
        event_name = data.get("event_name")

        # Get user
        tg_id = user_tg_id or message.from_user.id

        # Start personalization flow instead of going directly to matches
        from adapters.telegram.handlers.personalization import start_personalization

        await start_personalization(
            message=message,
            state=state,
            event_name=event_name,
            event_id=event_id,
            lang=lang
        )
        # Note: state is NOT cleared here - personalization will handle it

    except Exception as e:
        logger.error(f"Error in finish_onboarding_after_selfie: {e}")
        # Fallback: show matches directly if personalization fails
        try:
            data = await state.get_data()
            lang = data.get("language", "ru")
            event_id = data.get("event_id")
            event_name = data.get("event_name")
            tg_id = user_tg_id or message.from_user.id
            user_id = str(tg_id)
            user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)

            if event_id and user:
                from uuid import UUID

                class EventWrapper:
                    def __init__(self, id, name):
                        self.id = UUID(id)
                        self.name = name

                event = EventWrapper(event_id, event_name)
                await show_top_matches(message, user, event, lang, user.username)
            else:
                await message.answer(
                    "✓ Профиль готов!" if lang == "ru" else "✓ Profile ready!",
                    reply_markup=get_main_menu_keyboard(lang)
                )
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")
            await message.answer(
                "✓ Profile ready!",
                reply_markup=get_main_menu_keyboard("en")
            )
        finally:
            await state.clear()


# === Profile Extraction ===

async def extract_profile_from_transcription(
    transcription: str,
    event_name: str = None,
    detected_lang: str = "ru",
    return_raw: bool = False
) -> dict:
    """Extract structured profile data from voice transcription.

    Uses Chain-of-thought extraction for better analysis.
    If return_raw=True, returns the full LLM response for debugging.
    """
    from openai import AsyncOpenAI
    from config.settings import settings

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)

    prompt = AUDIO_EXTRACTION_PROMPT.format(
        transcription=transcription,
        event_name=event_name or "general networking",
        language=detected_lang
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,  # Chain-of-thought + JSON
            temperature=0.1  # Low for consistent extraction
        )

        text = response.choices[0].message.content

        # For debugging - return raw response
        if return_raw:
            return {"raw_response": text, "transcription": transcription}

        # Extract JSON from chain-of-thought response
        # Look for "## JSON:" section or just find the JSON block
        json_text = text

        # Try to find JSON section marker
        if "## JSON:" in text:
            json_text = text.split("## JSON:")[-1]
        elif "```json" in text:
            json_text = text.split("```json")[-1].split("```")[0]
        elif "{" in text:
            # Find the last JSON block (the output)
            start = text.rfind("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                json_text = text[start:end]

        # Clean JSON from markdown
        json_text = re.sub(r'```json\s*', '', json_text)
        json_text = re.sub(r'```\s*', '', json_text)
        json_text = json_text.strip()

        data = json.loads(json_text)
        return validate_extracted_profile(data)

    except Exception as e:
        logger.error(f"Profile extraction error: {e}")
        # Return minimal fallback - do NOT add fake looking_for/can_help_with
        # Better to have empty fields than fabricated ones that cause bad matches
        return {
            "display_name": "",  # Will use first_name as fallback during save
            "about": transcription[:200] if transcription else "",
            "looking_for": "",  # Empty - let matching handle this properly
            "can_help_with": "",  # Empty - better than fake data
            "interests": [],  # Empty - don't assume interests
            "goals": ["networking"],  # Only networking is safe to assume
            "profession": None,
            "company": None,
            "location": None,
            "skills": [],
            "experience_level": None,
            "confidence_score": 0.1  # Very low - extraction failed
        }


def validate_extracted_profile(data: dict) -> dict:
    """Validate and normalize extracted profile data"""
    valid_interests = {
        "tech", "business", "startups", "crypto", "design", "art",
        "music", "books", "travel", "sport", "wellness", "psychology",
        "gaming", "ecology", "cooking", "cinema", "science", "education",
        "marketing", "finance", "AI", "ML", "product", "web3", "UX",
        "fitness", "growth", "investing", "sales", "HR", "legal",
        "healthcare", "real_estate"
    }
    valid_goals = {
        "networking", "friends", "business", "mentorship",
        "cofounders", "creative", "learning", "dating", "hiring",
        "investing", "partnerships", "advice", "collaboration"
    }
    valid_experience_levels = {
        "junior", "mid", "senior", "founder", "executive"
    }

    # Filter to valid values
    interests = [i for i in data.get("interests", []) if i in valid_interests]
    goals = [g for g in data.get("goals", []) if g in valid_goals]

    # Ensure minimum
    if not interests:
        interests = ["networking"]
    if not goals:
        goals = ["networking"]

    # Validate experience level
    experience_level = data.get("experience_level")
    if experience_level and experience_level not in valid_experience_levels:
        experience_level = None

    # Extract skills as list
    skills = data.get("skills", [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",")]
    skills = skills[:10]  # Limit to 10 skills

    return {
        "display_name": data.get("display_name"),
        "about": data.get("about", "")[:500],
        "looking_for": data.get("looking_for", "")[:300],
        "can_help_with": data.get("can_help_with", "")[:300],
        "interests": interests[:5],
        "goals": goals[:3],
        "profession": data.get("profession"),
        "company": data.get("company"),
        "industry": data.get("industry"),
        "experience_level": experience_level,
        "skills": skills,
        "location": data.get("location"),
        "personality_traits": data.get("personality_traits", [])[:3],
        "unique_value": data.get("unique_value"),
        "link": data.get("link"),
        "raw_highlights": data.get("raw_highlights", [])[:5],
        "confidence_score": data.get("confidence_score", 0.5),
        "extraction_notes": data.get("extraction_notes")
    }


# === ADMIN: Test Extraction Command ===

class TestExtractStates(StatesGroup):
    """States for test extraction"""
    waiting_voice = State()


@router.message(Command("test_extract"))
async def test_extract_command(message: Message, state: FSMContext):
    """Admin command to test extraction on voice messages"""
    from config.settings import settings

    # Check if admin
    is_admin = message.from_user.id in settings.admin_telegram_ids
    is_debug = settings.debug

    if not is_admin and not is_debug:
        await message.answer("⛔ Admin only command")
        return

    lang = detect_lang(message)
    if lang == "ru":
        text = (
            "🔬 <b>Тест экстракции</b>\n\n"
            "Отправь голосовое сообщение — покажу raw JSON результат экстракции.\n\n"
            "Напиши /cancel чтобы отменить."
        )
    else:
        text = (
            "🔬 <b>Extraction Test</b>\n\n"
            "Send a voice message — I'll show the raw JSON extraction result.\n\n"
            "Type /cancel to cancel."
        )

    await message.answer(text)
    await state.set_state(TestExtractStates.waiting_voice)


@router.message(TestExtractStates.waiting_voice, F.voice)
async def test_extract_voice(message: Message, state: FSMContext):
    """Process voice for extraction test"""
    lang = detect_lang(message)

    status = await message.answer("🔬 Processing extraction test..." if lang == "en" else "🔬 Тестирую экстракцию...")

    try:
        # Get voice file
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

        # Transcribe + correct
        transcription = await voice_service.download_and_transcribe(
            file_url, language=lang, prompt=_whisper_prompt(lang)
        )

        if not transcription:
            await status.edit_text("❌ Could not transcribe audio" if lang == "en" else "❌ Не удалось транскрибировать")
            return

        transcription = await _correct_transcription(transcription)

        # Extract with raw=True to get full response
        result = await extract_profile_from_transcription(
            transcription,
            event_name="Test Event",
            detected_lang=lang,
            return_raw=True
        )

        if "raw_response" in result:
            # Show raw response
            raw = result["raw_response"]
            # Truncate if too long for Telegram
            if len(raw) > 3500:
                raw = raw[:3500] + "\n\n... (truncated)"

            await status.delete()
            await message.answer(
                f"📝 <b>Transcription:</b>\n<code>{transcription[:500]}</code>\n\n"
                f"🔬 <b>Raw Extraction:</b>\n<pre>{raw}</pre>",
                parse_mode="HTML"
            )
        else:
            # Show parsed result
            await status.delete()
            result_json = json.dumps(result, indent=2, ensure_ascii=False)
            if len(result_json) > 3500:
                result_json = result_json[:3500] + "\n... (truncated)"

            await message.answer(
                f"📝 <b>Transcription:</b>\n<code>{transcription[:300]}</code>\n\n"
                f"✅ <b>Parsed JSON:</b>\n<pre>{result_json}</pre>",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Test extraction error: {e}")
        await status.edit_text(f"❌ Error: {str(e)[:200]}")

    await state.clear()


@router.message(TestExtractStates.waiting_voice, Command("cancel"))
async def cancel_test_extract(message: Message, state: FSMContext):
    """Cancel test extraction"""
    await state.clear()
    await message.answer("✓ Cancelled" if detect_lang(message) == "en" else "✓ Отменено")


@router.message(TestExtractStates.waiting_voice, F.text)
async def test_extract_text_fallback(message: Message, state: FSMContext):
    """Handle text when expecting voice"""
    if message.text.startswith("/"):
        await state.clear()
        return

    lang = detect_lang(message)
    await message.answer(
        "🎤 Send a voice message for extraction test" if lang == "en"
        else "🎤 Отправь голосовое для теста экстракции"
    )
