"""
Conversational Onboarding Handler v2 - LLM-driven, multilingual.
Uses natural conversation instead of scripted buttons.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.domain.models import MessagePlatform
from core.services.conversation_service import (
    ConversationService,
    serialize_state,
    deserialize_state,
)
from infrastructure.ai.conversation_ai import create_conversation_ai
from adapters.telegram.loader import user_service, event_service, bot, embedding_service
from infrastructure.database.user_repository import SupabaseUserRepository
from adapters.telegram.keyboards import get_main_menu_keyboard
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup


def get_selfie_keyboard_v2(lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for selfie request"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="⏩ Пропустить", callback_data="skip_selfie_v2")
    else:
        builder.button(text="⏩ Skip", callback_data="skip_selfie_v2")
    return builder.as_markup()

logger = logging.getLogger(__name__)

router = Router(name="onboarding_v2")


# === FSM States ===

class ConversationalOnboarding(StatesGroup):
    """States for conversational onboarding"""
    in_conversation = State()  # Active conversation with LLM
    waiting_selfie = State()   # Waiting for selfie photo


# === Service initialization ===

# Create conversation AI (can be configured via settings)
conversation_ai = create_conversation_ai(provider="openai")
conversation_service = ConversationService(conversation_ai)


# === Handlers ===

async def start_conversational_onboarding(
    message: Message,
    state: FSMContext,
    event_name: str = None,
    event_code: str = None
):
    """
    Start conversational onboarding flow.

    Called from start handler when user needs onboarding.
    """
    # Create fresh conversation state
    conv_state = conversation_service.create_onboarding_state(
        event_name=event_name,
        user_first_name=message.from_user.first_name
    )

    # Store event code if present
    if event_code:
        conv_state.context["pending_event"] = event_code

    # Start conversation - get initial greeting
    conv_state, greeting = await conversation_service.start_conversation(conv_state)

    # Save state to FSM
    await state.update_data(conversation=serialize_state(conv_state))
    await state.set_state(ConversationalOnboarding.in_conversation)

    # Send greeting
    await message.answer(greeting)


async def start_conversational_onboarding_from_callback(
    callback: CallbackQuery,
    state: FSMContext,
    event_name: str = None,
    event_code: str = None
):
    """
    Start conversational onboarding from a callback.

    Uses callback.from_user (the actual user) instead of callback.message.from_user (the bot).
    """
    logger.info(f"[TEXT ONBOARDING] Starting conversational onboarding from callback for user {callback.from_user.id}")

    # Create fresh conversation state with correct user info
    conv_state = conversation_service.create_onboarding_state(
        event_name=event_name,
        user_first_name=callback.from_user.first_name
    )

    # Store event code if present
    if event_code:
        conv_state.context["pending_event"] = event_code

    # Start conversation - get initial greeting
    conv_state, greeting = await conversation_service.start_conversation(conv_state)

    logger.info(f"[TEXT ONBOARDING] Generated greeting, conv_state messages: {len(conv_state.messages)}")

    # Save state to FSM - store both conversation and metadata
    await state.update_data(
        conversation=serialize_state(conv_state),
        event_name=event_name,
        pending_event=event_code
    )
    await state.set_state(ConversationalOnboarding.in_conversation)

    # Verify state was set
    current_state = await state.get_state()
    logger.info(f"[TEXT ONBOARDING] State set to: {current_state}")

    # Send greeting using bot directly since callback.message belongs to bot
    await bot.send_message(callback.from_user.id, greeting)


@router.message(ConversationalOnboarding.in_conversation, F.text)
async def process_conversation_message(message: Message, state: FSMContext):
    """Process user message in conversation"""
    logger.info(f"[TEXT ONBOARDING] ========================================")
    logger.info(f"[TEXT ONBOARDING] Received message from {message.from_user.id}: {message.text[:50]}...")

    # Check for reset/restart commands first
    text_lower = message.text.lower().strip()
    if text_lower in ["reset", "start over", "заново", "/start", "/reset"]:
        logger.info(f"[TEXT ONBOARDING] User requested reset")
        await state.clear()
        await message.answer(
            "Let's start fresh! Send /start to begin again.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    # Check current FSM state
    current_fsm_state = await state.get_state()
    logger.info(f"[TEXT ONBOARDING] Current FSM state: {current_fsm_state}")

    # Get current state
    data = await state.get_data()
    conv_data = data.get("conversation")
    logger.info(f"[TEXT ONBOARDING] State data keys: {list(data.keys())}")
    logger.info(f"[TEXT ONBOARDING] conv_data exists: {conv_data is not None}")

    if not conv_data:
        # State lost, restart with fresh conversation
        logger.warning(f"[TEXT ONBOARDING] State lost for user {message.from_user.id}, restarting")

        # Get event info from state if available
        event_name = data.get("event_name")
        pending_event = data.get("pending_event")

        conv_state = conversation_service.create_onboarding_state(
            event_name=event_name,
            user_first_name=message.from_user.first_name
        )
        if pending_event:
            conv_state.context["pending_event"] = pending_event

        # Start fresh conversation
        conv_state, greeting = await conversation_service.start_conversation(conv_state)
        await state.update_data(conversation=serialize_state(conv_state))
        await message.answer(greeting)
        return

    # Deserialize state
    conv_state = deserialize_state(conv_data)
    logger.info(f"[TEXT ONBOARDING] Conversation step: {conv_state.step}, messages: {len(conv_state.messages)}")

    try:
        # Process message
        conv_state, result = await conversation_service.process_message(
            conv_state,
            message.text
        )
        logger.info(f"[TEXT ONBOARDING] Got response, is_complete: {result.is_complete}")

        # Save updated state
        await state.update_data(conversation=serialize_state(conv_state))

        # Send response
        await message.answer(result.response_text)

        # If complete, finalize onboarding
        if result.is_complete and result.profile_data:
            await complete_conversational_onboarding(
                message,
                state,
                result.profile_data,
                conv_state.context.get("pending_event")
            )
    except Exception as e:
        logger.error(f"[TEXT ONBOARDING] Error processing message: {e}", exc_info=True)
        # Try to restart the conversation
        try:
            # CRITICAL: Clear ALL state first to prevent corruption
            # Old state with error condition must not persist
            await state.clear()
            logger.info(f"[TEXT ONBOARDING] Cleared corrupted FSM state for user {message.from_user.id}")

            await message.answer(
                "Sorry, something went wrong. Let me start over.\n\n"
                "What's your name and what do you do?"
            )

            # Create fresh state WITHOUT any pending context
            # This ensures clean recovery, not continued with old event context
            conv_state = conversation_service.create_onboarding_state(
                event_name=None,  # Fresh recovery - no pending event
                user_first_name=message.from_user.first_name
            )
            logger.debug(f"[TEXT ONBOARDING] Created fresh onboarding state after error")

            # Initialize fresh conversation to get proper greeting
            conv_state, greeting = await conversation_service.start_conversation(conv_state)
            logger.info(f"[TEXT ONBOARDING] Started fresh conversation after error recovery")

            # Save only clean state
            await state.update_data(conversation=serialize_state(conv_state))
            await state.set_state(ConversationalOnboarding.in_conversation)
            logger.info(f"[TEXT ONBOARDING] Recovery complete - fresh conversation ready")

        except Exception as e2:
            logger.error(f"[TEXT ONBOARDING] Failed to recover from error: {e2}", exc_info=True)
            # Also clear state on recovery failure to prevent cascading corruption
            await state.clear()
            logger.warning(f"[TEXT ONBOARDING] Cleared state due to recovery failure")
            await message.answer("Please type /start to restart.")


@router.message(ConversationalOnboarding.in_conversation, F.voice)
async def process_conversation_voice(message: Message, state: FSMContext):
    """Process voice message in conversation"""
    from adapters.telegram.loader import voice_service

    status_msg = await message.answer("🎤 Listening...")

    try:
        # Transcribe voice
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        text = await voice_service.download_and_transcribe(file_url)

        if text:
            await status_msg.delete()
            # Process as text
            message.text = text  # Hack to reuse text handler logic

            # Get state and process
            data = await state.get_data()
            conv_data = data.get("conversation")

            if conv_data:
                conv_state = deserialize_state(conv_data)
                conv_state, result = await conversation_service.process_message(
                    conv_state,
                    text
                )
                await state.update_data(conversation=serialize_state(conv_state))
                await message.answer(result.response_text)

                if result.is_complete and result.profile_data:
                    await complete_conversational_onboarding(
                        message,
                        state,
                        result.profile_data,
                        conv_state.context.get("pending_event")
                    )
        else:
            await status_msg.edit_text("Couldn't hear that clearly. Could you type it or try again?")

    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await status_msg.edit_text("Technical issue with voice. Please type your response.")


async def complete_conversational_onboarding(
    message: Message,
    state: FSMContext,
    profile_data: dict,
    pending_event: str = None
):
    """Complete onboarding with extracted profile data"""

    user_id = str(message.from_user.id)
    tg_username = message.from_user.username

    # Convert to OnboardingData
    onboarding_data = conversation_service.convert_to_onboarding_data(
        profile_data,
        pending_event_code=pending_event
    )

    # Update user with extracted data - save each field separately
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        user_id,
        display_name=profile_data.get("display_name") or message.from_user.first_name,
        interests=profile_data.get("interests", []),
        goals=profile_data.get("goals", []),
        bio=profile_data.get("about", ""),  # Only use "about" for bio
        looking_for=profile_data.get("looking_for", ""),
        can_help_with=profile_data.get("can_help_with", ""),
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

        # Generate vector embeddings in background (non-blocking)
        async def generate_embeddings_background(user_obj):
            try:
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
                else:
                    logger.warning(f"Embeddings returned None for user {user_obj.id}")
            except Exception as e:
                logger.error(f"Background embedding generation failed for user {user_obj.id}: {e}")

        # Fire and forget - don't block the flow
        import asyncio
        asyncio.create_task(generate_embeddings_background(user))

    # Detect language
    lang_code = message.from_user.language_code or "en"
    lang = "ru" if lang_code.startswith(("ru", "uk")) else "en"

    # Handle event join if pending
    event = None
    if pending_event:
        success, msg, event = await event_service.join_event(
            pending_event,
            MessagePlatform.TELEGRAM,
            user_id
        )

        if success and event:
            # Save current_event_id to user profile
            await user_service.update_user(
                MessagePlatform.TELEGRAM,
                user_id,
                current_event_id=event.id
            )

    # Save event info for after selfie
    await state.update_data(
        pending_event=pending_event,
        event_id=str(event.id) if event else None,
        event_name=event.name if event else None,
        language=lang
    )

    # Ask for selfie
    if lang == "ru":
        selfie_text = (
            "📸 <b>Последний шаг!</b>\n\n"
            "Отправь своё фото, чтобы твои матчи могли легко найти тебя на ивенте.\n\n"
            "<i>Это поможет быстрее узнать друг друга в толпе!</i>"
        )
    else:
        selfie_text = (
            "📸 <b>One last thing!</b>\n\n"
            "Send a photo of yourself so your matches can easily find you at the event.\n\n"
            "<i>This helps you recognize each other in the crowd!</i>"
        )

    await message.answer(selfie_text, reply_markup=get_selfie_keyboard_v2(lang))
    await state.set_state(ConversationalOnboarding.waiting_selfie)


async def show_top_matches_v2(message: Message, user, event, tg_username: str = None, lang: str = "en"):
    """Show top matches after onboarding (v2 version) and notify matched users"""
    from adapters.telegram.loader import matching_service
    from adapters.telegram.handlers.matches import notify_about_match
    from config.features import Features

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
            if lang == "ru":
                text = "👀 Пока мало участников для матчинга.\nКак только появятся — напишу тебе!"
            else:
                text = "👀 Not enough participants yet.\nI'll notify you when matches are found!"
            await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
            return

        # Notify matched users about new match
        new_user_name = user.display_name or user.first_name or "Someone"
        for matched_user, match_result in matches:
            if matched_user.platform_user_id:
                try:
                    # Use matched user's language preference if available
                    matched_lang = getattr(matched_user, 'language_preference', 'en')
                    await notify_about_match(
                        user_telegram_id=int(matched_user.platform_user_id),
                        partner_name=new_user_name,
                        explanation=match_result.explanation,
                        icebreaker=match_result.icebreaker,
                        match_id=str(match_result.match_id),
                        lang=matched_lang
                    )
                    logger.info(f"Notified user {matched_user.platform_user_id} about new match")
                except Exception as e:
                    logger.error(f"Failed to notify user {matched_user.platform_user_id}: {e}")

        # Format matches
        if lang == "ru":
            header = f"🎯 <b>Топ-{len(matches)} людей на {event.name}:</b>\n\n"
        else:
            header = f"🎯 <b>Top {len(matches)} people to meet at {event.name}:</b>\n\n"
        lines = []
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        for i, (matched_user, match_result) in enumerate(matches):
            emoji = emojis[i] if i < len(emojis) else f"{i+1}."
            name = matched_user.display_name or matched_user.first_name or "Unknown"
            role_line = matched_user.bio[:50] if matched_user.bio else ""
            why = match_result.explanation[:100] if match_result.explanation else ""
            contact = f"📱 @{matched_user.username}" if matched_user.username else ""

            line = f"{emoji} <b>{name}</b>"
            if role_line:
                line += f"\n   {role_line}"
            if why:
                line += f"\n   💡 {why}"
            if contact:
                line += f"\n   {contact}"
            lines.append(line)

        text = header + "\n\n".join(lines)

        # Add icebreaker
        if matches and matches[0][1].icebreaker:
            if lang == "ru":
                text += f"\n\n💬 <i>Начни с: {matches[0][1].icebreaker}</i>"
            else:
                text += f"\n\n💬 <i>Start with: {matches[0][1].icebreaker}</i>"

        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))

    except Exception as e:
        logger.error(f"Error showing top matches v2: {e}")
        if lang == "ru":
            text = "✓ Профиль сохранён! Напишу, когда найду матчи."
        else:
            text = "✓ Profile saved! I'll notify you about matches."
        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))


# === Selfie Handlers ===

@router.message(ConversationalOnboarding.waiting_selfie, F.photo)
async def handle_selfie_photo_v2(message: Message, state: FSMContext):
    """Handle selfie photo upload"""
    data = await state.get_data()
    lang = data.get("language", "en")
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
            text = "✅ Фото сохранено! Теперь тебя легко найти на ивенте."
        else:
            text = "✅ Photo saved! Now you're easy to spot at the event."

        await message.answer(text)
    except Exception as e:
        logger.error(f"Failed to save photo for user {user_id}: {e}")
        # Continue anyway - photo is optional

    await finish_onboarding_v2(message, state)


@router.callback_query(ConversationalOnboarding.waiting_selfie, F.data == "skip_selfie_v2")
async def skip_selfie_v2(callback: CallbackQuery, state: FSMContext):
    """Skip selfie upload"""
    # Answer callback immediately to prevent Telegram retry
    await callback.answer()

    data = await state.get_data()
    lang = data.get("language", "en")

    if lang == "ru":
        text = "👌 Хорошо, можешь добавить фото позже в профиле."
    else:
        text = "👌 No problem, you can add a photo later in your profile."

    try:
        await callback.message.edit_text(text)
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")

    await finish_onboarding_v2(callback.message, state, callback.from_user.id)


@router.message(ConversationalOnboarding.waiting_selfie, F.text)
async def handle_selfie_text_v2(message: Message, state: FSMContext):
    """Handle text when expecting selfie"""
    data = await state.get_data()
    lang = data.get("language", "en")

    text_lower = message.text.lower()
    if text_lower in ["skip", "пропустить", "нет", "no", "позже", "later"]:
        if lang == "ru":
            text = "👌 Хорошо, можешь добавить фото позже в профиле."
        else:
            text = "👌 No problem, you can add a photo later in your profile."
        await message.answer(text)
        await finish_onboarding_v2(message, state)
    else:
        if lang == "ru":
            text = "📸 Отправь фото или нажми 'Пропустить'"
        else:
            text = "📸 Send a photo or tap 'Skip'"
        await message.answer(text, reply_markup=get_selfie_keyboard_v2(lang))


async def finish_onboarding_v2(message: Message, state: FSMContext, user_tg_id: int = None):
    """Complete onboarding after selfie step - start personalization flow"""
    lang = "en"  # Default
    try:
        data = await state.get_data()
        lang = data.get("language", "en")
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
        logger.error(f"Error in finish_onboarding_v2: {e}")
        # Fallback: show matches directly if personalization fails
        try:
            data = await state.get_data()
            lang = data.get("language", "en")
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
                await show_top_matches_v2(message, user, event, user.username, lang)
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


# Note: Reset/Cancel is now handled inside process_conversation_message to ensure proper priority
