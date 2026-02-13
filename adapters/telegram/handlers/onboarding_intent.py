"""
Intent-based onboarding handler (V1.1).
Four modes: Agent (recommended), Voice, Quick Choices, Social Media.
All modes converge to city → photo → confirm → save.
"""

import asyncio
import json
import re
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from locales import t
from core.domain.models import MessagePlatform, UserUpdate
from core.prompts.intent_onboarding import (
    VOICE_STAGE1_EXTRACTION, VOICE_STAGE2_EXTRACTION, VOICE_STAGE3_EXTRACTION,
    VOICE_FOLLOWUP_CHECK, AGENT_SYSTEM_PROMPT, AGENT_INTENT_GOALS,
    AGENT_EXTRACTION_PROMPT, SOCIAL_LINK_EXTRACTION, SOCIAL_GAP_ANALYSIS,
    format_profile_summary,
)
from adapters.telegram.loader import (
    user_service, bot, voice_service, ai_service, embedding_service, user_repo,
)
from adapters.telegram.keyboards.inline import (
    get_intent_selection_keyboard, get_mode_choice_keyboard,
    get_question_buttons_keyboard, get_question_multi_select_keyboard,
    get_social_source_keyboard, get_intent_city_keyboard,
    get_photo_skip_keyboard, get_intent_confirm_keyboard,
)
from adapters.telegram.states.onboarding import IntentOnboardingStates
from core.utils.language import detect_lang

logger = logging.getLogger(__name__)

router = Router()

MAX_INTENTS = 3
MAX_AGENT_TURNS = 12  # Max messages from user before forcing profile build


# ============================================================
# ENTRY POINT
# ============================================================

