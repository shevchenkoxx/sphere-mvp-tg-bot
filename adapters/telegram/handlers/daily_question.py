"""
Daily question handler.
Sends daily questions to users, handles answers (text + voice),
supports follow-up LLM conversation, and extracts profile enrichment data.
"""

import asyncio
import json
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from locales import t
from core.domain.models import MessagePlatform, UserUpdate
from questions import get_daily_question, get_question_text
from adapters.telegram.loader import (
    user_service, bot, voice_service, ai_service, embedding_service, user_repo,
)
from adapters.telegram.states.onboarding import DailyQuestionStates
from adapters.telegram.keyboards.inline import get_daily_question_keyboard
from core.utils.language import detect_lang

logger = logging.getLogger(__name__)

router = Router()

MAX_CHAT_MESSAGES = 10  # Max follow-up messages before ending conversation

# Extraction prompt for daily question answers
DAILY_EXTRACTION_PROMPT = """Analyze this user's answer to a daily question and extract profile-relevant information.

Question: {question}
Answer: {answer}

Current user profile:
- Bio: {bio}
- Interests: {interests}
- Goals: {goals}
- Looking for: {looking_for}
- Can help with: {can_help_with}
- Skills: {skills}

Extract ONLY NEW information not already in the profile. Return JSON:
{{
  "bio_addition": "new bio info to append, or null",
  "new_interests": ["interest1", "interest2"],
  "new_goals": ["goal1"],
  "looking_for_addition": "new looking_for info, or null",
  "can_help_with_addition": "new can_help_with info, or null",
  "new_skills": ["skill1"],
  "personality_vibe": "active/creative/intellectual/social or null",
  "values_signals": ["value1", "value2"],
  "reaction": "A brief, warm 1-sentence reaction to their answer"
}}

Respond with valid JSON only."""

# System prompt for follow-up conversation
DAILY_CHAT_SYSTEM = """You're having a friendly follow-up conversation about a topic the user brought up.
Be warm, curious, ask 1 follow-up question per message. Keep it concise (1-3 sentences).
Don't be a survey — be genuinely interested. Match the user's language and energy.

Context: The user answered a daily question: "{question}"
Their answer: "{answer}"
Their profile: {profile_summary}

In your responses, naturally explore related topics that help you understand them better.
Never mention that you're extracting data or building a profile."""

# Extraction prompt for chat messages
CHAT_EXTRACTION_PROMPT = """Extract any profile-relevant information from this conversation message.

Message: {message}
Conversation context: {context}

Return JSON with ONLY new insights (null for nothing new):
{{
  "new_interests": [],
  "new_goals": [],
  "new_skills": [],
  "looking_for_addition": null,
  "can_help_with_addition": null,
  "values_signals": [],
  "personality_vibe": null
}}

Respond with valid JSON only."""


# ============================================================
# DAILY QUESTION DELIVERY (called by scheduler)
# ============================================================

async def send_daily_question_to_user(user_id, platform_user_id: str, lang: str = "en"):
    """Send a daily question to a specific user. Called by scheduler."""
    try:
        # Get user from DB
        user = await user_repo.get_by_platform_id(
            MessagePlatform.TELEGRAM, platform_user_id
        )
        if not user or not user.onboarding_completed:
            return

        # Get already-asked question IDs
        asked_ids = await _get_asked_question_ids(str(user.id))

        # Select question
        question = get_daily_question(
            user_intents=user.connection_intents or ["friends"],
            asked_question_ids=asked_ids,
            user_profile={
                "bio": user.bio,
                "looking_for": user.looking_for,
                "can_help_with": user.can_help_with,
                "interests": user.interests,
                "goals": user.goals,
                "ideal_connection": user.ideal_connection,
                "skills": user.skills,
                "personality_vibe": user.personality_vibe,
                "partner_values": user.partner_values,
            },
            question_count=len(asked_ids),
        )

        if not question:
            logger.info(f"No daily question available for user {user.id}")
            return

        # Send question
        q_text = get_question_text(question, lang)
        text = f"{t('daily_header', lang)}\n{q_text}"
        keyboard = get_daily_question_keyboard(question["id"], lang)

        await bot.send_message(
            chat_id=int(platform_user_id),
            text=text,
            reply_markup=keyboard,
        )

        # Record that we sent this question
        await _save_question_sent(str(user.id), question["id"])
        logger.info(f"Sent daily question '{question['id']}' to user {user.id}")

    except Exception as e:
        logger.error(f"Error sending daily question to {platform_user_id}: {e}", exc_info=True)


