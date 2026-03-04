"""
Story onboarding handler — intent-first flow, bilingual EN/RU.

4 intents: friends, dating, networking, open
7 screens: hook, character, how_it_works, mechanism, match_card, game, cta

Flow (3 phases with message deletion between):
  Phase 1: Intent → Hook → Character → How it works + [See what happened →]
  Phase 2: [delete all] → Mechanism → Match card → Game (2 buttons)
  Phase 3: [delete all] → CTA (personalized by game answer) + [Let's go]
"""

import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from adapters.telegram.states.onboarding import StoryOnboarding
from core.services.story_service import INTENT_QUESTION, get_story, classify_intent

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


def _get_intent_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Build bilingual 4-intent keyboard."""
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Друзья", callback_data="story_intent_friends"),
                InlineKeyboardButton(text="💕 Знакомства", callback_data="story_intent_dating"),
            ],
            [
                InlineKeyboardButton(text="💼 Нетворкинг", callback_data="story_intent_networking"),
                InlineKeyboardButton(text="✨ Любое", callback_data="story_intent_open"),
            ],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Friends", callback_data="story_intent_friends"),
            InlineKeyboardButton(text="💕 Dating", callback_data="story_intent_dating"),
        ],
        [
            InlineKeyboardButton(text="💼 Network", callback_data="story_intent_networking"),
            InlineKeyboardButton(text="✨ Surprise", callback_data="story_intent_open"),
        ],
    ])


# ── Entry point ────────────────────────────────────────────────────────────

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
    question = INTENT_QUESTION.get(lang, INTENT_QUESTION["en"])
    await _send(message.chat.id, question, state, reply_markup=_get_intent_keyboard(lang))
    await state.set_state(StoryOnboarding.waiting_intent)


# ── Intent handlers ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("story_intent_"), StoryOnboarding.waiting_intent)
async def handle_intent_tap(callback: CallbackQuery, state: FSMContext):
    """User picked an intent."""
    await callback.answer()
    intent = callback.data.replace("story_intent_", "")

    if intent == "custom":
        # Delete intent message, ask user to type
        data = await state.get_data()
        lang = data.get("story_lang", "en")
        await _delete_all_story_msgs(callback.message.chat.id, state)
        prompt = "Что ты ищешь? Просто напиши 👇" if lang == "ru" else "What are you looking for? Just type it 👇"
        await _send(callback.message.chat.id, prompt, state)
        await state.set_state(StoryOnboarding.waiting_custom_intent)
        return

    # Delete intent message, start story
    await _delete_all_story_msgs(callback.message.chat.id, state)
    await state.update_data(story_intent=intent)
    data = await state.get_data()
    lang = data.get("story_lang", "en")
    await _play_story(callback.message.chat.id, state, intent, lang)


@router.message(StoryOnboarding.waiting_custom_intent)
async def handle_custom_intent_text(message: Message, state: FSMContext):
    """User typed their specific intent."""
    intent = classify_intent(message.text or "")
    await state.update_data(story_intent=intent)
    data = await state.get_data()
    lang = data.get("story_lang", "en")

    # Delete prompt + user's message
    await _delete_all_story_msgs(message.chat.id, state)
    await _delete_msg(message.chat.id, message.message_id)

    await _play_story(message.chat.id, state, intent, lang)


# ── Phase 1: Story playback ──────────────────────────────────────────────

async def _play_story(chat_id: int, state: FSMContext, intent: str, lang: str):
    """Phase 1: Hook → Character → How it works + reveal button."""
    story = get_story(intent, lang)
    await state.update_data(story_data=story)
    await state.set_state(StoryOnboarding.playing)

    # Hook
    await _send(chat_id, story["hook"], state)
    await asyncio.sleep(STEP_DELAY)

    # Character
    await _send(chat_id, story["character"], state)
    await asyncio.sleep(STEP_DELAY)

    # How it works + interactive button
    btn_text = "👀 Дальше →" if lang == "ru" else "👀 Next →"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, callback_data="story_reveal")]
    ])
    await _send(chat_id, story["how_it_works"], state, reply_markup=kb)
    await state.set_state(StoryOnboarding.waiting_reveal_tap)


# ── Phase 2: Reveal → Match card → Game ──────────────────────────────────

@router.callback_query(F.data == "story_reveal", StoryOnboarding.waiting_reveal_tap)
async def handle_reveal_tap(callback: CallbackQuery, state: FSMContext):
    """User tapped 'See what happened'. Delete Phase 1, show mechanism + card + game."""
    await callback.answer()
    chat_id = callback.message.chat.id
    data = await state.get_data()
    story = data.get("story_data", {})
    lang = data.get("story_lang", "en")

    # Delete all Phase 1 messages (hook, character, how it works)
    await _delete_all_story_msgs(chat_id, state)

    # Mechanism reveal
    await _send(chat_id, story.get("mechanism", ""), state)
    await asyncio.sleep(STEP_DELAY)

    # Match card
    await _send(chat_id, story.get("match_card", ""), state)
    await asyncio.sleep(STEP_DELAY)

    # Game — interactive with intent-specific options
    game_options = story.get("game_options", ["Option A", "Option B"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=game_options[0], callback_data="story_game_0"),
            InlineKeyboardButton(text=game_options[1], callback_data="story_game_1"),
        ]
    ])
    await _send(chat_id, story.get("game_question", ""), state, reply_markup=kb)
    await state.set_state(StoryOnboarding.waiting_game_tap)


# ── Phase 3: Game result → CTA (merged) ─────────────────────────────────

@router.callback_query(F.data.startswith("story_game_"), StoryOnboarding.waiting_game_tap)
async def handle_game_tap(callback: CallbackQuery, state: FSMContext):
    """User tapped a game option. Delete Phase 2, show personalized CTA."""
    await callback.answer()

    choice_idx = int(callback.data.split("_")[-1])
    data = await state.get_data()
    story = data.get("story_data", {})
    lang = data.get("story_lang", "en")

    # Get personalized CTA based on game answer
    ctas = story.get("ctas", [])
    if choice_idx < len(ctas):
        cta_text = ctas[choice_idx]
    elif ctas:
        cta_text = ctas[0]
    else:
        cta_text = "Your turn ✨" if lang == "en" else "Твоя очередь ✨"

    chat_id = callback.message.chat.id

    # Delete all Phase 2 messages (mechanism, match card, game)
    await _delete_all_story_msgs(chat_id, state)

    # CTA with Let's go button
    btn_text = "🚀 Погнали!" if lang == "ru" else "🚀 Let's go!"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, callback_data="story_start_onboarding")]
    ])
    await _send(chat_id, cta_text, state, reply_markup=kb)
    await state.set_state(StoryOnboarding.waiting_next_tap)


# ── Transition to onboarding ─────────────────────────────────────────────

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

    # Clear story FSM data BUT keep story_intent for agent onboarding
    await state.update_data(
        story_data=None, story_msg_ids=None,
        story_mode=None, story_lang=None,
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
@router.message(StoryOnboarding.waiting_reveal_tap)
@router.message(StoryOnboarding.waiting_game_tap)
@router.message(StoryOnboarding.waiting_next_tap)
@router.message(StoryOnboarding.waiting_intent)
async def ignore_text_during_story(message: Message, state: FSMContext):
    """Ignore text messages during story (except custom intent which has its own handler)."""
    pass