async def start_intent_onboarding(
    message: Message,
    state: FSMContext,
    event_name: Optional[str] = None,
    event_code: Optional[str] = None,
):
    """Start the intent-based onboarding flow."""
    lang = detect_lang(message)
    name = message.from_user.first_name or "friend"

    # Ensure user exists
    user = await user_service.get_or_create_user(
        platform=MessagePlatform.TELEGRAM,
        platform_user_id=str(message.from_user.id),
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    # Save language to DB
    try:
        await user_service.update_user(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id=str(message.from_user.id),
            language=lang,
        )
    except Exception:
        pass

    # Welcome message
    if event_name:
        welcome = t("welcome_event", lang, name=name, event_name=event_name)
    else:
        welcome = t("welcome", lang, name=name)

    await message.answer(f"<b>{welcome}</b>\n\n{t('intent_header', lang)}")

    await state.set_state(IntentOnboardingStates.selecting_intents)
    await state.update_data(
        language=lang,
        selected_intents=[],
        pending_event_code=event_code,
        profile_data={},
        display_name=name,
    )

    await message.answer(
        t("intent_header", lang),
        reply_markup=get_intent_selection_keyboard([], lang),
    )


# ============================================================
# STEP 1: INTENT SELECTION
# ============================================================

@router.callback_query(IntentOnboardingStates.selecting_intents, F.data.startswith("intent_"))
async def handle_intent_toggle(callback: CallbackQuery, state: FSMContext):
    """Toggle intent selection (multi-select, max 3)."""
    data = await state.get_data()
    lang = data.get("language", "en")
    selected = data.get("selected_intents", [])

    intent = callback.data.replace("intent_", "")

    if intent in selected:
        selected.remove(intent)
    else:
        if len(selected) >= MAX_INTENTS:
            await callback.answer(t("intent_max_warning", lang), show_alert=True)
            return
        selected.append(intent)

    await state.update_data(selected_intents=selected)

    await callback.message.edit_reply_markup(
        reply_markup=get_intent_selection_keyboard(selected, lang)
    )
    await callback.answer()


@router.callback_query(IntentOnboardingStates.selecting_intents, F.data == "intents_done")
async def handle_intents_done(callback: CallbackQuery, state: FSMContext):
    """Intents selected — show mode choice."""
    data = await state.get_data()
    lang = data.get("language", "en")
    selected = data.get("selected_intents", [])

    if not selected:
        await callback.answer("Pick at least one!", show_alert=True)
        return

    await callback.message.edit_text(
        t("mode_header", lang),
        reply_markup=get_mode_choice_keyboard(lang),
    )
    await state.set_state(IntentOnboardingStates.choosing_mode)
    await callback.answer()


# ============================================================
# STEP 2: MODE CHOICE
# ============================================================

@router.callback_query(IntentOnboardingStates.choosing_mode, F.data == "mode_agent")
async def start_agent_mode(callback: CallbackQuery, state: FSMContext):
    """Start agent conversational onboarding."""
    data = await state.get_data()
    lang = data.get("language", "en")

    await callback.message.edit_text(t("agent_intro", lang))
    await state.set_state(IntentOnboardingStates.agent_chatting)
    await state.update_data(agent_history=[], agent_turn_count=0)
    await callback.answer()


@router.callback_query(IntentOnboardingStates.choosing_mode, F.data == "mode_voice")
async def start_voice_mode(callback: CallbackQuery, state: FSMContext):
    """Start voice onboarding."""
    data = await state.get_data()
    lang = data.get("language", "en")

    await callback.message.edit_text(
        f"\U0001f3a4 {t('voice_stage1', lang)}"
    )
    await state.set_state(IntentOnboardingStates.voice_stage1)
    await callback.answer()


@router.callback_query(IntentOnboardingStates.choosing_mode, F.data == "mode_buttons")
async def start_buttons_mode(callback: CallbackQuery, state: FSMContext):
    """Start quick choices onboarding."""
    data = await state.get_data()
    lang = data.get("language", "en")
    intents = data.get("selected_intents", [])

    # Build question queue based on intents
    questions = _build_question_queue(intents)
    await state.update_data(question_queue=questions, question_index=0, qc_answers={})

    # Ask first question
    await _ask_next_question(callback.message, state, edit=True)
    await callback.answer()


@router.callback_query(IntentOnboardingStates.choosing_mode, F.data == "mode_social")
async def start_social_mode(callback: CallbackQuery, state: FSMContext):
    """Start social media import onboarding."""
    data = await state.get_data()
    lang = data.get("language", "en")

    await callback.message.edit_text(
        t("social_header", lang),
        reply_markup=get_social_source_keyboard(lang),
    )
    await state.set_state(IntentOnboardingStates.social_waiting_input)
    await callback.answer()


# ============================================================
# AGENT MODE — 3-Layer Architecture
# Layer 1: Conversation (user-facing, warm natural dialogue)
# Layer 2: Extraction (hidden, parses each message into profile data)
# Layer 3: Strategy (hidden, decides what to ask next)
# ============================================================

@router.message(IntentOnboardingStates.agent_chatting, F.text)
async def handle_agent_text(message: Message, state: FSMContext):
    """Handle text message in agent conversation — 3-layer processing."""
    if message.text and message.text.startswith("/"):
        # Allow commands to pass through
        return

    data = await state.get_data()
    lang = data.get("language", "en")
    intents = data.get("selected_intents", [])
    history = data.get("agent_history", [])
    turn_count = data.get("agent_turn_count", 0)
    profile_state = data.get("agent_profile_state", {})
    event_code = data.get("pending_event_code")

    # Add user message to history
    history.append({"role": "user", "content": message.text})
    turn_count += 1

    # === LAYER 2 + 3: Extraction + Strategy (parallel, hidden) ===
    conversation_str = "\n".join(
        f"{'User' if h['role'] == 'user' else 'Agent'}: {h['content']}"
        for h in history
    )

    strategy_result = None
    try:
        from core.prompts.intent_onboarding import AGENT_STRATEGY_PROMPT
        strategy_raw = await ai_service.chat(
            AGENT_STRATEGY_PROMPT.format(
                conversation=conversation_str,
                intents=", ".join(intents),
                profile_state=json.dumps(profile_state, ensure_ascii=False) if profile_state else "{}",
            ),
            max_tokens=800,
        )
        strategy_raw = re.sub(r'```json\s*', '', strategy_raw)
        strategy_raw = re.sub(r'```\s*', '', strategy_raw)
        strategy_result = json.loads(strategy_raw.strip())

        # Update profile state from extraction
        if strategy_result.get("profile_state"):
            profile_state = strategy_result["profile_state"]

    except Exception as e:
        logger.warning(f"Agent strategy extraction failed: {e}")
        strategy_result = {
            "strategy": {
                "missing_required": ["unknown"],
                "next_topic": "continue naturally",
                "engagement_level": "medium",
                "adapt_approach": "",
            }
        }

    strategy = strategy_result.get("strategy", {})
    missing = strategy.get("missing_required", [])
    next_topic = strategy.get("next_topic", "continue naturally")
    engagement = strategy.get("engagement_level", "medium")
    completion = profile_state.get("completion_score", 0.0)

    # === LAYER 1: Conversation (user-facing) ===
    # Build intent-specific goals
    intent_goals = "\n".join(
        AGENT_INTENT_GOALS.get(intent, "") for intent in intents
    )

    # Build context
    context_parts = []
    if event_code:
        context_parts.append(f"User came from event: {event_code}")
    context = "\n".join(context_parts) if context_parts else "Organic signup"

    system_prompt = AGENT_SYSTEM_PROMPT.format(
        intents=", ".join(intents),
        intent_specific_goals=intent_goals,
        profile_state=json.dumps(profile_state, ensure_ascii=False) if profile_state else "{}",
        missing_required=", ".join(missing) if missing else "None — profile looks complete",
        next_topic=next_topic,
        engagement_level=engagement,
        context=context,
    )

    # Show typing
    try:
        await bot.send_chat_action(message.chat.id, "typing")
    except Exception:
        pass

    try:
        response = await ai_service.client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            messages=[
                {"role": "system", "content": system_prompt},
                *[{"role": h["role"], "content": h["content"]} for h in history],
            ],
        )
        agent_reply = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Agent conversation error: {e}", exc_info=True)
        agent_reply = t("agent_continue", lang)

    # Check if agent signaled profile ready
    profile_ready = "[PROFILE_READY]" in agent_reply
    agent_reply_clean = agent_reply.replace("[PROFILE_READY]", "").strip()

    # Add agent reply to history
    history.append({"role": "assistant", "content": agent_reply_clean})

    await state.update_data(
        agent_history=history,
        agent_turn_count=turn_count,
        agent_profile_state=profile_state,
    )

    # Force profile build after MAX_AGENT_TURNS or when ready
    if profile_ready or turn_count >= MAX_AGENT_TURNS or completion >= 0.7:
        await message.answer(agent_reply_clean)
        await _agent_build_profile(message, state)
        return

    await message.answer(agent_reply_clean)


