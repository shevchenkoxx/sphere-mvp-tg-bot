"""
Story onboarding handler — plays branded cinematic story with interactive moments.
"""

import asyncio
import random
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from adapters.telegram.states.onboarding import StoryOnboarding

logger = logging.getLogger(__name__)
router = Router(name="story_onboarding")

# Delay between auto-play steps (seconds)
STEP_DELAY = 2.5
SHORT_DELAY = 2.0
LONG_DELAY = 3.0


async def start_story(message: Message, state: FSMContext, mode: str,
                       context_id: str = "default", lang: str = "en",
                       community_name: str = None, member_count: int = None,
                       topics: list = None, event_name: str = None,
                       event_code: str = None, community_id: str = None):
    """Entry point: generate story and start playing it."""
    from adapters.telegram.loader import story_service

    # Preserve context for onboarding later
    fsm_data = {}
    if community_id:
        fsm_data["community_id"] = community_id
    if community_name:
        fsm_data["community_name"] = community_name
    if event_code:
        fsm_data["pending_event"] = event_code
    fsm_data["story_lang"] = lang
    fsm_data["story_mode"] = mode
    await state.update_data(**fsm_data)

    # Get story
    story = await story_service.get_story(
        mode=mode,
        context_id=context_id,
        lang=lang,
        community_name=community_name,
        member_count=member_count,
        topics=topics,
        event_name=event_name,
    )

    steps = story.get("steps", [])
    game_options = story.get("game_options", ["Option A", "Option B"])

    await state.update_data(story_steps=steps, story_game_options=game_options)
    await state.set_state(StoryOnboarding.playing)

    if mode == "event":
        await _play_event_story(message, state, steps)
    else:
        await _play_community_story(message, state, steps, game_options)


async def _play_community_story(message: Message, state: FSMContext,
                                 steps: list, game_options: list):
    """Play the 10-step community/global story."""
    chat_id = message.chat.id

    from adapters.telegram.loader import bot

    # Step 1: Hook
    await bot.send_message(chat_id, steps[0], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 2: Character 1
    await bot.send_message(chat_id, steps[1], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 3: Observation
    await bot.send_message(chat_id, steps[2], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 4: Game — INTERACTIVE #1
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=game_options[0], callback_data="story_game_0"),
            InlineKeyboardButton(text=game_options[1], callback_data="story_game_1"),
        ]
    ])
    await bot.send_message(chat_id, steps[3], reply_markup=kb, parse_mode="HTML")
    await state.set_state(StoryOnboarding.waiting_game_tap)
    # Flow continues in handle_game_tap callback


async def _continue_after_game(callback: CallbackQuery, state: FSMContext):
    """Continue community story after game interaction."""
    data = await state.get_data()
    steps = data.get("story_steps", [])
    chat_id = callback.message.chat.id

    from adapters.telegram.loader import bot

    # Step 5: Character 2
    await bot.send_message(chat_id, steps[5], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 6: AI Matching
    await bot.send_message(chat_id, steps[6], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 7: Match Preview — INTERACTIVE #2
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 See what happened next", callback_data="story_next")]
    ])
    await bot.send_message(chat_id, steps[7], reply_markup=kb, parse_mode="HTML")
    await state.set_state(StoryOnboarding.waiting_next_tap)
    # Flow continues in handle_next_tap callback


async def _continue_after_match(callback: CallbackQuery, state: FSMContext):
    """Continue community story after match preview interaction."""
    data = await state.get_data()
    steps = data.get("story_steps", [])
    chat_id = callback.message.chat.id
    lang = data.get("story_lang", "en")

    from adapters.telegram.loader import bot

    # Step 8: Resolution
    await bot.send_message(chat_id, steps[8], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 9: Bonus use cases
    await bot.send_message(chat_id, steps[9], parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Step 10: CTA
    cta_text = "🚀 Let's go" if lang == "en" else "🚀 Поехали"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cta_text, callback_data="story_start_onboarding")]
    ])
    await bot.send_message(chat_id, steps[10], reply_markup=kb, parse_mode="HTML")
    # Wait for CTA tap — handled by callback


async def _play_event_story(message: Message, state: FSMContext, steps: list):
    """Play the 7-step events story."""
    chat_id = message.chat.id
    data = await state.get_data()
    lang = data.get("story_lang", "en")

    from adapters.telegram.loader import bot

    # Step 1: Hook
    await bot.send_message(chat_id, steps[0], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 2: Create
    await bot.send_message(chat_id, steps[1], parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Step 3: Share & Fill
    await bot.send_message(chat_id, steps[2], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 4: Match Preview — INTERACTIVE
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⚡ See what happened" if lang == "en" else "⚡ Что произошло",
            callback_data="story_next"
        )]
    ])
    await bot.send_message(chat_id, steps[3], reply_markup=kb, parse_mode="HTML")
    await state.set_state(StoryOnboarding.waiting_next_tap)


