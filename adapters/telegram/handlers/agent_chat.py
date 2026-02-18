"""
Agent Chat Handler — post-onboarding AI assistant.

Single LLM-driven conversation loop with tool use for
profile editing, navigation, and dynamic UI.

Entry: user taps "Chat with Sphere" in main menu.
Exit: user says "menu"/"back" or AI calls end_chat tool.
"""

import asyncio
import json
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from openai import AsyncOpenAI

from adapters.telegram.keyboards import get_main_menu_keyboard, build_ai_keyboard
from adapters.telegram.loader import (
    bot,
    embedding_service,
    user_service,
    voice_service,
)
from adapters.telegram.states.onboarding import AgentChatStates
from config.settings import settings
from core.domain.models import MessagePlatform
from core.prompts.agent_chat_prompts import (
    AGENT_CHAT_TOOLS,
    build_agent_chat_prompt,
)
from core.prompts.audio_onboarding import WHISPER_PROMPT_EN, WHISPER_PROMPT_RU
from core.utils.language import detect_lang
from infrastructure.ai.orchestrator_models import UIInstruction

logger = logging.getLogger(__name__)

router = Router(name="agent_chat")

AGENT_CHAT_MODEL = "gpt-4o-mini"
MAX_HISTORY = 30  # messages to keep

# Screen → callback_data mapping for navigation
SCREEN_MAP = {
    "profile": "my_profile",
    "matches": "my_matches",
    "events": "my_events",
    "sphere_city": "sphere_city",
    "vibe_check": "vibe_check",
    "menu": "back_to_menu",
}


# ------------------------------------------------------------------
# Entry point (called from start.py callback)
# ------------------------------------------------------------------

async def start_agent_chat(message_or_callback, state: FSMContext, lang: str = "en"):
    """Initialize agent chat session."""
    if isinstance(message_or_callback, CallbackQuery):
        user_id = str(message_or_callback.from_user.id)
        first_name = message_or_callback.from_user.first_name or ""
        send = message_or_callback.message.answer
    else:
        user_id = str(message_or_callback.from_user.id)
        first_name = message_or_callback.from_user.first_name or ""
        send = message_or_callback.answer

    # Load user profile
    user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)
    if not user or not user.onboarding_completed:
        await send("Please complete onboarding first! Tap /start")
        return

    profile_dict = user.model_dump() if hasattr(user, "model_dump") else {}

    # Init chat state
    await state.update_data(
        agent_chat_messages=[],
        agent_chat_profile=profile_dict,
        agent_chat_lang=lang,
    )
    await state.set_state(AgentChatStates.chatting)

    # Generate opening message
    greeting = (
        f"Hey {first_name}! I'm Sphere, your AI assistant. "
        "Ask me anything — I can update your profile, find matches, or just chat."
        if lang == "en" else
        f"Привет, {first_name}! Я Sphere, твой AI-помощник. "
        "Спрашивай что угодно — могу обновить профиль, найти матчи или просто поболтать."
    )
    kb = build_ai_keyboard(
        options=[
            "Show my profile" if lang == "en" else "Покажи профиль",
            "Find matches" if lang == "en" else "Найди матчи",
            "Improve my profile" if lang == "en" else "Улучши профиль",
        ],
        ui_type="inline_choice",
        callback_prefix="ai_chat",
    )
    await send(greeting, reply_markup=kb)
    await state.update_data(ai_chat_options=[
        "Show my profile" if lang == "en" else "Покажи профиль",
        "Find matches" if lang == "en" else "Найди матчи",
        "Improve my profile" if lang == "en" else "Улучши профиль",
    ])


# ------------------------------------------------------------------
# Core LLM turn
# ------------------------------------------------------------------