@router.message(IntentOnboardingStates.agent_chatting, F.voice)
async def handle_agent_voice(message: Message, state: FSMContext):
    """Handle voice message in agent mode — transcribe and treat as text."""
    data = await state.get_data()
    lang = data.get("language", "en")

    try:
        await bot.send_chat_action(message.chat.id, "typing")
    except Exception:
        pass

    try:
        # Download and transcribe
        file_info = await bot.get_file(message.voice.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        transcript = await voice_service.transcribe(file_bytes.read())

        if not transcript or not transcript.strip():
            await message.answer(t("error_generic", lang))
            return

        # Inject transcript as text message and process
        message.text = transcript
        await handle_agent_text(message, state)

    except Exception as e:
        logger.error(f"Agent voice error: {e}", exc_info=True)
        await message.answer(t("error_generic", lang))


async def _agent_build_profile(message: Message, state: FSMContext):
    """Extract final profile from agent conversation and show confirmation."""
    data = await state.get_data()
    lang = data.get("language", "en")
    intents = data.get("selected_intents", [])
    history = data.get("agent_history", [])
    profile_state = data.get("agent_profile_state", {})

    # Build conversation string
    conversation = "\n".join(
        f"{'User' if h['role'] == 'user' else 'Agent'}: {h['content']}"
        for h in history
    )

    prompt = AGENT_EXTRACTION_PROMPT.format(
        conversation=conversation,
        intents=", ".join(intents),
        profile_state=json.dumps(profile_state, ensure_ascii=False) if profile_state else "{}",
    )

    try:
        raw = await ai_service.chat(prompt, max_tokens=1000)
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        profile_data = json.loads(raw.strip())
    except Exception as e:
        logger.error(f"Agent extraction failed: {e}", exc_info=True)
        # Fall back to profile_state
        profile_data = {}
        if profile_state:
            profile_data = {k: v for k, v in profile_state.items()
                           if k not in ("completion_score", "messages_exchanged", "context_tags", "onboarding_source")
                           and v}

    # Merge with any existing data
    existing = data.get("profile_data", {})
    for key, val in profile_data.items():
        if val and (not existing.get(key)):
            existing[key] = val
    profile_data = existing

    # Use display_name from TG if not extracted
    if not profile_data.get("display_name"):
        profile_data["display_name"] = data.get("display_name")

    await state.update_data(profile_data=profile_data)

    # Show profile summary
    summary = format_profile_summary(profile_data, lang)
    await message.answer(
        t("agent_profile_ready", lang, profile=summary),
        reply_markup=get_intent_confirm_keyboard(lang),
    )
    await state.set_state(IntentOnboardingStates.choosing_city)
    # Skip city if already detected in conversation
    if profile_data.get("city_current"):
        await state.update_data(city_current=profile_data["city_current"])


# ============================================================
# VOICE MODE
# ============================================================

@router.message(IntentOnboardingStates.voice_stage1, F.voice)
async def handle_voice_stage1(message: Message, state: FSMContext):
    """Process voice stage 1: general intro."""
    await _process_voice_stage(
        message, state,
        extraction_prompt=VOICE_STAGE1_EXTRACTION,
        next_state=IntentOnboardingStates.voice_stage2,
        stage_key="voice_stage2",
    )


@router.message(IntentOnboardingStates.voice_stage2, F.voice)
async def handle_voice_stage2(message: Message, state: FSMContext):
    """Process voice stage 2: intent-specific question."""
    data = await state.get_data()
    intents = data.get("selected_intents", [])
    primary = intents[0] if intents else "networking"
    question = data.get("language", "en")

    await _process_voice_stage(
        message, state,
        extraction_prompt=VOICE_STAGE2_EXTRACTION,
        prompt_kwargs={"intents": ", ".join(intents), "question": f"stage2_{primary}"},
        next_state=IntentOnboardingStates.voice_stage3,
        stage_key="voice_stage3",
    )


@router.message(IntentOnboardingStates.voice_stage3, F.voice)
async def handle_voice_stage3(message: Message, state: FSMContext):
    """Process voice stage 3: ideal match."""
    await _process_voice_stage(
        message, state,
        extraction_prompt=VOICE_STAGE3_EXTRACTION,
        next_state=IntentOnboardingStates.voice_stage4,
        stage_key="voice_stage4_check",
    )


@router.message(IntentOnboardingStates.voice_stage4, F.voice)
async def handle_voice_stage4(message: Message, state: FSMContext):
    """Process voice stage 4: optional follow-up."""
    data = await state.get_data()
    lang = data.get("language", "en")

    # Transcribe and extract
    transcript = await _transcribe_voice(message)
    if not transcript:
        await message.answer(t("error_generic", lang))
        return

    # Merge any new data
    profile_data = data.get("profile_data", {})
    try:
        raw = await ai_service.chat(
            VOICE_STAGE3_EXTRACTION.format(transcript=transcript),
            max_tokens=500,
        )
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        new_data = json.loads(raw.strip())
        for k, v in new_data.items():
            if v and not profile_data.get(k):
                profile_data[k] = v
    except Exception:
        pass

    await state.update_data(profile_data=profile_data)
    await _go_to_city_step(message, state)


# Voice helper: handle text input in voice states (let them type too)
@router.message(IntentOnboardingStates.voice_stage1, F.text)
@router.message(IntentOnboardingStates.voice_stage2, F.text)
@router.message(IntentOnboardingStates.voice_stage3, F.text)
@router.message(IntentOnboardingStates.voice_stage4, F.text)
async def handle_voice_text_fallback(message: Message, state: FSMContext):
    """If user types text instead of voice, accept it."""
    if message.text and message.text.startswith("/"):
        return  # Skip commands

    data = await state.get_data()
    lang = data.get("language", "en")
    current_state = await state.get_state()

    # Simulate a transcript
    message.voice = None  # Clear voice flag
    # Determine which stage and process
    if current_state == IntentOnboardingStates.voice_stage1.state:
        await _process_text_as_voice(message, state, VOICE_STAGE1_EXTRACTION, IntentOnboardingStates.voice_stage2, "voice_stage2")
    elif current_state == IntentOnboardingStates.voice_stage2.state:
        intents = data.get("selected_intents", [])
        await _process_text_as_voice(message, state, VOICE_STAGE2_EXTRACTION, IntentOnboardingStates.voice_stage3, "voice_stage3",
                                     prompt_kwargs={"intents": ", ".join(intents), "question": "stage2"})
    elif current_state == IntentOnboardingStates.voice_stage3.state:
        await _process_text_as_voice(message, state, VOICE_STAGE3_EXTRACTION, IntentOnboardingStates.voice_stage4, "voice_stage4_check")
    elif current_state == IntentOnboardingStates.voice_stage4.state:
        # Last stage — go to city
        profile_data = data.get("profile_data", {})
        await state.update_data(profile_data=profile_data)
        await _go_to_city_step(message, state)


async def _process_text_as_voice(message, state, extraction_prompt, next_state, stage_key, prompt_kwargs=None):
    """Process text input as if it were a voice transcript."""
    data = await state.get_data()
    lang = data.get("language", "en")
    transcript = message.text

    kwargs = {"transcript": transcript}
    if prompt_kwargs:
        kwargs.update(prompt_kwargs)

    profile_data = data.get("profile_data", {})

    try:
        raw = await ai_service.chat(extraction_prompt.format(**kwargs), max_tokens=500)
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        new_data = json.loads(raw.strip())
        for k, v in new_data.items():
            if v and not profile_data.get(k):
                profile_data[k] = v
    except Exception as e:
        logger.warning(f"Text extraction failed: {e}")

    await state.update_data(profile_data=profile_data)

    # Check if this is the follow-up check stage
    if stage_key == "voice_stage4_check":
        await _check_followup_or_city(message, state)
        return

    # Move to next stage
    intents = data.get("selected_intents", [])
    primary = intents[0] if intents else "networking"

    if stage_key == "voice_stage2":
        question_key = f"voice_stage2_{primary}"
        await message.answer(f"\U0001f3a4 {t(question_key, lang)}")
    elif stage_key == "voice_stage3":
        await message.answer(f"\U0001f3a4 {t('voice_stage3', lang)}")
    elif stage_key == "voice_stage4_check":
        pass  # handled above

    await state.set_state(next_state)


async def _process_voice_stage(message, state, extraction_prompt, next_state, stage_key, prompt_kwargs=None):
    """Generic voice stage processor."""
    data = await state.get_data()
    lang = data.get("language", "en")

    processing_msg = await message.answer(t("voice_processing", lang))

    transcript = await _transcribe_voice(message)
    if not transcript:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(t("error_generic", lang))
        return

    kwargs = {"transcript": transcript}
    if prompt_kwargs:
        kwargs.update(prompt_kwargs)

    profile_data = data.get("profile_data", {})

    try:
        raw = await ai_service.chat(extraction_prompt.format(**kwargs), max_tokens=500)
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        new_data = json.loads(raw.strip())
        for k, v in new_data.items():
            if v and not profile_data.get(k):
                profile_data[k] = v
    except Exception as e:
        logger.warning(f"Voice extraction failed: {e}")

    await state.update_data(profile_data=profile_data)

    try:
        await processing_msg.delete()
    except Exception:
        pass

    # Handle stage transitions
    if stage_key == "voice_stage4_check":
        await _check_followup_or_city(message, state)
        return

    intents = data.get("selected_intents", [])
    primary = intents[0] if intents else "networking"

    if stage_key == "voice_stage2":
        question_key = f"voice_stage2_{primary}"
        await message.answer(f"\U0001f3a4 {t(question_key, lang)}")
    elif stage_key == "voice_stage3":
        await message.answer(f"\U0001f3a4 {t('voice_stage3', lang)}")

    await state.set_state(next_state)


async def _check_followup_or_city(message, state):
    """Check if follow-up needed, otherwise go to city."""
    data = await state.get_data()
    lang = data.get("language", "en")
    intents = data.get("selected_intents", [])
    profile_data = data.get("profile_data", {})

    prompt = VOICE_FOLLOWUP_CHECK.format(
        intents=", ".join(intents),
        bio=profile_data.get("bio", ""),
        looking_for=profile_data.get("looking_for", ""),
        can_help_with=profile_data.get("can_help_with", ""),
        interests=", ".join(profile_data.get("interests", [])),
        profession=profile_data.get("profession", ""),
        ideal_connection=profile_data.get("ideal_connection", ""),
        gender=profile_data.get("gender", ""),
        looking_for_gender=", ".join(profile_data.get("looking_for_gender", [])),
    )

    try:
        raw = await ai_service.chat(prompt, max_tokens=300)
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        result = json.loads(raw.strip())

        if result.get("needs_followup"):
            question = result.get(f"question_{lang}", result.get("question_en", ""))
            if question:
                await message.answer(t("voice_stage4_prompt", lang, question=question))
                await state.set_state(IntentOnboardingStates.voice_stage4)
                return
    except Exception as e:
        logger.warning(f"Follow-up check failed: {e}")

    # No follow-up needed
    await message.answer(t("voice_skip_followup", lang))
    await _go_to_city_step(message, state)


async def _transcribe_voice(message: Message) -> Optional[str]:
    """Download and transcribe voice message."""
    try:
        file_info = await bot.get_file(message.voice.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        transcript = await voice_service.transcribe(file_bytes.read())
        return transcript.strip() if transcript else None
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}", exc_info=True)
        return None


# ============================================================
# QUICK CHOICES MODE
# ============================================================

def _build_question_queue(intents: list) -> list:
    """Build dynamic question queue based on intents."""
    questions = []

    # Universal questions
    questions.append({"type": "text", "key": "bio", "prompt_key": "qc_about"})
    questions.append({"type": "text", "key": "looking_for", "prompt_key": "qc_looking_for"})

    # Networking questions
    if "networking" in intents:
        questions.append({"type": "text", "key": "profession", "prompt_key": "qc_profession"})
        questions.append({
            "type": "multi_select", "key": "skills", "prompt_key": "qc_skills",
            "options": [
                {"key": "tech", "label_key": "skill_tech"},
                {"key": "business", "label_key": "skill_business"},
                {"key": "marketing", "label_key": "skill_marketing"},
                {"key": "design", "label_key": "skill_design"},
                {"key": "finance", "label_key": "skill_finance"},
                {"key": "creative", "label_key": "skill_creative"},
                {"key": "operations", "label_key": "skill_operations"},
            ],
        })
        questions.append({"type": "text", "key": "can_help_with", "prompt_key": "qc_can_help"})

    # Friends questions
    if "friends" in intents:
        questions.append({
            "type": "multi_select", "key": "interests", "prompt_key": "qc_interests",
            "options": [
                {"key": "tech", "label_key": "interest_tech"},
                {"key": "sports", "label_key": "interest_sports"},
                {"key": "music", "label_key": "interest_music"},
                {"key": "travel", "label_key": "interest_travel"},
                {"key": "food", "label_key": "interest_food"},
                {"key": "art", "label_key": "interest_art"},
                {"key": "gaming", "label_key": "interest_gaming"},
                {"key": "books", "label_key": "interest_books"},
                {"key": "outdoors", "label_key": "interest_outdoors"},
                {"key": "fitness", "label_key": "interest_fitness"},
            ],
        })
        questions.append({
            "type": "buttons", "key": "personality_vibe", "prompt_key": "qc_vibe",
            "options": [
                {"key": "active", "label_key": "vibe_active"},
                {"key": "creative", "label_key": "vibe_creative"},
                {"key": "intellectual", "label_key": "vibe_intellectual"},
                {"key": "social", "label_key": "vibe_social"},
            ],
        })

    # Romance questions
    gender_asked = False
    if "romance" in intents:
        questions.append({
            "type": "buttons", "key": "gender", "prompt_key": "qc_gender",
            "options": [
                {"key": "male", "label_key": "gender_male"},
                {"key": "female", "label_key": "gender_female"},
                {"key": "nonbinary", "label_key": "gender_nonbinary"},
            ],
        })
        gender_asked = True
        questions.append({
            "type": "multi_select", "key": "looking_for_gender", "prompt_key": "qc_interested_in",
            "options": [
                {"key": "men", "label_key": "interested_men"},
                {"key": "women", "label_key": "interested_women"},
                {"key": "everyone", "label_key": "interested_everyone"},
            ],
        })
        questions.append({
            "type": "buttons", "key": "age_range", "prompt_key": "qc_age_range",
            "options": [
                {"key": "18-25", "label_key": "age_18_25"},
                {"key": "25-35", "label_key": "age_25_35"},
                {"key": "35-45", "label_key": "age_35_45"},
                {"key": "45+", "label_key": "age_45_plus"},
            ],
        })
        questions.append({
            "type": "multi_select", "key": "partner_values", "prompt_key": "qc_values",
            "options": [
                {"key": "humor", "label_key": "value_humor"},
                {"key": "ambition", "label_key": "value_ambition"},
                {"key": "kindness", "label_key": "value_kindness"},
                {"key": "intelligence", "label_key": "value_intelligence"},
                {"key": "adventurous", "label_key": "value_adventurous"},
                {"key": "family", "label_key": "value_family"},
            ],
        })

    # Hookup questions
    if "hookup" in intents:
        if not gender_asked:
            questions.append({
                "type": "buttons", "key": "gender", "prompt_key": "qc_gender",
                "options": [
                    {"key": "male", "label_key": "gender_male"},
                    {"key": "female", "label_key": "gender_female"},
                    {"key": "nonbinary", "label_key": "gender_nonbinary"},
                ],
            })
            questions.append({
                "type": "multi_select", "key": "looking_for_gender", "prompt_key": "qc_interested_in",
                "options": [
                    {"key": "men", "label_key": "interested_men"},
                    {"key": "women", "label_key": "interested_women"},
                    {"key": "everyone", "label_key": "interested_everyone"},
                ],
            })
        questions.append({
            "type": "buttons", "key": "hookup_preference", "prompt_key": "qc_hookup_vibe",
            "options": [
                {"key": "chill", "label_key": "hookup_chill"},
                {"key": "party", "label_key": "hookup_party"},
                {"key": "active", "label_key": "hookup_active"},
                {"key": "talk", "label_key": "hookup_talk"},
            ],
        })

    return questions


async def _ask_next_question(message_or_msg, state, edit=False):
    """Ask the next question in the queue."""
    data = await state.get_data()
    lang = data.get("language", "en")
    questions = data.get("question_queue", [])
    index = data.get("question_index", 0)

    if index >= len(questions):
        # All questions answered — go to city
        if hasattr(message_or_msg, "edit_text") and edit:
            await message_or_msg.edit_text(t("voice_skip_followup", lang))
        else:
            target = message_or_msg if isinstance(message_or_msg, Message) else message_or_msg
            await target.answer(t("voice_skip_followup", lang))
        # Build profile data from answers
        qc_answers = data.get("qc_answers", {})
        profile_data = data.get("profile_data", {})
        profile_data.update(qc_answers)
        await state.update_data(profile_data=profile_data)
        # Go to city using a plain Message
        if isinstance(message_or_msg, Message):
            await _go_to_city_step(message_or_msg, state)
        else:
            # It's an edited message, send a new one
            await _go_to_city_step_by_chat(message_or_msg.chat.id, state)
        return

    q = questions[index]
    prompt_text = t(q["prompt_key"], lang)
    await state.set_state(IntentOnboardingStates.answering_question)

    if q["type"] == "text":
        if edit and hasattr(message_or_msg, "edit_text"):
            await message_or_msg.edit_text(prompt_text)
        else:
            target = message_or_msg if isinstance(message_or_msg, Message) else message_or_msg
            await target.answer(prompt_text)
    elif q["type"] == "buttons":
        kb = get_question_buttons_keyboard(q["options"], lang)
        if edit and hasattr(message_or_msg, "edit_text"):
            await message_or_msg.edit_text(prompt_text, reply_markup=kb)
        else:
            target = message_or_msg if isinstance(message_or_msg, Message) else message_or_msg
            await target.answer(prompt_text, reply_markup=kb)
    elif q["type"] == "multi_select":
        selected = data.get(f"qcm_selected_{q['key']}", [])
        kb = get_question_multi_select_keyboard(q["options"], selected, lang)
        if edit and hasattr(message_or_msg, "edit_text"):
            await message_or_msg.edit_text(prompt_text, reply_markup=kb)
        else:
            target = message_or_msg if isinstance(message_or_msg, Message) else message_or_msg
            await target.answer(prompt_text, reply_markup=kb)


# Handle text answers for quick choices
@router.message(IntentOnboardingStates.answering_question, F.text)
async def handle_qc_text_answer(message: Message, state: FSMContext):
    """Handle text answer to a quick choice question."""
    if message.text and message.text.startswith("/"):
        return

    data = await state.get_data()
    questions = data.get("question_queue", [])
    index = data.get("question_index", 0)

    if index >= len(questions):
        return

    q = questions[index]
    if q["type"] != "text":
        return  # Expecting button press, not text

    # Save answer
    qc_answers = data.get("qc_answers", {})

    # Special handling for profession (split into profession + company)
    if q["key"] == "profession":
        text = message.text.strip()
        if " @ " in text or " at " in text.lower():
            parts = re.split(r'\s+@\s+|\s+at\s+', text, maxsplit=1, flags=re.IGNORECASE)
            qc_answers["profession"] = parts[0].strip()
            if len(parts) > 1:
                qc_answers["company"] = parts[1].strip()
        else:
            qc_answers["profession"] = text
    else:
        qc_answers[q["key"]] = message.text.strip()

    await state.update_data(qc_answers=qc_answers, question_index=index + 1)
    await _ask_next_question(message, state)


# Handle button selection for quick choices
@router.callback_query(IntentOnboardingStates.answering_question, F.data.startswith("qc_"))
async def handle_qc_button_answer(callback: CallbackQuery, state: FSMContext):
    """Handle single-select button answer."""
    data = await state.get_data()
    questions = data.get("question_queue", [])
    index = data.get("question_index", 0)

    if callback.data == "qc_skip":
        await state.update_data(question_index=index + 1)
        await _ask_next_question(callback.message, state, edit=True)
        await callback.answer()
        return

    if index >= len(questions):
        await callback.answer()
        return

    q = questions[index]
    value = callback.data.replace("qc_", "")

    qc_answers = data.get("qc_answers", {})
    qc_answers[q["key"]] = value
    await state.update_data(qc_answers=qc_answers, question_index=index + 1)

    await _ask_next_question(callback.message, state, edit=True)
    await callback.answer()


# Handle multi-select toggle
@router.callback_query(IntentOnboardingStates.answering_question, F.data.startswith("qcm_"))
async def handle_qc_multi_select(callback: CallbackQuery, state: FSMContext):
    """Handle multi-select toggle or done."""
    data = await state.get_data()
    lang = data.get("language", "en")
    questions = data.get("question_queue", [])
    index = data.get("question_index", 0)

    if callback.data == "qcm_done":
        # Save selected items as the answer
        if index < len(questions):
            q = questions[index]
            selected = data.get(f"qcm_selected_{q['key']}", [])
            qc_answers = data.get("qc_answers", {})
            qc_answers[q["key"]] = selected
            await state.update_data(qc_answers=qc_answers, question_index=index + 1)
            # Clean up selection state
            new_data = await state.get_data()
            # Move to next question
            await _ask_next_question(callback.message, state, edit=True)
        await callback.answer()
        return

    if index >= len(questions):
        await callback.answer()
        return

    q = questions[index]
    value = callback.data.replace("qcm_", "")
    selected_key = f"qcm_selected_{q['key']}"
    selected = data.get(selected_key, [])

    if value in selected:
        selected.remove(value)
    else:
        selected.append(value)

    await state.update_data(**{selected_key: selected})

    # Refresh keyboard
    kb = get_question_multi_select_keyboard(q["options"], selected, lang)
    prompt_text = t(q["prompt_key"], lang)
    await callback.message.edit_text(prompt_text, reply_markup=kb)
    await callback.answer()


# ============================================================
# SOCIAL MEDIA MODE
# ============================================================

@router.callback_query(IntentOnboardingStates.social_waiting_input, F.data.in_(["social_link", "social_screenshot"]))
async def handle_social_source_choice(callback: CallbackQuery, state: FSMContext):
    """User chose link or screenshot."""
    data = await state.get_data()
    lang = data.get("language", "en")

    source_type = "link" if callback.data == "social_link" else "screenshot"
    await state.update_data(social_source_type=source_type)

    if source_type == "link":
        await callback.message.edit_text(t("social_waiting_link", lang))
    else:
        await callback.message.edit_text(t("social_waiting_screenshot", lang))
    await callback.answer()


@router.message(IntentOnboardingStates.social_waiting_input, F.text)
async def handle_social_link(message: Message, state: FSMContext):
    """Handle social media link."""
    data = await state.get_data()
    lang = data.get("language", "en")

    url = message.text.strip()
    if not url.startswith("http"):
        await message.answer(t("social_waiting_link", lang))
        return

    processing_msg = await message.answer(t("social_processing", lang))

    try:
        # Fetch URL content using event parser pattern
        from infrastructure.ai.event_parser_service import EventParserService
        parser = EventParserService()
        content = await parser._fetch_url_content(url)

        if not content:
            try:
                await processing_msg.delete()
            except Exception:
                pass
            await message.answer(t("social_error", lang))
            return

        # Extract profile from content
        prompt = SOCIAL_LINK_EXTRACTION.format(url=url, content=content[:3000])
        raw = await ai_service.chat(prompt, max_tokens=800)
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        imported = json.loads(raw.strip())

        try:
            await processing_msg.delete()
        except Exception:
            pass

        profile_data = data.get("profile_data", {})
        for k, v in imported.items():
            if v and k != "platform" and not profile_data.get(k):
                profile_data[k] = v

        platform = imported.get("platform", "profile")
        await state.update_data(profile_data=profile_data, social_platform=platform)

        # Show extracted data
        summary = format_profile_summary(profile_data, lang)
        await message.answer(
            t("social_extracted", lang,
              platform=platform,
              bio=profile_data.get("bio", ""),
              interests=", ".join(profile_data.get("interests", [])),
              profession=profile_data.get("profession", "")),
        )

        # Ask follow-up questions
        await _social_ask_followup(message, state)

    except Exception as e:
        logger.error(f"Social link processing failed: {e}", exc_info=True)
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(t("social_error", lang))


@router.message(IntentOnboardingStates.social_waiting_input, F.photo)
async def handle_social_screenshot(message: Message, state: FSMContext):
    """Handle social media screenshot."""
    data = await state.get_data()
    lang = data.get("language", "en")

    processing_msg = await message.answer(t("social_processing", lang))

    try:
        # Get the largest photo
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        import base64
        img_data = base64.b64encode(file_bytes.read()).decode("utf-8")

        # Use GPT-4o vision to extract profile
        response = await ai_service.client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract profile information from this screenshot. Return JSON with: platform, display_name, bio, profession, interests (array), looking_for, city_current. Only include fields visible in the screenshot."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}},
                ],
            }],
        )

        raw = response.choices[0].message.content
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        imported = json.loads(raw.strip())

        try:
            await processing_msg.delete()
        except Exception:
            pass

        profile_data = data.get("profile_data", {})
        for k, v in imported.items():
            if v and k != "platform" and not profile_data.get(k):
                profile_data[k] = v

        platform = imported.get("platform", "screenshot")
        await state.update_data(profile_data=profile_data, social_platform=platform)

        summary = format_profile_summary(profile_data, lang)
        await message.answer(
            t("social_extracted", lang,
              platform=platform,
              bio=profile_data.get("bio", ""),
              interests=", ".join(profile_data.get("interests", [])),
              profession=profile_data.get("profession", "")),
        )

        await _social_ask_followup(message, state)

    except Exception as e:
        logger.error(f"Screenshot processing failed: {e}", exc_info=True)
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await message.answer(t("social_error", lang))


