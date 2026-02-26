"""
Story onboarding handler — intent-first flow with message deletion.

Flow: Intent question → Hook → How it works → Game → Match preview → CTA → Onboarding
Each message deletes the previous for a clean chat experience.
"""

import asyncio
import random
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from adapters.telegram.states.onboarding import StoryOnboarding
from core.services.story_service import (
    INTENT_QUESTION, get_story, classify_intent, GAME_OPTIONS,
)

logger = logging.getLogger(__name__)
router = Router(name="story_onboarding")

# Delays (seconds)
STEP_DELAY = 2.5
SHORT_DELAY = 1.8


# ── Helpers ────────────────────────────────────────────────────────────────

async def _delete_msg(chat_id: int, msg_id: int):
    """Safely delete a message."""
    try:
        from adapters.telegram.loader import bot
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


async def _send_and_track(chat_id: int, text: str, state: FSMContext,
                           reply_markup=None, delete_previous=True) -> int:
    """Send a message, optionally delete the previous one, track msg_id in FSM."""
    from adapters.telegram.loader import bot

    if delete_previous:
        data = await state.get_data()
        prev_id = data.get("story_last_msg_id")
        if prev_id:
            await _delete_msg(chat_id, prev_id)

    sent = await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
    await state.update_data(story_last_msg_id=sent.message_id)
    return sent.message_id


# ── Entry point ────────────────────────────────────────────────────────────

INTENT_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🤝 Find friends", callback_data="story_intent_friends"),
        InlineKeyboardButton(text="💕 Meet someone", callback_data="story_intent_dating"),
    ],
    [
        InlineKeyboardButton(text="⚡ Activity partners", callback_data="story_intent_activities"),
        InlineKeyboardButton(text="💼 Networking", callback_data="story_intent_networking"),
    ],
    [
        InlineKeyboardButton(text="🌟 Open to anything", callback_data="story_intent_open"),
        InlineKeyboardButton(text="✍️ Something specific", callback_data="story_intent_custom"),
    ],
])


async def start_story(message: Message, state: FSMContext, mode: str = "global",
                       context_id: str = "default", lang: str = "en",
                       community_name: str = None, member_count: int = None,
                       topics: list = None, event_name: str = None,
                       event_code: str = None, community_id: str = None):
    """Entry point: show intent selection."""
    # Preserve context for onboarding later
    fsm_data = {"story_lang": lang, "story_mode": mode}
    if community_id:
        fsm_data["community_id"] = community_id
    if community_name:
        fsm_data["community_name"] = community_name
    if event_code:
        fsm_data["pending_event"] = event_code
    if event_name:
        fsm_data["event_name"] = event_name
    await state.update_data(**fsm_data)

    # Send intent question
    from adapters.telegram.loader import bot
    sent = await bot.send_message(
        message.chat.id, INTENT_QUESTION,
        reply_markup=INTENT_KEYBOARD, parse_mode="HTML",
    )
    await state.update_data(story_last_msg_id=sent.message_id)
    await state.set_state(StoryOnboarding.waiting_intent)


# ── Intent handlers ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("story_intent_"), StoryOnboarding.waiting_intent)
async def handle_intent_tap(callback: CallbackQuery, state: FSMContext):
    """User picked an intent (or 'custom')."""
    await callback.answer()
    intent = callback.data.replace("story_intent_", "")

    if intent == "custom":
        # Ask user to type
        await _send_and_track(
            callback.message.chat.id,
            "What are you looking for? Just type it 👇",
            state, delete_previous=True,
        )
        await state.set_state(StoryOnboarding.waiting_custom_intent)
        return

    # Got a concrete intent — start the story
    await state.update_data(story_intent=intent)
    await _play_story(callback.message.chat.id, state, intent)


@router.message(StoryOnboarding.waiting_custom_intent)
async def handle_custom_intent_text(message: Message, state: FSMContext):
    """User typed their specific intent."""
    intent = classify_intent(message.text or "")
    await state.update_data(story_intent=intent)

    # Delete user's message for clean chat
    await _delete_msg(message.chat.id, message.message_id)

    await _play_story(message.chat.id, state, intent)


# ── Story playback ─────────────────────────────────────────────────────────

