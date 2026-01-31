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

import json
import re
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.domain.models import MessagePlatform
from core.prompts.audio_onboarding import (
    AUDIO_GUIDE_PROMPT_RU,
    AUDIO_GUIDE_PROMPT,
    AUDIO_INTRO_PROMPT,
    AUDIO_EXTRACTION_PROMPT,
    AUDIO_VALIDATION_PROMPT,
    AUDIO_CONFIRMATION_TEMPLATE,
    AUDIO_CONFIRMATION_TEMPLATE_RU,
)
from adapters.telegram.loader import user_service, event_service, voice_service, matching_service, bot
from adapters.telegram.keyboards import get_main_menu_keyboard
from config.settings import settings

logger = logging.getLogger(__name__)

router = Router()


# === Language Detection ===

def detect_language(message: Message) -> str:
    """Detect user language from Telegram settings. Default: English."""
    lang_code = message.from_user.language_code or "en"

    # Map language codes to our supported languages
    if lang_code.startswith("ru"):
        return "ru"
    elif lang_code.startswith("uk"):  # Ukrainian -> use Russian
        return "ru"
    else:
        return "en"  # Default to English for all other languages


def get_language_name(lang: str) -> str:
    """Get full language name for prompts."""
    return "Russian" if lang == "ru" else "English"


# === FSM States ===