async def _social_ask_followup(message: Message, state: FSMContext):
    """Generate and ask follow-up questions after social import."""
    data = await state.get_data()
    lang = data.get("language", "en")
    intents = data.get("selected_intents", [])
    profile_data = data.get("profile_data", {})

    try:
        prompt = SOCIAL_GAP_ANALYSIS.format(
            intents=", ".join(intents),
            imported_data=json.dumps(profile_data, ensure_ascii=False),
        )
        raw = await ai_service.chat(prompt, max_tokens=400)
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        result = json.loads(raw.strip())

        questions = result.get("questions", [])
        if questions:
            q = questions[0]
            question_text = q.get(f"question_{lang}", q.get("question_en", ""))
            await state.update_data(
                social_followup_questions=questions,
                social_followup_index=0,
            )
            await message.answer(t("social_followup", lang, question=question_text))
            await state.set_state(IntentOnboardingStates.social_followup)
            return
    except Exception as e:
        logger.warning(f"Gap analysis failed: {e}")

    # No follow-up needed — go to city
    await _go_to_city_step(message, state)


@router.message(IntentOnboardingStates.social_followup, F.text)
async def handle_social_followup_text(message: Message, state: FSMContext):
    """Handle text response to social follow-up question."""
    if message.text and message.text.startswith("/"):
        return

    data = await state.get_data()
    lang = data.get("language", "en")
    profile_data = data.get("profile_data", {})
    questions = data.get("social_followup_questions", [])
    index = data.get("social_followup_index", 0)

    # Extract from the answer
    if index < len(questions):
        fills = questions[index].get("fills", [])
        for field in fills:
            if not profile_data.get(field):
                profile_data[field] = message.text.strip()

    await state.update_data(profile_data=profile_data, social_followup_index=index + 1)

    # Check if more follow-up questions
    if index + 1 < len(questions):
        q = questions[index + 1]
        question_text = q.get(f"question_{lang}", q.get("question_en", ""))
        await message.answer(t("social_followup", lang, question=question_text))
        return

    # All follow-ups done
    await _go_to_city_step(message, state)