async def _continue_event_after_match(callback: CallbackQuery, state: FSMContext):
    """Continue events story after match preview interaction."""
    data = await state.get_data()
    steps = data.get("story_steps", [])
    chat_id = callback.message.chat.id
    lang = data.get("story_lang", "en")

    from adapters.telegram.loader import bot

    # Step 5: Resolution
    await bot.send_message(chat_id, steps[4], parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Step 6: Bonus examples
    await bot.send_message(chat_id, steps[5], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 7a: Value message
    await bot.send_message(chat_id, steps[6], parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Step 7b: CTA
    cta_text_create = "🚀 Create an event" if lang == "en" else "🚀 Создать ивент"
    cta_text_join = "🎫 Join one" if lang == "en" else "🎫 Присоединиться"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=cta_text_create, callback_data="story_create_event"),
            InlineKeyboardButton(text=cta_text_join, callback_data="story_start_onboarding"),
        ]
    ])
    await bot.send_message(chat_id, steps[7], reply_markup=kb, parse_mode="HTML")


# ── Callback handlers ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("story_game_"), StoryOnboarding.waiting_game_tap)
async def handle_game_tap(callback: CallbackQuery, state: FSMContext):
    """Interactive #1: user tapped a game option."""
    await callback.answer()

    choice_idx = int(callback.data.split("_")[-1])
    data = await state.get_data()
    steps = data.get("story_steps", [])
    game_options = data.get("story_game_options", ["Option A", "Option B"])

    chosen = game_options[choice_idx] if choice_idx < len(game_options) else "that"
    pct = random.randint(58, 78)
    feedbacks = ["Nice", "Great choice", "Interesting", "Good pick"]
    feedback = random.choice(feedbacks)

    # Format step 4b with placeholders
    after_text = steps[4] if len(steps) > 4 else "Nice! Most people agree."
    after_text = after_text.replace("{feedback}", feedback)
    after_text = after_text.replace("{pct}", str(pct))
    after_text = after_text.replace("{choice}", chosen)

    # Remove the keyboard from the game message
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    from adapters.telegram.loader import bot
    await bot.send_message(callback.message.chat.id, after_text, parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Continue story
    await _continue_after_game(callback, state)


@router.callback_query(F.data == "story_next", StoryOnboarding.waiting_next_tap)
async def handle_next_tap(callback: CallbackQuery, state: FSMContext):
    """Interactive #2: user tapped 'see what happened next'."""
    await callback.answer()

    # Remove keyboard
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()
    mode = data.get("story_mode", "global")

    if mode == "event":
        await _continue_event_after_match(callback, state)
    else:
        await _continue_after_match(callback, state)


@router.callback_query(F.data == "story_start_onboarding")
async def handle_start_onboarding(callback: CallbackQuery, state: FSMContext):
    """CTA: user tapped 'Let's go' — transition to real onboarding."""
    await callback.answer()

    # Remove keyboard
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()
    event_code = data.get("pending_event")
    event_name = data.get("event_name")
    community_id = data.get("community_id")
    community_name = data.get("community_name")

    # Clear story-specific FSM data but keep context
    await state.update_data(story_steps=None, story_game_options=None, story_mode=None, story_lang=None)

    # Dispatch to the configured onboarding version
    from adapters.telegram.handlers.start import _start_onboarding_with_context
    await _start_onboarding_with_context(
        callback.message, state,
        event_name=event_name,
        event_code=event_code,
        community_id=community_id,
        community_name=community_name,
        skip_story=True,
    )


@router.callback_query(F.data == "story_create_event")
async def handle_create_event(callback: CallbackQuery, state: FSMContext):
    """Events CTA: user wants to create an event."""
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()

    # If user is not onboarded, onboard first
    from adapters.telegram.loader import user_service
    from core.domain.models import MessagePlatform
    user = await user_service.get_or_create_user(
        platform=MessagePlatform.TELEGRAM,
        platform_user_id=str(callback.from_user.id),
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )

    if not user.onboarding_completed:
        await state.update_data(post_onboarding_action="create_event")
        from adapters.telegram.handlers.start import _start_onboarding_with_context
        await _start_onboarding_with_context(callback.message, state, skip_story=True)
    else:
        # Go directly to event creation
        lang = data.get("story_lang", "en")
        await callback.message.answer(
            "Let's create your event! Send me the event name:" if lang == "en"
            else "Создаем ивент! Отправь мне название:",
        )
        from adapters.telegram.states.onboarding import EventStates
        await state.set_state(EventStates.waiting_name)
