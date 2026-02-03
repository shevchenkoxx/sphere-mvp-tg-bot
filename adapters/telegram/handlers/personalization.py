"""
Post-onboarding personalization handler.

Collects additional context through:
1. Sharp question: "Чем ты горишь в жизни прямо сейчас?"
2. Intent buttons: "Что для тебя будет win сегодня?"
3. LLM-generated adaptive buttons based on answers
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from openai import AsyncOpenAI

from adapters.telegram.states.onboarding import PersonalizationStates
from adapters.telegram.keyboards.inline import (
    get_intent_keyboard,
    get_adaptive_buttons_keyboard,
    get_main_menu_keyboard,
)
from adapters.telegram.loader import (
    user_service, voice_service, matching_service
)
from core.domain.models import MessagePlatform, UserUpdate
from config.settings import settings

router = Router()
logger = logging.getLogger(__name__)


# === PROMPTS ===

ADAPTIVE_BUTTONS_PROMPT = """Based on the user's response about what they're passionate about and their intent for today, generate exactly 3 button options that will help match them with the right people.

USER'S PASSION (what they're excited about right now):
{passion_text}

USER'S INTENT FOR TODAY:
{intent}

RULES FOR GENERATING BUTTONS:
1. Each button should MAXIMALLY DIFFERENTIATE this user from others
2. Each button represents a DISTINCT matching vector (different types of people they might connect with)
3. Buttons should be mutually exclusive - picking one gives clear signal about what they want
4. Use the user's language ({language})
5. Each button text should be 5-10 words, starting with an emoji
6. Frame buttons as "what kind of connection they're looking for"