async def _process_chat_turn(
    user_message: str,
    state: FSMContext,
    message_type: str = "text",
) -> dict:
    """Process one turn with the agent chat LLM. Returns action dict."""
    data = await state.get_data()
    messages = data.get("agent_chat_messages", [])
    profile_dict = data.get("agent_chat_profile", {})
    lang = data.get("agent_chat_lang", "en")

    # Append user message
    if message_type == "voice":
        user_message = f"[Voice transcription] {user_message}"
    messages.append({"role": "user", "content": user_message})

    # Trim
    if len(messages) > MAX_HISTORY:
        messages = messages[-MAX_HISTORY:]

    system_prompt = build_agent_chat_prompt(profile_dict, lang)
    api_messages = [{"role": "system", "content": system_prompt}] + messages

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=25.0)

    try:
        response = await client.chat.completions.create(
            model=AGENT_CHAT_MODEL,
            messages=api_messages,
            tools=AGENT_CHAT_TOOLS,
            tool_choice="auto",
            max_tokens=400,
            temperature=0.7,
        )

        choice = response.choices[0]
        assistant_msg = choice.message
        reply_text = assistant_msg.content or ""

        # Result dict
        result = {
            "text": reply_text,
            "ui": None,
            "navigate_to": None,
            "edit_field": None,
            "end_chat": False,
        }

        if assistant_msg.tool_calls:
            for tc in assistant_msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if tc.function.name == "interact_with_user":
                    result["text"] = args.get("message_text", reply_text)
                    ui_type = args.get("ui_type", "none")
                    options = args.get("options", [])
                    if ui_type != "none" and options:
                        result["ui"] = UIInstruction(ui_type=ui_type, options=options[:6])

                elif tc.function.name == "navigate_to":
                    result["navigate_to"] = args.get("screen", "menu")

                elif tc.function.name == "edit_profile_field":
                    result["edit_field"] = {
                        "field": args.get("field_name"),
                        "value": args.get("value"),
                    }

                elif tc.function.name == "end_chat":
                    result["end_chat"] = True

        # Store assistant reply
        messages.append({"role": "assistant", "content": result["text"]})
        await state.update_data(agent_chat_messages=messages)

        return result

    except Exception as e:
        logger.error(f"Agent chat LLM error: {e}", exc_info=True)
        messages.append({"role": "assistant", "content": "..."})
        await state.update_data(agent_chat_messages=messages)
        return {
            "text": "Something went wrong. Try again or tap /menu to go back."
                    if lang == "en" else
                    "Что-то пошло не так. Попробуй ещё или нажми /menu.",
            "ui": None, "navigate_to": None, "edit_field": None, "end_chat": False,
        }


async def _send_result(message: Message, state: FSMContext, result: dict, from_user=None):
    """Send the LLM result to the user — handle UI, navigation, edits."""
    data = await state.get_data()
    lang = data.get("agent_chat_lang", "en")
    user_id = str(from_user.id) if from_user else str(message.chat.id)

    # Handle profile edit
    if result.get("edit_field"):
        field_info = result["edit_field"]
        field_name = field_info.get("field")
        value = field_info.get("value")
        if field_name and value is not None:
            try:
                await user_service.update_user(
                    MessagePlatform.TELEGRAM, user_id, **{field_name: value}
                )
                # Update cached profile
                profile_dict = data.get("agent_chat_profile", {})
                profile_dict[field_name] = value
                await state.update_data(agent_chat_profile=profile_dict)

                # Background: regenerate embeddings
                user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)
                if user:
                    asyncio.create_task(_regen_embeddings(user))
            except Exception as e:
                logger.error(f"Agent chat edit failed: {e}")

    # Handle navigation
    if result.get("navigate_to"):
        screen = result["navigate_to"]
        callback_data = SCREEN_MAP.get(screen, "back_to_menu")
        # Clear state and let the user navigate via menu
        await state.clear()
        text = result.get("text") or ("Opening..." if lang == "en" else "Открываю...")
        # Send text + hint to tap the button
        from adapters.telegram.keyboards.inline import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        label_map = {
            "profile": "👤 Profile" if lang == "en" else "👤 Профиль",
            "matches": "💫 Matches" if lang == "en" else "💫 Матчи",
            "events": "🎉 Events" if lang == "en" else "🎉 Ивенты",
            "sphere_city": "🏙️ Sphere City",
            "vibe_check": "🔮 Vibe Check",
            "menu": "← Menu" if lang == "en" else "← Меню",
        }
        kb.button(text=label_map.get(screen, "← Menu"), callback_data=callback_data)
        await message.answer(text, reply_markup=kb.as_markup())
        return

    # Handle end_chat
    if result.get("end_chat"):
        await state.clear()
        text = result.get("text") or ("Back to menu!" if lang == "en" else "Возвращаю в меню!")
        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
        return

    # Handle regular response with optional UI
    keyboard = None
    if result.get("ui") and result["ui"].options:
        keyboard = build_ai_keyboard(
            options=result["ui"].options,
            ui_type=result["ui"].ui_type,
            callback_prefix="ai_chat",
        )
        await state.update_data(ai_chat_options=result["ui"].options)

    text = result.get("text", "")
    if text:
        await message.answer(text, reply_markup=keyboard)
    elif keyboard:
        await message.answer("Choose:" if lang == "en" else "Выбирай:", reply_markup=keyboard)


