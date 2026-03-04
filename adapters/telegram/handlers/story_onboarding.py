"""
Story Onboarding Handler.

Shows a 7-screen story flow before actual onboarding:
1. Intent selection (4 options)
2. Hook → Character → How it works → Mechanism → Match card → Game → CTA
3. CTA "Let's go" button starts real onboarding

Bilingual: EN/RU based on Telegram language setting.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from adapters.telegram.states.onboarding import StoryOnboardingStates
from adapters.telegram.keyboards import (
    get_story_intent_keyboard,
    get_story_next_keyboard,
    get_story_game_keyboard,
    get_story_cta_keyboard,
)
from core.services.story_service import (
    get_screen,
    get_screen_index,
    get_next_screen,
    SCREEN_ORDER,
)
from core.utils.language import detect_lang

logger = logging.getLogger(__name__)

router = Router(name="story_onboarding")


# === Entry Point (called from start.py) ===

async def start_story_onboarding(message, state: FSMContext, lang: str = None,
                                  event_name: str = None, event_code: str = None):
    """Start the story onboarding flow. Called before actual onboarding."""
    if lang is None:
        lang = detect_lang(message)

    await state.update_data(
        story_lang=lang,
        story_event_name=event_name,
        story_event_code=event_code,
    )

    # Show intent selection
    if lang == "ru":
        text = "🌐 <b>Зачем ты здесь?</b>\n\nВыбери, и я покажу как это работает."
    else:
        text = "🌐 <b>What brings you here?</b>\n\nPick one, and I'll show you how it works."

    await message.answer(text, reply_markup=get_story_intent_keyboard(lang))
    await state.set_state(StoryOnboardingStates.choosing_intent)


# === Intent Selection ===

@router.callback_query(StoryOnboardingStates.choosing_intent, F.data.startswith("story_intent_"))
async def handle_intent_selection(callback: CallbackQuery, state: FSMContext):
    """User picked an intent — start the story screens."""
    intent = callback.data.replace("story_intent_", "")
    data = await state.get_data()
    lang = data.get("story_lang", "en")

    await state.update_data(story_intent=intent, story_screen="hook")

    # Show first screen (hook)
    text = get_screen(intent, "hook", lang)
    if not text:
        logger.error(f"Missing hook screen for intent: {intent}")
        await callback.answer("Something went wrong", show_alert=True)
        return

    await callback.message.edit_text(
        text,
        reply_markup=get_story_next_keyboard(lang, screen_index=0),
    )
    await state.set_state(StoryOnboardingStates.viewing_screen)
    await callback.answer()


# === Screen Navigation ===

@router.callback_query(StoryOnboardingStates.viewing_screen, F.data == "story_next")
async def handle_next_screen(callback: CallbackQuery, state: FSMContext):
    """Advance to the next story screen."""
    data = await state.get_data()
    lang = data.get("story_lang", "en")
    intent = data.get("story_intent", "friends")
    current_screen = data.get("story_screen", "hook")

    next_screen = get_next_screen(current_screen)
    if not next_screen:
        # Shouldn't happen — CTA is the last screen and has its own handler
        await callback.answer()
        return

    await state.update_data(story_screen=next_screen)

    if next_screen == "game":
        # Game screen — show question with answer buttons
        game_data = get_screen(intent, "game", lang)
        if game_data:
            await callback.message.edit_text(
                game_data["question"],
                reply_markup=get_story_game_keyboard(game_data["options"]),
            )
            await state.set_state(StoryOnboardingStates.playing_game)
        else:
            # Skip game if missing — go to CTA
            await _show_cta_with_default(callback, state, intent, lang)
    else:
        # Regular text screen
        text = get_screen(intent, next_screen, lang)
        if not text:
            logger.warning(f"Missing screen {next_screen} for intent {intent}")
            await callback.answer()
            return

        screen_idx = get_screen_index(next_screen)

        # how_it_works screen has a special button text
        btn_label = None
        if next_screen == "how_it_works":
            btn_label = "See what happened →" if lang == "en" else "Что получилось →"

        await callback.message.edit_text(
            text,
            reply_markup=get_story_next_keyboard(lang, screen_index=screen_idx, btn_label=btn_label),
        )

    await callback.answer()


# === Game Answer ===

@router.callback_query(StoryOnboardingStates.playing_game, F.data.startswith("game_"))
async def handle_game_answer(callback: CallbackQuery, state: FSMContext):
    """User answered the game question — show CTA with personalized response."""
    game_answer = callback.data
    data = await state.get_data()
    lang = data.get("story_lang", "en")
    intent = data.get("story_intent", "friends")

    await state.update_data(story_game_answer=game_answer, story_screen="cta")

    # Get CTA text based on game answer
    cta_data = get_screen(intent, "cta", lang)
    if cta_data and isinstance(cta_data, dict):
        text = cta_data.get(game_answer)
        if not text:
            # Fallback to first available CTA
            text = next(iter(cta_data.values()), None)
    else:
        text = None

    if not text:
        text = ("Let's find your people!" if lang == "en"
                else "Давай найдём твоих людей!")

    await callback.message.edit_text(
        text,
        reply_markup=get_story_cta_keyboard(lang),
    )
    await state.set_state(StoryOnboardingStates.viewing_cta)
    await callback.answer()


async def _show_cta_with_default(callback, state, intent, lang):
    """Show CTA screen with a default game answer (when game is skipped)."""
    cta_data = get_screen(intent, "cta", lang)
    if cta_data and isinstance(cta_data, dict):
        text = next(iter(cta_data.values()), None)
    else:
        text = None

    if not text:
        text = ("Let's find your people!" if lang == "en"
                else "Давай найдём твоих людей!")

    await state.update_data(story_screen="cta")
    await callback.message.edit_text(
        text,
        reply_markup=get_story_cta_keyboard(lang),
    )
    await state.set_state(StoryOnboardingStates.viewing_cta)


# === CTA — Start Real Onboarding ===

@router.callback_query(StoryOnboardingStates.viewing_cta, F.data == "story_start_onboarding")
async def handle_start_onboarding(callback: CallbackQuery, state: FSMContext):
    """User clicked 'Let's go' — start actual onboarding."""
    data = await state.get_data()
    lang = data.get("story_lang", "en")
    event_name = data.get("story_event_name")
    event_code = data.get("story_event_code")
    intent = data.get("story_intent", "friends")

    # Clear story state
    await state.clear()

    # Start real onboarding
    from adapters.telegram.config import ONBOARDING_VERSION

    if ONBOARDING_VERSION == "audio":
        from adapters.telegram.handlers.onboarding_audio import start_audio_onboarding
        await start_audio_onboarding(
            callback.message, state,
            event_name=event_name,
            event_code=event_code,
            lang=lang,
        )
    elif ONBOARDING_VERSION == "v2":
        from adapters.telegram.handlers.onboarding_v2 import start_conversational_onboarding
        await start_conversational_onboarding(
            callback.message, state,
            event_name=event_name,
            event_code=event_code,
        )
    else:
        # Legacy v1 — just show name prompt
        from adapters.telegram.states.onboarding import OnboardingStates
        await state.update_data(language=lang)
        if lang == "ru":
            text = "👋 Отлично! Давай познакомимся — как тебя зовут?"
        else:
            text = "👋 Great! Let's get to know each other — what's your name?"
        await callback.message.answer(text)
        await state.set_state(OnboardingStates.waiting_name)

    await callback.answer()


# === Back to Intent Selection ===

@router.callback_query(
    StoryOnboardingStates.viewing_screen,
    F.data == "story_back_to_intents"
)
@router.callback_query(
    StoryOnboardingStates.playing_game,
    F.data == "story_back_to_intents"
)
@router.callback_query(
    StoryOnboardingStates.viewing_cta,
    F.data == "story_back_to_intents"
)
async def handle_back_to_intents(callback: CallbackQuery, state: FSMContext):
    """Go back to intent selection."""
    data = await state.get_data()
    lang = data.get("story_lang", "en")

    if lang == "ru":
        text = "🌐 <b>Зачем ты здесь?</b>\n\nВыбери, и я покажу как это работает."
    else:
        text = "🌐 <b>What brings you here?</b>\n\nPick one, and I'll show you how it works."

    await callback.message.edit_text(text, reply_markup=get_story_intent_keyboard(lang))
    await state.set_state(StoryOnboardingStates.choosing_intent)
    await callback.answer()