BAD EXAMPLES (don't do this - everyone would pick all):
🔹 Люблю интересные разговоры
🔹 Хочу познакомиться с умными людьми
🔹 Ищу вдохновение

GOOD EXAMPLES (differentiate clearly):
🔹 Ищу ментора/советника с опытом в {relevant_field}
🔹 Хочу найти единомышленников из {relevant_industry}
🔹 Просто хочу отвлечься и поболтать о другом

Generate 3 buttons in JSON format:
{{"buttons": ["button1_text", "button2_text", "button3_text"], "header": "short_header_text"}}

The header should be a short phrase like "Ещё пару деталей:" in {language}.
Respond with JSON only, no other text."""


# === ENTRY POINT ===

async def start_personalization(message: Message, state: FSMContext, lang: str = "ru"):
    """Start the personalization flow after onboarding."""
    # Save language and context
    data = await state.get_data()
    await state.update_data(language=lang)

    # Step 1: Ask the sharp question
    if lang == "ru":
        text = (
            "🔥 <b>Последний штрих!</b>\n\n"
            "Опиши одним-двумя предложениями:\n"
            "<b>Чем ты горишь в жизни прямо сейчас?</b>\n\n"
            "Текстом или голосовым 🎤"
        )
    else:
        text = (
            "🔥 <b>One last thing!</b>\n\n"
            "In one or two sentences:\n"
            "<b>What are you most excited about in life right now?</b>\n\n"
            "Text or voice 🎤"
        )

    await state.set_state(PersonalizationStates.waiting_passion)
    await message.answer(text)


# === STEP 1: PASSION RESPONSE ===

@router.message(PersonalizationStates.waiting_passion)
async def process_passion_response(message: Message, state: FSMContext):
    """Process the user's passion response (text or voice)."""
    data = await state.get_data()
    lang = data.get("language", "ru")

    passion_text = ""

    # Handle voice message
    if message.voice:
        try:
            # Download and transcribe voice
            file = await message.bot.get_file(message.voice.file_id)
            file_bytes = await message.bot.download_file(file.file_path)
            audio_data = file_bytes.read()

            passion_text = await voice_service.transcribe(audio_data)
            logger.info(f"Transcribed passion: {passion_text[:100]}...")
        except Exception as e:
            logger.error(f"Voice transcription failed: {e}")
            error_text = "Не удалось распознать голос. Попробуй текстом?" if lang == "ru" else "Couldn't transcribe voice. Try text?"
            await message.answer(error_text)
            return
    else:
        passion_text = message.text or ""

    if not passion_text.strip():
        hint = "Напиши или запиши голосовое 🎤" if lang == "ru" else "Send text or voice 🎤"
        await message.answer(hint)
        return

    # Save passion text
    await state.update_data(passion_text=passion_text)

    # Move to Step 2: Intent buttons
    if lang == "ru":
        text = (
            "👍 Отлично!\n\n"
            "<b>Что для тебя будет win сегодня?</b>"
        )
    else:
        text = (
            "👍 Great!\n\n"
            "<b>What would be a win for you today?</b>"
        )

    await state.set_state(PersonalizationStates.choosing_intent)
    await message.answer(text, reply_markup=get_intent_keyboard(lang))


# === STEP 2: INTENT SELECTION ===

@router.callback_query(PersonalizationStates.choosing_intent, F.data.startswith("intent_"))
async def process_intent_selection(callback: CallbackQuery, state: FSMContext):
    """Process the user's intent selection."""
    data = await state.get_data()
    lang = data.get("language", "ru")
    passion_text = data.get("passion_text", "")

    # Parse intent
    intent_key = callback.data.replace("intent_", "")

    # Map intent to readable text
    intent_map = {
        "conversation": "Найти интересного собеседника" if lang == "ru" else "Find interesting conversation",
        "relationship": "Познакомиться для отношений" if lang == "ru" else "Meet someone for relationship",
        "business": "Найти партнёра/коллегу" if lang == "ru" else "Find business partner/colleague",
    }

    intent_text = intent_map.get(intent_key, intent_key)
    await state.update_data(intent=intent_text, intent_key=intent_key)

    await callback.answer()

    # Show loading while generating adaptive buttons
    loading_text = "🤔 Подбираю вопросы под тебя..." if lang == "ru" else "🤔 Generating personalized questions..."
    await callback.message.edit_text(loading_text)

    # Generate adaptive buttons with LLM
    try:
        buttons_data = await generate_adaptive_buttons(passion_text, intent_text, lang)

        header = buttons_data.get("header", "Ещё пару деталей:" if lang == "ru" else "A few more details:")
        buttons = buttons_data.get("buttons", [])

        if not buttons or len(buttons) < 3:
            # Fallback buttons
            buttons = get_fallback_buttons(intent_key, lang)
            header = "Что тебе ближе?" if lang == "ru" else "What resonates with you?"

        await state.update_data(adaptive_buttons=buttons)
        await state.set_state(PersonalizationStates.choosing_adaptive)

        await callback.message.edit_text(
            f"<b>{header}</b>",
            reply_markup=get_adaptive_buttons_keyboard(buttons, lang)
        )

    except Exception as e:
        logger.error(f"Failed to generate adaptive buttons: {e}")
        # Use fallback and continue
        buttons = get_fallback_buttons(intent_key, lang)
        await state.update_data(adaptive_buttons=buttons)
        await state.set_state(PersonalizationStates.choosing_adaptive)

        header = "Что тебе ближе?" if lang == "ru" else "What resonates with you?"
        await callback.message.edit_text(
            f"<b>{header}</b>",
            reply_markup=get_adaptive_buttons_keyboard(buttons, lang)
        )


# === STEP 3: ADAPTIVE BUTTON SELECTION ===

@router.callback_query(PersonalizationStates.choosing_adaptive, F.data.startswith("adaptive_"))
async def process_adaptive_selection(callback: CallbackQuery, state: FSMContext):
    """Process the adaptive button selection and complete personalization."""
    data = await state.get_data()
    lang = data.get("language", "ru")
    passion_text = data.get("passion_text", "")
    intent_text = data.get("intent", "")
    intent_key = data.get("intent_key", "")
    buttons = data.get("adaptive_buttons", [])

    # Parse selection
    try:
        button_index = int(callback.data.replace("adaptive_", ""))
        selected_button = buttons[button_index] if button_index < len(buttons) else ""
    except (ValueError, IndexError):
        selected_button = ""

    await callback.answer()

    # Save personalization data to user profile
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if user:
        # Build personalization context for matching
        personalization_context = f"""
Passion: {passion_text}
Intent: {intent_text}
Preference: {selected_button}
""".strip()

        # Update user's looking_for with enriched context
        current_looking_for = user.looking_for or ""
        enhanced_looking_for = f"{current_looking_for}\n\n[Personalization]\n{personalization_context}".strip()

        try:
            await user_service.update_user(
                MessagePlatform.TELEGRAM,
                str(callback.from_user.id),
                looking_for=enhanced_looking_for
            )
            logger.info(f"Saved personalization for user {callback.from_user.id}")
        except Exception as e:
            logger.error(f"Failed to save personalization: {e}")

    # Show completion message
    event_id = data.get("event_id")
    event_name = data.get("event_name")

    if event_id:
        if lang == "ru":
            text = (
                "✅ <b>Готово!</b>\n\n"
                f"🔍 Анализирую участников <b>{event_name}</b>...\n"
                "Пришлю лучшие матчи через пару секунд!"
            )
        else:
            text = (
                "✅ <b>Done!</b>\n\n"
                f"🔍 Analyzing participants of <b>{event_name}</b>...\n"
                "Sending best matches in a moment!"
            )
    else:
        if lang == "ru":
            text = (
                "✅ <b>Готово!</b>\n\n"
                "🔍 Ищу интересных людей для тебя...\n"
                "Пришлю матчи, как только найду!"
            )
        else:
            text = (
                "✅ <b>Done!</b>\n\n"
                "🔍 Finding interesting people for you...\n"
                "Will send matches as soon as I find them!"
            )

    await callback.message.edit_text(text)

    # Now proceed to show matches
    await show_matches_after_personalization(callback.message, state, callback.from_user.id)


# === HELPER FUNCTIONS ===

async def generate_adaptive_buttons(passion_text: str, intent: str, lang: str) -> dict:
    """Generate adaptive buttons using LLM."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    prompt = ADAPTIVE_BUTTONS_PROMPT.format(
        passion_text=passion_text,
        intent=intent,
        language="Russian" if lang == "ru" else "English"
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.7
    )

    import json
    import re

    text = response.choices[0].message.content.strip()
    # Remove markdown code blocks if present
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    return json.loads(text)


def get_fallback_buttons(intent_key: str, lang: str) -> list:
    """Get fallback buttons if LLM generation fails."""
    if lang == "ru":
        if intent_key == "conversation":
            return [
                "🧠 Ищу глубокие разговоры о смыслах",
                "⚡ Хочу энергичного общения и новых идей",
                "😌 Просто хочу расслабиться и поболтать"
            ]
        elif intent_key == "relationship":
            return [
                "💫 Ищу человека со схожими ценностями",
                "🎯 Важна амбициозность и цели",
                "🌿 Ценю спокойствие и гармонию"
            ]
        else:  # business
            return [
                "🚀 Ищу ко-фаундера или партнёра",
                "🎓 Хочу найти ментора с опытом",
                "🤝 Интересен нетворкинг в моей сфере"
            ]
    else:
        if intent_key == "conversation":
            return [
                "🧠 Looking for deep, meaningful talks",
                "⚡ Want energetic exchange of ideas",
                "😌 Just want to relax and chat"
            ]
        elif intent_key == "relationship":
            return [
                "💫 Looking for shared values",
                "🎯 Ambition and goals matter",
                "🌿 Value calmness and harmony"
            ]
        else:  # business
            return [
                "🚀 Looking for co-founder or partner",
                "🎓 Want to find an experienced mentor",
                "🤝 Interested in industry networking"
            ]


async def show_matches_after_personalization(message: Message, state: FSMContext, user_tg_id: int):
    """Show matches after personalization is complete."""
    from adapters.telegram.handlers.onboarding_audio import show_top_matches
    from uuid import UUID

    data = await state.get_data()
    lang = data.get("language", "ru")
    event_id = data.get("event_id")
    event_name = data.get("event_name")

    try:
        user = await user_service.get_user_by_platform(
            MessagePlatform.TELEGRAM,
            str(user_tg_id)
        )

        if event_id and user:
            # Create event wrapper for show_top_matches
            class EventWrapper:
                def __init__(self, id, name):
                    self.id = UUID(id)
                    self.name = name

            event = EventWrapper(event_id, event_name)
            await show_top_matches(message, user, event, lang, user.username)
        else:
            # No event - show main menu
            await message.answer(
                "👇 Используй меню для навигации" if lang == "ru" else "👇 Use the menu to navigate",
                reply_markup=get_main_menu_keyboard(lang)
            )
    except Exception as e:
        logger.error(f"Error showing matches after personalization: {e}")
        await message.answer(
            "✓ Готово! Проверяй матчи в меню." if lang == "ru" else "✓ Done! Check matches in menu.",
            reply_markup=get_main_menu_keyboard(lang)
        )
    finally:
        await state.clear()
