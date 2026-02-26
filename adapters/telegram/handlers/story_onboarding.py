"""
Story onboarding handler — intent-first flow.

Flow: Intent → Hook → Character → How it works → Game → Match card → CTA → Onboarding
Messages accumulate during auto-play. Deleted only when user taps a button.
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


async def _send(chat_id: int, text: str, state: FSMContext,
                reply_markup=None) -> int:
    """Send a message and track its ID for later deletion."""
    from adapters.telegram.loader import bot
    sent = await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")

    # Track all story message IDs
    data = await state.get_data()
    msg_ids = data.get("story_msg_ids", [])
    msg_ids.append(sent.message_id)
    await state.update_data(story_msg_ids=msg_ids)
    return sent.message_id


async def _delete_all_story_msgs(chat_id: int, state: FSMContext):
    """Delete all tracked story messages."""
    data = await state.get_data()
    msg_ids = data.get("story_msg_ids", [])
    for mid in msg_ids:
        await _delete_msg(chat_id, mid)
    await state.update_data(story_msg_ids=[])


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
    fsm_data = {
        "story_lang": lang, "story_mode": mode, "story_msg_ids": [],
        "user_first_name": message.from_user.first_name,
    }
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
    await _send(message.chat.id, INTENT_QUESTION, state, reply_markup=INTENT_KEYBOARD)
    await state.set_state(StoryOnboarding.waiting_intent)


# ── Intent handlers ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("story_intent_"), StoryOnboarding.waiting_intent)
async def handle_intent_tap(callback: CallbackQuery, state: FSMContext):
    """User picked an intent."""
    await callback.answer()
    intent = callback.data.replace("story_intent_", "")

    if intent == "custom":
        # Delete intent message, ask user to type
        await _delete_all_story_msgs(callback.message.chat.id, state)
        await _send(
            callback.message.chat.id,
            "What are you looking for? Just type it 👇",
            state,
        )
        await state.set_state(StoryOnboarding.waiting_custom_intent)
        return

    # Delete intent message, start story
    await _delete_all_story_msgs(callback.message.chat.id, state)
    await state.update_data(story_intent=intent)
    await _play_story(callback.message.chat.id, state, intent)


@router.message(StoryOnboarding.waiting_custom_intent)
async def handle_custom_intent_text(message: Message, state: FSMContext):
    """User typed their specific intent."""
    intent = classify_intent(message.text or "")
    await state.update_data(story_intent=intent)

    # Delete prompt + user's message
    await _delete_all_story_msgs(message.chat.id, state)
    await _delete_msg(message.chat.id, message.message_id)

    await _play_story(message.chat.id, state, intent)


# ── Story playback ─────────────────────────────────────────────────────────

async def _play_story(chat_id: int, state: FSMContext, intent: str):
    """Play the story. Messages accumulate — no deletion during auto-play."""
    story = get_story(intent)
    await state.update_data(story_data=story)
    await state.set_state(StoryOnboarding.playing)

    # Step 1: Hook
    await _send(chat_id, story["hook"], state)
    await asyncio.sleep(STEP_DELAY)

    # Step 2: Character
    await _send(chat_id, story["character"], state)
    await asyncio.sleep(STEP_DELAY)

    # Step 3: How it works
    await _send(chat_id, story["how_it_works"], state)
    await asyncio.sleep(STEP_DELAY)

    # Step 4: Game — interactive (messages stay until user taps)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=story["game_options"][0], callback_data="story_game_0"),
            InlineKeyboardButton(text=story["game_options"][1], callback_data="story_game_1"),
        ]
    ])
    await _send(chat_id, story["game_question"], state, reply_markup=kb)
    await state.set_state(StoryOnboarding.waiting_game_tap)


# ── Callback handlers ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("story_game_"), StoryOnboarding.waiting_game_tap)
async def handle_game_tap(callback: CallbackQuery, state: FSMContext):
    """User tapped a game option. Delete all previous messages, show result + match."""
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

    # Delete all story messages so far (hook, character, how it works, game)
    await _delete_all_story_msgs(chat_id, state)

    # Show game result
    await _send(chat_id, after_text, state)
    await asyncio.sleep(SHORT_DELAY)

    # Show match card directly (full card with outcome)
    match_card = story.get("match_card", "")
    await _send(chat_id, match_card, state)
    await asyncio.sleep(STEP_DELAY)

    # CTA
    lang = data.get("story_lang", "en")
    cta_text = "🚀 Let's go" if lang == "en" else "🚀 Поехали"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cta_text, callback_data="story_start_onboarding")]
    ])
    await _send(chat_id, story.get("cta", "Your turn ✨"), state, reply_markup=kb)
    await state.set_state(StoryOnboarding.waiting_next_tap)


@router.callback_query(F.data == "story_start_onboarding")
async def handle_start_onboarding(callback: CallbackQuery, state: FSMContext):
    """CTA: user tapped 'Let's go' — clean up and start onboarding."""
    await callback.answer()

    data = await state.get_data()
    event_code = data.get("pending_event")
    event_name = data.get("event_name")
    community_id = data.get("community_id")
    community_name = data.get("community_name")

    # Delete all story messages
    await _delete_all_story_msgs(callback.message.chat.id, state)

    # Clear story FSM data
    await state.update_data(
        story_data=None, story_msg_ids=None,
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
