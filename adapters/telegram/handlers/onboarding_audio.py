"""
Audio Onboarding Handler - 60-second voice message flow.
User speaks naturally, we extract structured profile data.
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
    AUDIO_EXTRACTION_PROMPT,
    AUDIO_CONFIRMATION_TEMPLATE,
    AUDIO_CONFIRMATION_TEMPLATE_RU,
)
from adapters.telegram.loader import user_service, event_service, voice_service, bot
from adapters.telegram.keyboards import get_main_menu_keyboard
from config.settings import settings

logger = logging.getLogger(__name__)

router = Router()


# === FSM States ===

class AudioOnboarding(StatesGroup):
    """States for audio onboarding"""
    waiting_audio = State()      # Waiting for voice message
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
    lang: str = "ru"
):
    """
    Start audio onboarding flow.
    Called from start handler.
    """
    # Save context
    await state.update_data(
        event_name=event_name,
        pending_event=event_code,
        language=lang,
        user_first_name=message.from_user.first_name
    )

    # Choose language
    guide = AUDIO_GUIDE_PROMPT_RU if lang == "ru" else AUDIO_GUIDE_PROMPT

    # Send guide
    if event_name:
        intro = f"👋 Привет! Ты на <b>{event_name}</b>\n\n" if lang == "ru" else f"👋 Hi! You're at <b>{event_name}</b>\n\n"
    else:
        intro = "👋 Привет! Давай познакомимся.\n\n" if lang == "ru" else "👋 Hi! Let's get to know each other.\n\n"

    await message.answer(
        intro + guide,
        reply_markup=get_audio_start_keyboard(lang)
    )
    await state.set_state(AudioOnboarding.waiting_audio)


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
    lang = data.get("language", "ru")

    # Status message
    status = await message.answer("🎤 Обрабатываю..." if lang == "ru" else "🎤 Processing...")

    try:
        # Get voice file
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

        # Transcribe
        transcription = await voice_service.download_and_transcribe(file_url)

        if not transcription or len(transcription) < 20:
            await status.edit_text(
                "Не расслышал 😅 Попробуй ещё раз, говори чётче." if lang == "ru"
                else "Couldn't hear that clearly 😅 Please try again, speak clearly."
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

        # Show confirmation
        await status.delete()
        await show_profile_confirmation(message, state, profile_data, lang)

    except Exception as e:
        logger.error(f"Audio processing error: {e}")
        await status.edit_text(
            "Что-то пошло не так. Попробуй ещё раз." if lang == "ru"
            else "Something went wrong. Please try again."
        )


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
    else:
        message = message_or_callback
        user_id = str(message.from_user.id)

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

    # Update user
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        user_id,
        display_name=profile_data.get("display_name") or data.get("user_first_name"),
        interests=profile_data.get("interests", [])[:5],
        goals=profile_data.get("goals", [])[:3],
        bio=bio,
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
    if pending_event:
        success, msg, event = await event_service.join_event(
            pending_event,
            MessagePlatform.TELEGRAM,
            user_id
        )

        if success and event:
            text = (
                f"🎉 Ты в ивенте <b>{event.name}</b>!\n\n"
                "Уже ищу для тебя интересных людей. Напишу, когда найду!"
            ) if lang == "ru" else (
                f"🎉 You're in <b>{event.name}</b>!\n\n"
                "Already finding interesting people for you!"
            )
        else:
            text = "✓ Профиль сохранён!" if lang == "ru" else "✓ Profile saved!"
    else:
        text = (
            "🎉 <b>Профиль готов!</b>\n\n"
            "Сканируй QR-коды на ивентах, чтобы находить интересных людей!"
        ) if lang == "ru" else (
            "🎉 <b>Profile ready!</b>\n\n"
            "Scan QR codes at events to meet interesting people!"
        )

    await message.answer(text, reply_markup=get_main_menu_keyboard())
    await state.clear()


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