async def send_daily_questions_batch():
    """Send daily questions to all active users. Called by scheduler."""
    from infrastructure.database.supabase_client import supabase, run_sync

    @run_sync
    def _get_active_users():
        response = supabase.table("users").select(
            "id, platform_user_id, language, connection_intents"
        ).eq("onboarding_completed", True).eq("is_active", True).execute()
        return response.data or []

    users = await _get_active_users()
    logger.info(f"Sending daily questions to {len(users)} active users")

    for u in users:
        lang = u.get("language", "en")
        await send_daily_question_to_user(
            u["id"], u["platform_user_id"], lang
        )
        # Small delay between sends to avoid rate limits
        await asyncio.sleep(0.5)


# ============================================================
# HANDLERS: Answer daily question
# ============================================================

@router.callback_query(F.data.startswith("daily_skip_"))
async def handle_daily_skip(callback: CallbackQuery, state: FSMContext):
    """User skipped the daily question."""
    await callback.answer()
    question_id = callback.data.replace("daily_skip_", "")
    # Just acknowledge, no extraction needed
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("daily_voice_"))
async def handle_daily_voice_prompt(callback: CallbackQuery, state: FSMContext):
    """User wants to answer with voice."""
    await callback.answer()
    question_id = callback.data.replace("daily_voice_", "")
    lang = detect_lang(callback.from_user)

    # Store question context in state
    await state.set_state(DailyQuestionStates.answering)
    await state.update_data(
        daily_question_id=question_id,
        daily_lang=lang,
        daily_input_mode="voice",
    )

    await callback.message.answer(t("daily_voice", lang))


@router.callback_query(F.data.startswith("daily_answer_"))
async def handle_daily_answer_start(callback: CallbackQuery, state: FSMContext):
    """User tapped to answer the daily question (text mode)."""
    await callback.answer()
    question_id = callback.data.replace("daily_answer_", "")
    lang = detect_lang(callback.from_user)

    # Store question context
    await state.set_state(DailyQuestionStates.answering)
    await state.update_data(
        daily_question_id=question_id,
        daily_lang=lang,
        daily_input_mode="text",
    )

    # Remove keyboard from question message
    await callback.message.edit_reply_markup(reply_markup=None)


@router.message(DailyQuestionStates.answering, F.voice)
async def handle_daily_voice_answer(message: Message, state: FSMContext):
    """Process voice answer to daily question."""
    data = await state.get_data()
    lang = data.get("daily_lang", "en")
    question_id = data.get("daily_question_id", "")

    await message.answer(t("voice_processing", lang))

    try:
        # Transcribe voice
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcript = await voice_service.download_and_transcribe(file_url)

        if not transcript:
            await message.answer(t("error_generic", lang))
            await state.clear()
            return

        # Process the answer
        await _process_daily_answer(message, state, transcript, question_id, lang)

    except Exception as e:
        logger.error(f"Error processing daily voice: {e}", exc_info=True)
        await message.answer(t("error_generic", lang))
        await state.clear()


@router.message(DailyQuestionStates.answering, F.text)
async def handle_daily_text_answer(message: Message, state: FSMContext):
    """Process text answer to daily question."""
    data = await state.get_data()
    lang = data.get("daily_lang", "en")
    question_id = data.get("daily_question_id", "")

    await _process_daily_answer(message, state, message.text, question_id, lang)


async def _process_daily_answer(
    message: Message, state: FSMContext,
    answer_text: str, question_id: str, lang: str,
):
    """Process daily question answer: extract data + offer chat continuation."""
    try:
        # Get user
        user = await user_repo.get_by_platform_id(
            MessagePlatform.TELEGRAM, str(message.from_user.id)
        )
        if not user:
            await state.clear()
            return

        # Find question text for context
        from questions.bank import QUESTION_BANK
        q_text = ""
        for q in QUESTION_BANK:
            if q["id"] == question_id:
                q_text = get_question_text(q, lang)
                break

        # Extract profile data from answer
        extraction_prompt = DAILY_EXTRACTION_PROMPT.format(
            question=q_text,
            answer=answer_text,
            bio=user.bio or "",
            interests=", ".join(user.interests) if user.interests else "",
            goals=", ".join(user.goals) if user.goals else "",
            looking_for=user.looking_for or "",
            can_help_with=user.can_help_with or "",
            skills=", ".join(user.skills) if user.skills else "",
        )

        raw = await ai_service.chat(extraction_prompt)
        extracted = _safe_parse_json(raw)

        # Save answer to user_questions table
        await _save_question_answer(str(user.id), question_id, answer_text, extracted)

        # Apply extracted data to profile (fire-and-forget)
        if extracted:
            asyncio.create_task(
                _merge_extracted_data(user, extracted)
            )

        # Show reaction + offer to continue chatting
        reaction = extracted.get("reaction", "") if extracted else ""
        response_text = t("daily_reaction", lang, reaction=reaction)
        await message.answer(response_text)

        # Transition to chatting state
        await state.set_state(DailyQuestionStates.chatting)
        await state.update_data(
            daily_question_id=question_id,
            daily_question_text=q_text,
            daily_answer=answer_text,
            daily_chat_count=0,
            daily_chat_history=[
                {"role": "user", "content": answer_text},
            ],
            daily_lang=lang,
        )

    except Exception as e:
        logger.error(f"Error processing daily answer: {e}", exc_info=True)
        await message.answer(t("error_generic", lang))
        await state.clear()