@router.message(IntentOnboardingStates.social_followup, F.voice)
async def handle_social_followup_voice(message: Message, state: FSMContext):
    """Handle voice response to social follow-up."""
    data = await state.get_data()
    lang = data.get("language", "en")

    transcript = await _transcribe_voice(message)
    if transcript:
        message.text = transcript
        await handle_social_followup_text(message, state)
    else:
        await message.answer(t("error_generic", lang))


# ============================================================
# CITY STEP (all modes converge here)
# ============================================================

async def _go_to_city_step(message: Message, state: FSMContext):
    """Show city picker."""
    data = await state.get_data()
    lang = data.get("language", "en")
    profile_data = data.get("profile_data", {})

    # If city already known, skip
    if profile_data.get("city_current"):
        await _go_to_photo_step(message, state)
        return

    await message.answer(
        t("city_header", lang),
        reply_markup=get_intent_city_keyboard(lang),
    )
    await state.set_state(IntentOnboardingStates.choosing_city)


async def _go_to_city_step_by_chat(chat_id: int, state: FSMContext):
    """Show city picker via chat_id (when we don't have a Message)."""
    data = await state.get_data()
    lang = data.get("language", "en")
    profile_data = data.get("profile_data", {})

    if profile_data.get("city_current"):
        await _go_to_photo_step_by_chat(chat_id, state)
        return

    await bot.send_message(
        chat_id,
        t("city_header", lang),
        reply_markup=get_intent_city_keyboard(lang),
    )
    await state.set_state(IntentOnboardingStates.choosing_city)