async def _regen_embeddings(user):
    """Background task to regenerate embeddings after profile edit."""
    try:
        result = await embedding_service.generate_embeddings(user)
        if result:
            from infrastructure.database.user_repository import SupabaseUserRepository
            repo = SupabaseUserRepository()
            await repo.update_embeddings(user.id, *result)
    except Exception as e:
        logger.debug(f"Embedding regen failed: {e}")


# ------------------------------------------------------------------
# Message handlers
# ------------------------------------------------------------------

@router.message(AgentChatStates.chatting, F.text)
async def handle_text(message: Message, state: FSMContext):
    """Text input during agent chat."""
    if message.text and message.text.startswith("/"):
        # Handle commands — exit chat
        await state.clear()
        cmd = message.text.split()[0].lower()
        if cmd in ("/menu", "/start"):
            from adapters.telegram.handlers.start import menu_command
            await menu_command(message)
        else:
            await message.answer("Chat ended. Send the command again.")
        return

    result = await _process_chat_turn(message.text, state)
    await _send_result(message, state, result, from_user=message.from_user)


@router.message(AgentChatStates.chatting, F.voice)
async def handle_voice(message: Message, state: FSMContext):
    """Voice input — transcribe then process."""
    data = await state.get_data()
    lang = data.get("agent_chat_lang", "en")

    status = await message.answer("🎤 ..." if lang == "en" else "🎤 ...")
    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        prompt = WHISPER_PROMPT_RU if lang == "ru" else WHISPER_PROMPT_EN
        transcription = await voice_service.download_and_transcribe(
            file_url, language=lang, prompt=prompt
        )
        try:
            await status.delete()
        except Exception:
            pass

        if not transcription or len(transcription) < 5:
            await message.answer(
                "Couldn't hear that. Try again or type." if lang == "en"
                else "Не расслышал. Попробуй ещё или напиши."
            )
            return

        result = await _process_chat_turn(transcription, state, message_type="voice")
        await _send_result(message, state, result, from_user=message.from_user)

    except Exception as e:
        logger.error(f"Agent chat voice error: {e}")
        try:
            await status.edit_text("Error. Try again." if lang == "en" else "Ошибка. Попробуй ещё.")
        except Exception:
            pass


@router.message(AgentChatStates.chatting)
async def handle_other(message: Message, state: FSMContext):
    """Any other content type — photo, sticker, etc."""
    data = await state.get_data()
    lang = data.get("agent_chat_lang", "en")

    if message.photo:
        # Save photo
        try:
            user_id = str(message.from_user.id)
            photo = message.photo[-1]
            await user_service.update_user(
                MessagePlatform.TELEGRAM, user_id, photo_url=photo.file_id
            )
            await message.answer(
                "📸 Photo updated!" if lang == "en" else "📸 Фото обновлено!"
            )
        except Exception as e:
            logger.error(f"Agent chat photo save failed: {e}")
    elif message.sticker:
        await message.answer("😄")
    else:
        await message.answer(
            "I can handle text and voice. Try typing!" if lang == "en"
            else "Я понимаю текст и голос. Попробуй написать!"
        )


# ------------------------------------------------------------------
# AI-generated button callbacks
# ------------------------------------------------------------------

@router.callback_query(AgentChatStates.chatting, F.data.startswith("ai_chat:"))
async def handle_ai_chat_choice(callback: CallbackQuery, state: FSMContext):
    """Handle button press from AI-generated keyboard."""
    await callback.answer()

    data = await state.get_data()
    options = data.get("ai_chat_options", [])

    try:
        idx = int(callback.data.split(":")[1])
        chosen = options[idx] if idx < len(options) else callback.data
    except (ValueError, IndexError):
        chosen = callback.data

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    result = await _process_chat_turn(f"User selected: {chosen}", state)
    await _send_result(callback.message, state, result, from_user=callback.from_user)