# ============================================================
# HANDLERS: Follow-up chat conversation
# ============================================================

@router.message(DailyQuestionStates.chatting, F.text)
async def handle_daily_chat(message: Message, state: FSMContext):
    """Handle follow-up conversation after daily question answer."""
    data = await state.get_data()
    lang = data.get("daily_lang", "en")
    chat_count = data.get("daily_chat_count", 0)
    history = data.get("daily_chat_history", [])
    q_text = data.get("daily_question_text", "")
    answer = data.get("daily_answer", "")

    # Check if conversation should end
    if chat_count >= MAX_CHAT_MESSAGES:
        await _end_daily_chat(message, state, lang)
        return

    # Check for goodbye signals
    bye_signals = {"bye", "пока", "хватит", "стоп", "stop", "done", "всё", "ладно"}
    if message.text.lower().strip() in bye_signals:
        await _end_daily_chat(message, state, lang)
        return

    # Add user message to history
    history.append({"role": "user", "content": message.text})

    try:
        # Get user for profile context
        user = await user_repo.get_by_platform_id(
            MessagePlatform.TELEGRAM, str(message.from_user.id)
        )
        profile_summary = ""
        if user:
            profile_summary = f"Bio: {user.bio or 'N/A'}, Interests: {', '.join(user.interests) if user.interests else 'N/A'}"

        # Generate LLM response
        system_prompt = DAILY_CHAT_SYSTEM.format(
            question=q_text,
            answer=answer,
            profile_summary=profile_summary,
        )

        messages = [{"role": "system", "content": system_prompt}] + history

        response = await ai_service.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=200,
            temperature=0.8,
        )
        reply = response.choices[0].message.content.strip()

        # Add assistant response to history
        history.append({"role": "assistant", "content": reply})

        # Fire-and-forget: extract data from user message
        if user:
            asyncio.create_task(
                _extract_from_chat_message(user, message.text, history)
            )

        # Update state
        await state.update_data(
            daily_chat_count=chat_count + 1,
            daily_chat_history=history,
        )

        await message.answer(reply)

    except Exception as e:
        logger.error(f"Error in daily chat: {e}", exc_info=True)
        await _end_daily_chat(message, state, lang)


@router.message(DailyQuestionStates.chatting, F.voice)
async def handle_daily_chat_voice(message: Message, state: FSMContext):
    """Handle voice messages in follow-up chat."""
    data = await state.get_data()
    lang = data.get("daily_lang", "en")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcript = await voice_service.download_and_transcribe(file_url)

        if transcript:
            # Fake a text message processing with the transcript
            message.text = transcript
            await handle_daily_chat(message, state)
        else:
            await message.answer(t("error_generic", lang))
    except Exception as e:
        logger.error(f"Error transcribing daily chat voice: {e}", exc_info=True)
        await message.answer(t("error_generic", lang))


async def _end_daily_chat(message: Message, state: FSMContext, lang: str):
    """End the daily chat conversation and finalize profile updates."""
    try:
        user = await user_repo.get_by_platform_id(
            MessagePlatform.TELEGRAM, str(message.from_user.id)
        )
        if user:
            # Regenerate embeddings with updated profile
            asyncio.create_task(_regenerate_embeddings(user))

        await message.answer(t("daily_end", lang))
    except Exception as e:
        logger.error(f"Error ending daily chat: {e}", exc_info=True)
    finally:
        await state.clear()


# ============================================================
# DATA HELPERS
# ============================================================