@router.callback_query(IntentOnboardingStates.choosing_city, F.data.startswith("icity_"))
async def handle_city_select(callback: CallbackQuery, state: FSMContext):
    """Handle city selection."""
    data = await state.get_data()
    lang = data.get("language", "en")

    city_key = callback.data.replace("icity_", "")

    if city_key == "other":
        await callback.message.edit_text(t("city_type", lang))
        await state.set_state(IntentOnboardingStates.typing_city)
        await callback.answer()
        return

    from adapters.telegram.keyboards.inline import SPHERE_CITIES
    city_name = SPHERE_CITIES.get(city_key, {}).get("en", city_key)

    profile_data = data.get("profile_data", {})
    profile_data["city_current"] = city_name
    await state.update_data(profile_data=profile_data)

    await callback.answer()
    await _go_to_photo_step_by_chat(callback.message.chat.id, state)


# Also handle iconfirm_yes/edit at this state (from agent mode)
@router.callback_query(IntentOnboardingStates.choosing_city, F.data == "iconfirm_yes")
async def handle_agent_confirm_at_city(callback: CallbackQuery, state: FSMContext):
    """Agent mode: user confirmed profile, now show city picker."""
    data = await state.get_data()
    lang = data.get("language", "en")
    profile_data = data.get("profile_data", {})

    if profile_data.get("city_current"):
        await callback.answer()
        await _go_to_photo_step_by_chat(callback.message.chat.id, state)
    else:
        await callback.message.edit_text(
            t("city_header", lang),
            reply_markup=get_intent_city_keyboard(lang),
        )
        await callback.answer()