class AudioOnboarding(StatesGroup):
    """States for audio onboarding"""
    waiting_audio = State()      # Waiting for voice message
    waiting_followup = State()   # Waiting for follow-up answer
    confirming = State()         # Confirming extracted profile


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
        builder.button(text="🎤 Перезаписать", callback_data="audio_retry")
    else:
        builder.button(text="✅ Looks good!", callback_data="audio_confirm")
        builder.button(text="🎤 Re-record", callback_data="audio_retry")
    builder.adjust(2)
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
        lang = detect_language(message)

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
    """Generate personalized intro using LLM."""
    from openai import AsyncOpenAI

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        event_context = f"event called '{event_name}'" if event_name else "networking event"
        language_name = get_language_name(lang)

        prompt = AUDIO_INTRO_PROMPT.format(
            event_context=event_context,
            language_name=language_name,
            first_name=first_name or "friend"
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Failed to generate intro: {e}")
        # Fallback to static guide
        if lang == "ru":
            intro = f"👋 Привет{', ' + first_name if first_name else ''}!\n\n"
            return intro + AUDIO_GUIDE_PROMPT_RU
        else:
            intro = f"👋 Hi{' ' + first_name if first_name else ''}!\n\n"
            return intro + AUDIO_GUIDE_PROMPT


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
    """Switch to conversational onboarding"""
    from adapters.telegram.handlers.onboarding_v2 import start_conversational_onboarding

    data = await state.get_data()
    await state.clear()

    # Delete old message with buttons to avoid confusion
    try:
        await callback.message.delete()
    except Exception:
        pass  # Message might be too old to delete

    # Create a fake message object with correct user info for the new flow
    await start_conversational_onboarding(
        callback.message,
        state,
        event_name=data.get("event_name"),
        event_code=data.get("pending_event")
    )
    await callback.answer()


@router.message(AudioOnboarding.waiting_audio, F.voice)
async def process_audio(message: Message, state: FSMContext):
    """Process voice message and extract profile"""
    data = await state.get_data()
    lang = data.get("language", "en")

    # Status message
    status = await message.answer("🎤 Processing..." if lang == "en" else "🎤 Обрабатываю...")

    try:
        # Get voice file
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

        # Transcribe
        transcription = await voice_service.download_and_transcribe(file_url)

        if not transcription or len(transcription) < 20:
            await status.edit_text(
                "Couldn't hear that clearly 😅 Please try again, speak clearly." if lang == "en"
                else "Не расслышал 😅 Попробуй ещё раз, говори чётче."
            )
            return

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

        # Validate profile completeness
        validation = await validate_profile_completeness(profile_data, lang)

        if validation["is_complete"]:
            # Profile is complete, show confirmation
            await show_profile_confirmation(message, state, profile_data, lang)
        else:
            # Missing important info, ask follow-up
            follow_up = validation.get("follow_up_question")
            if follow_up:
                await state.update_data(missing_fields=validation["missing_fields"])
                await message.answer(follow_up)
                await state.set_state(AudioOnboarding.waiting_followup)
            else:
                # No follow-up generated, just show what we have
                await show_profile_confirmation(message, state, profile_data, lang)

    except Exception as e:
        logger.error(f"Audio processing error: {e}")
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

    status = await message.answer("🎤 Processing..." if lang == "en" else "🎤 Обрабатываю...")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcription = await voice_service.download_and_transcribe(file_url)

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
    """Show extracted profile for confirmation"""

    # Format interests
    interests = profile_data.get("interests", [])
    interests_display = " ".join([f"#{i}" for i in interests[:5]]) if interests else ""

    # Choose template
    template = AUDIO_CONFIRMATION_TEMPLATE_RU if lang == "ru" else AUDIO_CONFIRMATION_TEMPLATE

    text = template.format(
        display_name=profile_data.get("display_name") or message.from_user.first_name,
        about=profile_data.get("about") or "—",
        looking_for=profile_data.get("looking_for") or "—",
        can_help_with=profile_data.get("can_help_with") or "—",
        interests_display=interests_display
    )

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


@router.callback_query(AudioOnboarding.confirming, F.data == "audio_retry")
async def retry_audio(callback: CallbackQuery, state: FSMContext):
    """User wants to re-record"""
    data = await state.get_data()
    lang = data.get("language", "ru")

    await callback.message.edit_text(
        "🎤 Окей! Записывай новое голосовое сообщение." if lang == "ru"
        else "🎤 Okay! Record a new voice message."
    )
    await state.set_state(AudioOnboarding.waiting_audio)
    await callback.answer()


@router.message(AudioOnboarding.confirming, F.text)
async def handle_confirmation_text(message: Message, state: FSMContext):
    """Handle text confirmation"""
    data = await state.get_data()
    lang = data.get("language", "ru")
    text_lower = message.text.lower().strip()

    # Check for confirmation
    confirmations = ["да", "yes", "ок", "ok", "верно", "correct", "подтверждаю", "confirm"]
    if text_lower in confirmations:
        profile_data = data.get("profile_data", {})
        await save_audio_profile(message, state, profile_data)
        return

    # Check for retry
    retries = ["нет", "no", "заново", "retry", "перезаписать"]
    if text_lower in retries:
        await message.answer(
            "🎤 Окей! Записывай новое голосовое сообщение." if lang == "ru"
            else "🎤 Okay! Record a new voice message."
        )
        await state.set_state(AudioOnboarding.waiting_audio)
        return

    await message.answer(
        "Скажи 'да' для подтверждения или 'нет' чтобы перезаписать." if lang == "ru"
        else "Say 'yes' to confirm or 'no' to re-record."
    )


@router.message(AudioOnboarding.confirming, F.voice)
async def handle_new_voice_in_confirmation(message: Message, state: FSMContext):
    """User recorded new voice instead of confirming - process it"""
    # Treat as re-record
    await state.set_state(AudioOnboarding.waiting_audio)
    await process_audio(message, state)


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

    # Build bio from extracted data
    bio_parts = []
    if profile_data.get("about"):
        bio_parts.append(profile_data["about"])
    if profile_data.get("profession"):
        bio_parts.append(f"🏢 {profile_data['profession']}")
    if profile_data.get("company"):
        bio_parts.append(f"@ {profile_data['company']}")

    bio = " | ".join(bio_parts)[:500] if bio_parts else ""

    # Update user with all extracted data
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        user_id,
        display_name=profile_data.get("display_name") or data.get("user_first_name"),
        interests=profile_data.get("interests", [])[:5],
        goals=profile_data.get("goals", [])[:3],
        bio=bio,
        looking_for=profile_data.get("looking_for", "")[:300] or None,
        can_help_with=profile_data.get("can_help_with", "")[:300] or None,
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

    # Handle event join
    pending_event = data.get("pending_event")
    event = None

    if pending_event:
        success, msg, event = await event_service.join_event(
            pending_event,
            MessagePlatform.TELEGRAM,
            user_id
        )

        if success and event:
            # Save current_event_id to user profile
            from uuid import UUID
            await user_service.update_user(
                MessagePlatform.TELEGRAM,
                user_id,
                current_event_id=event.id
            )

            # Re-fetch user with updated current_event_id
            user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)

            text = (
                f"🎉 Ты в ивенте <b>{event.name}</b>!\n\n"
                "Ищу для тебя интересных людей..."
            ) if lang == "ru" else (
                f"🎉 You're in <b>{event.name}</b>!\n\n"
                "Finding interesting people for you..."
            )
            await message.answer(text)

            # Find and show top matches
            if user:
                await show_top_matches(message, user, event, lang, tg_username)
        else:
            text = "✓ Профиль сохранён!" if lang == "ru" else "✓ Profile saved!"
            await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
    else:
        text = (
            "🎉 <b>Профиль готов!</b>\n\n"
            "Сканируй QR-коды на ивентах, чтобы находить интересных людей!"
        ) if lang == "ru" else (
            "🎉 <b>Profile ready!</b>\n\n"
            "Scan QR codes at events to meet interesting people!"
        )
        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))

    await state.clear()


