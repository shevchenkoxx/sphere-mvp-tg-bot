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


@router.message(ConversationalOnboarding.in_conversation, F.text)
async def process_conversation_message(message: Message, state: FSMContext):
    """Process user message in conversation"""

    # Get current state
    data = await state.get_data()
    conv_data = data.get("conversation")

    if not conv_data:
        # State lost, restart
        await message.answer("Let's start over. What's your name?")
        conv_state = conversation_service.create_onboarding_state(
            user_first_name=message.from_user.first_name
        )
        await state.update_data(conversation=serialize_state(conv_state))
        return

    # Deserialize state
    conv_state = deserialize_state(conv_data)

    # Process message
    conv_state, result = await conversation_service.process_message(
        conv_state,
        message.text
    )

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
            text = (
                f"🎉 You're in! Welcome to <b>{event.name}</b>\n\n"
                "I'm already finding interesting people for you. I'll message you when I find matches!"
            )
        else:
            text = (
                "✓ Profile saved!\n\n"
                "The event is no longer available, but you can join other events."
            )
    else:
        text = (
            "🎉 <b>Profile complete!</b>\n\n"
            "Scan QR codes at events to start meeting interesting people!"
        )

    await message.answer(text, reply_markup=get_main_menu_keyboard())
    await state.clear()


# === Reset/Cancel ===

@router.message(ConversationalOnboarding.in_conversation, F.text.lower().in_(["reset", "start over", "заново", "/start"]))
async def reset_conversation(message: Message, state: FSMContext):
    """Reset conversation if user is stuck"""
    await state.clear()
    await message.answer(
        "Let's start fresh! Send /start to begin again.",
        reply_markup=get_main_menu_keyboard()
    )