@router.callback_query(IntentOnboardingStates.choosing_city, F.data == "iconfirm_edit")
async def handle_agent_edit_at_city(callback: CallbackQuery, state: FSMContext):
    """Agent mode: user wants to edit. Go back to agent chatting."""
    data = await state.get_data()
    lang = data.get("language", "en")

    await callback.message.edit_text(t("agent_continue", lang))
    await state.set_state(IntentOnboardingStates.agent_chatting)
    await callback.answer()


@router.message(IntentOnboardingStates.typing_city, F.text)
async def handle_city_typed(message: Message, state: FSMContext):
    """Handle typed city name."""
    if message.text and message.text.startswith("/"):
        return

    data = await state.get_data()
    profile_data = data.get("profile_data", {})
    profile_data["city_current"] = message.text.strip()
    await state.update_data(profile_data=profile_data)

    await _go_to_photo_step(message, state)


# ============================================================
# PHOTO STEP
# ============================================================

async def _go_to_photo_step(message: Message, state: FSMContext):
    """Ask for photo."""
    data = await state.get_data()
    lang = data.get("language", "en")

    await message.answer(
        t("photo_header", lang),
        reply_markup=get_photo_skip_keyboard(lang),
    )
    await state.set_state(IntentOnboardingStates.waiting_photo)