async def show_top_matches(message, user, event, lang: str, tg_username: str = None):
    """Show top 3 matches after onboarding"""
    from config.features import Features

    try:
        # Find matches for this user
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


# === Profile Extraction ===

async def extract_profile_from_transcription(
    transcription: str,
    event_name: str = None,
    detected_lang: str = "ru"
) -> dict:
    """Extract structured profile data from voice transcription"""
    from openai import AsyncOpenAI
    from config.settings import settings

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    prompt = AUDIO_EXTRACTION_PROMPT.format(
        transcription=transcription,
        event_name=event_name or "general networking",
        language=detected_lang
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.1  # Low for consistent extraction
        )

        text = response.choices[0].message.content

        # Clean JSON from markdown
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        data = json.loads(text)
        return validate_extracted_profile(data)

    except Exception as e:
        logger.error(f"Profile extraction error: {e}")
        # Return minimal fallback
        return {
            "display_name": None,
            "about": transcription[:200],
            "looking_for": "",
            "can_help_with": "",
            "interests": ["networking"],
            "goals": ["networking"],
            "confidence_score": 0.3
        }


def validate_extracted_profile(data: dict) -> dict:
    """Validate and normalize extracted profile data"""
    valid_interests = {
        "tech", "business", "startups", "crypto", "design", "art",
        "music", "books", "travel", "sport", "wellness", "psychology",
        "gaming", "ecology", "cooking", "cinema", "science", "education",
        "marketing", "finance"
    }
    valid_goals = {
        "networking", "friends", "business", "mentorship",
        "cofounders", "creative", "learning", "dating", "hiring", "investing"
    }

    # Filter to valid values
    interests = [i for i in data.get("interests", []) if i in valid_interests]
    goals = [g for g in data.get("goals", []) if g in valid_goals]

    # Ensure minimum
    if not interests:
        interests = ["networking"]
    if not goals:
        goals = ["networking"]

    return {
        "display_name": data.get("display_name"),
        "about": data.get("about", "")[:500],
        "looking_for": data.get("looking_for", "")[:300],
        "can_help_with": data.get("can_help_with", "")[:300],
        "interests": interests[:5],
        "goals": goals[:3],
        "profession": data.get("profession"),
        "company": data.get("company"),
        "link": data.get("link"),
        "raw_highlights": data.get("raw_highlights", [])[:5],
        "confidence_score": data.get("confidence_score", 0.5)
    }