async def _play_story(chat_id: int, state: FSMContext, intent: str):
    """Play the 5-step story for the given intent."""
    story = get_story(intent)
    await state.update_data(story_data=story)
    await state.set_state(StoryOnboarding.playing)

    # Step 1: Hook
    await _send_and_track(chat_id, story["hook"], state, delete_previous=True)
    await asyncio.sleep(STEP_DELAY)

    # Step 2: How it works
    await _send_and_track(chat_id, story["how_it_works"], state, delete_previous=True)
    await asyncio.sleep(STEP_DELAY)

    # Step 3: Game — interactive
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=story["game_options"][0], callback_data="story_game_0"),
            InlineKeyboardButton(text=story["game_options"][1], callback_data="story_game_1"),
        ]
    ])
    await _send_and_track(chat_id, story["game_question"], state, reply_markup=kb, delete_previous=True)
    await state.set_state(StoryOnboarding.waiting_game_tap)


# ── Callback handlers ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("story_game_"), StoryOnboarding.waiting_game_tap)
async def handle_game_tap(callback: CallbackQuery, state: FSMContext):
    """User tapped a game option."""
    await callback.answer()

    choice_idx = int(callback.data.split("_")[-1])
    data = await state.get_data()
    story = data.get("story_data", {})
    game_options = story.get("game_options", GAME_OPTIONS)

    chosen = game_options[choice_idx] if choice_idx < len(game_options) else "that"
    pct = random.randint(58, 78)
    feedbacks = ["Nice one", "Great pick", "Interesting", "Good choice"]
    feedback = random.choice(feedbacks)

    after_text = story.get("game_after", "{feedback}! {pct}% picked the same 🎯")
    after_text = after_text.replace("{feedback}", feedback)
    after_text = after_text.replace("{pct}", str(pct))
    after_text = after_text.replace("{choice}", chosen)

    chat_id = callback.message.chat.id

    # Delete game message, show response
    await _send_and_track(chat_id, after_text, state, delete_previous=True)
    await asyncio.sleep(SHORT_DELAY)

    # Step 4: Match preview — interactive
    match_card = story.get("match_card", "")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 See what happened", callback_data="story_next")]
    ])
    await _send_and_track(chat_id, match_card, state, reply_markup=kb, delete_previous=True)
    await state.set_state(StoryOnboarding.waiting_next_tap)


@router.callback_query(F.data == "story_next", StoryOnboarding.waiting_next_tap)
async def handle_next_tap(callback: CallbackQuery, state: FSMContext):
    """User tapped 'See what happened'."""
    await callback.answer()

    data = await state.get_data()
    story = data.get("story_data", {})
    lang = data.get("story_lang", "en")
    chat_id = callback.message.chat.id

    # Show match card + outcome together
    match_card = story.get("match_card", "")
    match_outcome = story.get("match_outcome", "")
    full_text = f"{match_card}\n\n{match_outcome}"

    await _send_and_track(chat_id, full_text, state, delete_previous=True)
    await asyncio.sleep(STEP_DELAY)

    # Step 5: CTA
    cta_text = "🚀 Let's go" if lang == "en" else "🚀 Поехали"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cta_text, callback_data="story_start_onboarding")]
    ])
    await _send_and_track(chat_id, story.get("cta", "Your turn ✨"), state, reply_markup=kb, delete_previous=True)


@router.callback_query(F.data == "story_start_onboarding")
async def handle_start_onboarding(callback: CallbackQuery, state: FSMContext):
    """CTA: user tapped 'Let's go' — transition to real onboarding."""
    await callback.answer()

    data = await state.get_data()
    event_code = data.get("pending_event")
    event_name = data.get("event_name")
    community_id = data.get("community_id")
    community_name = data.get("community_name")

    # Delete CTA message
    await _delete_msg(callback.message.chat.id, callback.message.message_id)

    # Clear story-specific FSM data but keep context
    await state.update_data(
        story_data=None, story_last_msg_id=None,
        story_mode=None, story_lang=None, story_intent=None,
    )

    # Dispatch to onboarding
    from adapters.telegram.handlers.start import _start_onboarding_with_context
    await _start_onboarding_with_context(
        callback.message, state,
        event_name=event_name,
        event_code=event_code,
        community_id=community_id,
        community_name=community_name,
        skip_story=True,
    )


# ── Ignore text during story ──────────────────────────────────────────────

@router.message(StoryOnboarding.playing)
@router.message(StoryOnboarding.waiting_game_tap)
@router.message(StoryOnboarding.waiting_next_tap)
@router.message(StoryOnboarding.waiting_intent)
async def ignore_text_during_story(message: Message, state: FSMContext):
    """Ignore text messages during story (except custom intent which has its own handler)."""
    pass