async def _go_to_photo_step_by_chat(chat_id: int, state: FSMContext):
    """Ask for photo via chat_id."""
    data = await state.get_data()
    lang = data.get("language", "en")

    await bot.send_message(
        chat_id,
        t("photo_header", lang),
        reply_markup=get_photo_skip_keyboard(lang),
    )
    await state.set_state(IntentOnboardingStates.waiting_photo)


@router.message(IntentOnboardingStates.waiting_photo, F.photo)
async def handle_photo_upload(message: Message, state: FSMContext):
    """Handle photo upload."""
    data = await state.get_data()
    lang = data.get("language", "en")

    photo = message.photo[-1]
    profile_data = data.get("profile_data", {})
    profile_data["photo_file_id"] = photo.file_id
    await state.update_data(profile_data=profile_data)

    await message.answer(t("photo_saved", lang))
    await _go_to_confirm_step(message, state)


@router.callback_query(IntentOnboardingStates.waiting_photo, F.data == "iphoto_skip")
async def handle_photo_skip(callback: CallbackQuery, state: FSMContext):
    """Skip photo."""
    await callback.answer()
    await _go_to_confirm_step_by_chat(callback.message.chat.id, state)


# ============================================================
# CONFIRM & SAVE
# ============================================================

async def _go_to_confirm_step(message: Message, state: FSMContext):
    """Show profile summary for confirmation."""
    data = await state.get_data()
    lang = data.get("language", "en")
    profile_data = data.get("profile_data", {})

    summary = format_profile_summary(profile_data, lang)
    await message.answer(
        f"{t('confirm_header', lang)}\n\n{summary}",
        reply_markup=get_intent_confirm_keyboard(lang),
    )
    await state.set_state(IntentOnboardingStates.confirming_profile)


async def _go_to_confirm_step_by_chat(chat_id: int, state: FSMContext):
    """Show profile summary via chat_id."""
    data = await state.get_data()
    lang = data.get("language", "en")
    profile_data = data.get("profile_data", {})

    summary = format_profile_summary(profile_data, lang)
    await bot.send_message(
        chat_id,
        f"{t('confirm_header', lang)}\n\n{summary}",
        reply_markup=get_intent_confirm_keyboard(lang),
    )
    await state.set_state(IntentOnboardingStates.confirming_profile)


@router.callback_query(IntentOnboardingStates.confirming_profile, F.data == "iconfirm_yes")
async def handle_confirm_yes(callback: CallbackQuery, state: FSMContext):
    """Save profile and finish onboarding."""
    data = await state.get_data()
    lang = data.get("language", "en")
    profile_data = data.get("profile_data", {})
    intents = data.get("selected_intents", [])
    event_code = data.get("pending_event_code")

    await callback.message.edit_text(t("confirm_saved", lang))

    # Build update dict
    update_data = UserUpdate(
        display_name=profile_data.get("display_name") or data.get("display_name"),
        bio=profile_data.get("bio"),
        profession=profile_data.get("profession"),
        company=profile_data.get("company"),
        skills=profile_data.get("skills"),
        interests=profile_data.get("interests"),
        looking_for=profile_data.get("looking_for"),
        can_help_with=profile_data.get("can_help_with"),
        ideal_connection=profile_data.get("ideal_connection"),
        city_current=profile_data.get("city_current"),
        connection_intents=intents,
        gender=profile_data.get("gender"),
        looking_for_gender=profile_data.get("looking_for_gender"),
        age_range=profile_data.get("age_range"),
        partner_values=profile_data.get("partner_values"),
        personality_vibe=profile_data.get("personality_vibe"),
        hookup_preference=profile_data.get("hookup_preference"),
        language=lang,
        onboarding_completed=True,
    )

    # Save photo if uploaded
    photo_file_id = profile_data.get("photo_file_id")
    if photo_file_id:
        update_data.photo_url = photo_file_id

    # Update user
    user = await user_service.update_user(
        platform=MessagePlatform.TELEGRAM,
        platform_user_id=str(callback.from_user.id),
        **update_data.model_dump(exclude_unset=True, exclude_none=True),
    )

    # Join event if pending
    if event_code:
        try:
            from adapters.telegram.loader import event_service
            event = await event_service.get_event_by_code(event_code)
            if event and user:
                await event_service.join_event(user.id, event.id)
                await user_service.update_user(
                    platform=MessagePlatform.TELEGRAM,
                    platform_user_id=str(callback.from_user.id),
                    current_event_id=str(event.id),
                )
        except Exception as e:
            logger.warning(f"Event join failed: {e}")

    # Generate embeddings in background
    if user:
        async def _gen_embeddings():
            try:
                result = await embedding_service.generate_embeddings(user)
                if result:
                    await user_repo.update_embeddings(user.id, *result)
                    logger.info(f"Embeddings generated for {user.id}")
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}", exc_info=True)

        asyncio.create_task(_gen_embeddings())

    # Clear state
    await state.clear()

    # Show tip + menu
    from adapters.telegram.keyboards.inline import get_main_menu_keyboard
    await bot.send_message(
        callback.message.chat.id,
        t("tip_enrich", lang),
    )
    menu_text = "What would you like to do?" if lang == "en" else "\u0427\u0442\u043e \u0434\u0435\u043b\u0430\u0435\u043c?"
    await bot.send_message(
        callback.message.chat.id,
        menu_text,
        reply_markup=get_main_menu_keyboard(lang),
    )

    await callback.answer()


@router.callback_query(IntentOnboardingStates.confirming_profile, F.data == "iconfirm_edit")
async def handle_confirm_edit(callback: CallbackQuery, state: FSMContext):
    """Go back to agent mode for editing."""
    data = await state.get_data()
    lang = data.get("language", "en")

    # Re-enter agent mode for edits
    await callback.message.edit_text(t("agent_continue", lang))
    await state.set_state(IntentOnboardingStates.agent_chatting)
    await callback.answer()