async def _merge_extracted_data(user, extracted: dict):
    """Merge extracted data from daily question answer into user profile."""
    try:
        update = UserUpdate()
        changed = False

        # Merge interests
        new_interests = extracted.get("new_interests", [])
        if new_interests:
            current = set(user.interests or [])
            added = [i for i in new_interests if i.lower() not in {x.lower() for x in current}]
            if added:
                update.interests = list(current) + added
                changed = True

        # Merge goals
        new_goals = extracted.get("new_goals", [])
        if new_goals:
            current = set(user.goals or [])
            added = [g for g in new_goals if g.lower() not in {x.lower() for x in current}]
            if added:
                update.goals = list(current) + added
                changed = True

        # Merge skills
        new_skills = extracted.get("new_skills", [])
        if new_skills:
            current = set(user.skills or [])
            added = [s for s in new_skills if s.lower() not in {x.lower() for x in current}]
            if added:
                update.skills = list(current) + added
                changed = True

        # Append to looking_for
        lf_add = extracted.get("looking_for_addition")
        if lf_add:
            current = user.looking_for or ""
            if lf_add.lower() not in current.lower():
                update.looking_for = f"{current}. {lf_add}" if current else lf_add
                changed = True

        # Append to can_help_with
        ch_add = extracted.get("can_help_with_addition")
        if ch_add:
            current = user.can_help_with or ""
            if ch_add.lower() not in current.lower():
                update.can_help_with = f"{current}. {ch_add}" if current else ch_add
                changed = True

        # Set personality_vibe if not set
        vibe = extracted.get("personality_vibe")
        if vibe and not user.personality_vibe:
            update.personality_vibe = vibe
            changed = True

        if changed:
            await user_repo.update(user.id, update)
            logger.info(f"Merged daily question data for user {user.id}")

    except Exception as e:
        logger.error(f"Error merging extracted data: {e}", exc_info=True)


async def _extract_from_chat_message(user, message_text: str, history: list):
    """Extract profile data from a chat message (fire-and-forget)."""
    try:
        # Build conversation context (last 4 messages)
        context = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Agent'}: {m['content']}"
            for m in history[-4:]
        )

        prompt = CHAT_EXTRACTION_PROMPT.format(
            message=message_text,
            context=context,
        )

        raw = await ai_service.chat(prompt)
        extracted = _safe_parse_json(raw)

        if extracted:
            await _merge_extracted_data(user, extracted)

    except Exception as e:
        logger.error(f"Error extracting from chat message: {e}", exc_info=True)


async def _regenerate_embeddings(user):
    """Regenerate user embeddings after profile enrichment."""
    try:
        # Re-fetch user to get latest data
        fresh_user = await user_repo.get_by_id(user.id)
        if not fresh_user:
            return

        result = await embedding_service.generate_embeddings(fresh_user)
        if result:
            await user_repo.update_embeddings(fresh_user.id, *result)
            logger.info(f"Regenerated embeddings for user {fresh_user.id}")
    except Exception as e:
        logger.error(f"Error regenerating embeddings: {e}", exc_info=True)


# ============================================================
# DB HELPERS (user_questions table)
# ============================================================

async def _get_asked_question_ids(user_id: str) -> list:
    """Get IDs of questions already asked to this user."""
    from infrastructure.database.supabase_client import supabase, run_sync

    @run_sync
    def _query():
        response = supabase.table("user_questions").select(
            "question_id"
        ).eq("user_id", user_id).execute()
        return [r["question_id"] for r in (response.data or [])]

    return await _query()


async def _save_question_sent(user_id: str, question_id: str):
    """Record that a question was sent to a user."""
    from infrastructure.database.supabase_client import supabase, run_sync

    @run_sync
    def _insert():
        supabase.table("user_questions").insert({
            "user_id": user_id,
            "question_id": question_id,
        }).execute()

    try:
        await _insert()
    except Exception as e:
        logger.error(f"Error saving question sent: {e}", exc_info=True)


async def _save_question_answer(
    user_id: str, question_id: str, answer_text: str, extracted_data: dict
):
    """Update user_questions record with the user's answer."""
    from infrastructure.database.supabase_client import supabase, run_sync

    @run_sync
    def _update():
        supabase.table("user_questions").update({
            "answer_text": answer_text,
            "extracted_data": extracted_data or {},
        }).eq("user_id", user_id).eq("question_id", question_id).execute()

    try:
        await _update()
    except Exception as e:
        logger.error(f"Error saving question answer: {e}", exc_info=True)


def _safe_parse_json(raw: str) -> Optional[dict]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not raw:
        return None
    try:
        # Strip markdown code blocks
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"Failed to parse JSON from daily question extraction: {raw[:200]}")
        return None
