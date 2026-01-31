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
from adapters.telegram.loader import user_service, event_service, bot
from adapters.telegram.keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router()


# === FSM States ===

class ConversationalOnboarding(StatesGroup):
    """States for conversational onboarding"""
    in_conversation = State()  # Active conversation with LLM


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

    # Save state to FSM
    await state.update_data(conversation=serialize_state(conv_state))
    await state.set_state(ConversationalOnboarding.in_conversation)

    # Send greeting using bot directly since callback.message belongs to bot
    await bot.send_message(callback.from_user.id, greeting)


@router.message(ConversationalOnboarding.in_conversation, F.text)
async def process_conversation_message(message: Message, state: FSMContext):
    """Process user message in conversation"""
    logger.info(f"[TEXT ONBOARDING] Received message from {message.from_user.id}: {message.text[:50]}...")

    # Get current state
    data = await state.get_data()
    conv_data = data.get("conversation")
    logger.info(f"[TEXT ONBOARDING] State data keys: {list(data.keys())}")

    if not conv_data:
        # State lost, restart
        logger.warning(f"[TEXT ONBOARDING] State lost for user {message.from_user.id}, restarting")
        await message.answer("Let's start over. What's your name?")
        conv_state = conversation_service.create_onboarding_state(
            user_first_name=message.from_user.first_name
        )
        await state.update_data(conversation=serialize_state(conv_state))
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
        await message.answer("Sorry, something went wrong. Please try again or type /start to restart.")


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

    # Update user with extracted data
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        user_id,
        display_name=profile_data.get("display_name") or message.from_user.first_name,
        interests=profile_data.get("interests", []),
        goals=profile_data.get("goals", []),
        bio=conversation_service._build_bio_from_extracted(profile_data),
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

    # Handle event join if pending
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

            # Re-fetch user with updated current_event_id
            user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)

            await message.answer(
                f"🎉 You're in! Welcome to <b>{event.name}</b>\n\n"
                "Finding interesting people for you..."
            )

            # Show top matches
            if user:
                await show_top_matches_v2(message, user, event, tg_username)
        else:
            text = (
                "✓ Profile saved!\n\n"
                "The event is no longer available, but you can join other events."
            )
            await message.answer(text, reply_markup=get_main_menu_keyboard())
    else:
        text = (
            "🎉 <b>Profile complete!</b>\n\n"
            "Scan QR codes at events to start meeting interesting people!"
        )
        await message.answer(text, reply_markup=get_main_menu_keyboard())

    await state.clear()


async def show_top_matches_v2(message: Message, user, event, tg_username: str = None):
    """Show top matches after onboarding (v2 version) and notify matched users"""
    from adapters.telegram.loader import matching_service
    from adapters.telegram.handlers.matches import notify_about_match
    from config.features import Features

    try:
        matches = await matching_service.find_and_create_matches_for_user(
            user=user,
            event_id=event.id,
            limit=Features.SHOW_TOP_MATCHES
        )

        if not matches:
            await message.answer(
                "👀 Not enough participants yet.\n"
                "I'll notify you when matches are found!",
                reply_markup=get_main_menu_keyboard()
            )
            return

        # Notify matched users about new match
        new_user_name = user.display_name or user.first_name or "Someone"
        for matched_user, match_result in matches:
            if matched_user.platform_user_id:
                try:
                    await notify_about_match(
                        user_telegram_id=int(matched_user.platform_user_id),
                        partner_name=new_user_name,
                        explanation=match_result.explanation,
                        icebreaker=match_result.icebreaker,
                        match_id=str(match_result.match_id),
                        lang="en"  # Default to English for v2
                    )
                    logger.info(f"Notified user {matched_user.platform_user_id} about new match")
                except Exception as e:
                    logger.error(f"Failed to notify user {matched_user.platform_user_id}: {e}")

        # Format matches
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
            text += f"\n\n💬 <i>Start with: {matches[0][1].icebreaker}</i>"

        await message.answer(text, reply_markup=get_main_menu_keyboard())

    except Exception as e:
        logger.error(f"Error showing top matches v2: {e}")
        await message.answer(
            "✓ Profile saved! I'll notify you about matches.",
            reply_markup=get_main_menu_keyboard()
        )


# === Reset/Cancel ===

@router.message(ConversationalOnboarding.in_conversation, F.text.lower().in_(["reset", "start over", "заново", "/start"]))
async def reset_conversation(message: Message, state: FSMContext):
    """Reset conversation if user is stuck"""
    await state.clear()
    await message.answer(
        "Let's start fresh! Send /start to begin again.",
        reply_markup=get_main_menu_keyboard()
    )
