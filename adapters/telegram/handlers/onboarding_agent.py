"""
AI Agent Onboarding Handler — single LLM-driven conversation.

Replaces the fixed FSM onboarding with an adaptive AI orchestrator.
Two FSM states:
  - AgentOnboarding.in_conversation — main loop (text/voice/photo)
  - AgentOnboarding.confirming_profile — user reviews profile preview

The orchestrator decides what to ask, when to extract, and when to show
the profile preview — all through OpenAI function calling.
"""

import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from adapters.telegram.keyboards import get_main_menu_keyboard
from adapters.telegram.keyboards.inline import get_agent_confirm_keyboard
from adapters.telegram.loader import (
    bot,
    embedding_service,
    event_service,
    matching_service,
    orchestrator_service,
    user_service,
    voice_service,
)
from adapters.telegram.states.onboarding import AgentOnboarding
from config.features import Features
from core.domain.models import MessagePlatform
from core.prompts.audio_onboarding import WHISPER_PROMPT_EN, WHISPER_PROMPT_RU
from core.utils.language import detect_lang
from infrastructure.ai.orchestrator_models import OnboardingAgentState, ProfileChecklist
from infrastructure.database.user_repository import SupabaseUserRepository

logger = logging.getLogger(__name__)

router = Router(name="onboarding_agent")


# ------------------------------------------------------------------
# Helpers (reused from onboarding_audio)
# ------------------------------------------------------------------

def _whisper_prompt(lang: str) -> str:
    return WHISPER_PROMPT_RU if lang == "ru" else WHISPER_PROMPT_EN


async def _correct_transcription(text: str) -> str:
    """Quick LLM pass to fix Whisper transcription errors."""
    from openai import AsyncOpenAI
    from config.settings import settings
    from core.prompts.audio_onboarding import TRANSCRIPT_CORRECTION_PROMPT

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=15.0)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": TRANSCRIPT_CORRECTION_PROMPT.format(transcription=text)}],
            max_tokens=len(text) + 200,
            temperature=0.1,
        )
        corrected = response.choices[0].message.content.strip()
        if corrected and len(corrected) > 10:
            return corrected
    except Exception as e:
        logger.warning(f"Transcript correction failed, using raw: {e}")
    return text


def _on_background_task_done(task: asyncio.Task, user_id: str = "unknown"):
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(f"Background task failed for user {user_id}: {exc}", exc_info=exc)


async def _handle_command_in_fsm(message: Message, state: FSMContext) -> bool:
    """If user sends a /command during FSM, clear state and handle it."""
    if not message.text or not message.text.startswith("/"):
        return False

    await state.clear()
    cmd = message.text.split()[0].lower()
    if cmd in ("/start", "/start@spheresocial_bot"):
        from adapters.telegram.handlers.start import start_command
        await start_command(message, state)
    elif cmd in ("/menu", "/menu@spheresocial_bot"):
        from adapters.telegram.handlers.start import menu_command
        await menu_command(message)
    elif cmd in ("/reset", "/reset@spheresocial_bot"):
        from adapters.telegram.handlers.start import reset_command
        await reset_command(message, state)
    else:
        await message.answer("Onboarding cancelled. Send the command again.")
    return True


# ------------------------------------------------------------------
# Entry point (called from start.py)
# ------------------------------------------------------------------

async def start_agent_onboarding(
    message: Message,
    state: FSMContext,
    event_name: str = None,
    event_code: str = None,
    lang: str = None,
):
    """Start the AI agent onboarding conversation."""
    if lang is None:
        lang = detect_lang(message)

    first_name = message.from_user.first_name or ""

    # Initialise agent state
    agent_state = OnboardingAgentState(
        event_code=event_code,
        event_name=event_name,
        lang=lang,
        first_name=first_name,
    )

    # Set display_name from Telegram
    cl = agent_state.get_checklist()
    cl.display_name = first_name
    agent_state.set_checklist(cl)

    # Store in FSM
    await state.update_data(
        **agent_state.to_dict(),
        pending_event=event_code,
        language=lang,
        user_first_name=first_name,
    )

    # Opening message from the agent
    response = await orchestrator_service.process_turn(
        agent_state,
        user_message=f"[System] User {first_name} just started onboarding"
        + (f" at event '{event_name}'" if event_name else "")
        + f". Greet them warmly and ask them to introduce themselves.",
        message_type="text",
    )

    # Save updated state
    await state.update_data(**agent_state.to_dict())
    await state.set_state(AgentOnboarding.in_conversation)

    await message.answer(response.text)


# ------------------------------------------------------------------
# In-conversation handlers
# ------------------------------------------------------------------

@router.message(AgentOnboarding.in_conversation, F.text)
async def handle_text(message: Message, state: FSMContext):
    """Handle text messages during agent onboarding."""
    if await _handle_command_in_fsm(message, state):
        return

    data = await state.get_data()
    agent_state = OnboardingAgentState.from_fsm_data(data)

    response = await orchestrator_service.process_turn(
        agent_state,
        user_message=message.text,
        message_type="text",
    )

    await state.update_data(**agent_state.to_dict())

    if response.is_complete:
        await _do_complete_onboarding(message, state, agent_state)
        return

    if response.show_profile:
        await _show_profile_preview(message, state, agent_state)
        return

    if response.text:
        await message.answer(response.text)


@router.message(AgentOnboarding.in_conversation, F.voice)
async def handle_voice(message: Message, state: FSMContext):
    """Handle voice messages — transcribe then feed to orchestrator."""
    data = await state.get_data()
    agent_state = OnboardingAgentState.from_fsm_data(data)
    lang = agent_state.lang

    if message.voice.duration > Features.MAX_VOICE_DURATION:
        max_dur = Features.MAX_VOICE_DURATION
        text = f"Voice too long (max {max_dur}s). Please try shorter!" if lang == "en" else f"Слишком длинное (макс {max_dur} сек). Покороче!"
        await message.answer(text)
        return

    status = await message.answer("🎤 Transcribing..." if lang == "en" else "🎤 Расшифровываю...")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

        transcription = await voice_service.download_and_transcribe(
            file_url, language=lang, prompt=_whisper_prompt(lang)
        )

        if not transcription or len(transcription) < 10:
            await status.edit_text(
                "Couldn't hear that clearly. Please try again or type." if lang == "en"
                else "Не расслышал. Попробуй ещё раз или напиши текстом."
            )
            return

        transcription = await _correct_transcription(transcription)

        try:
            await status.edit_text("✨ Processing..." if lang == "en" else "✨ Обрабатываю...")
        except Exception:
            pass

        response = await orchestrator_service.process_turn(
            agent_state,
            user_message=transcription,
            message_type="voice",
        )

        await state.update_data(**agent_state.to_dict())

        try:
            await status.delete()
        except Exception:
            pass

        if response.is_complete:
            await _do_complete_onboarding(message, state, agent_state)
            return

        if response.show_profile:
            await _show_profile_preview(message, state, agent_state)
            return

        if response.text:
            await message.answer(response.text)

    except Exception as e:
        logger.error(f"Voice processing error in agent: {e}", exc_info=True)
        try:
            await status.edit_text(
                "Something went wrong. Please try again or type." if lang == "en"
                else "Что-то пошло не так. Попробуй ещё раз или напиши."
            )
        except Exception:
            pass


@router.message(AgentOnboarding.in_conversation, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    """Handle photo during onboarding — save it and continue."""
    data = await state.get_data()
    agent_state = OnboardingAgentState.from_fsm_data(data)
    lang = agent_state.lang
    user_id = str(message.from_user.id)
    photo = message.photo[-1]

    try:
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            user_id,
            photo_url=photo.file_id,
        )
        cl = agent_state.get_checklist()
        cl.photo_url = photo.file_id
        agent_state.set_checklist(cl)
        await state.update_data(**agent_state.to_dict())

        text = "📸 Photo saved!" if lang == "en" else "📸 Фото сохранено!"
        await message.answer(text)
    except Exception as e:
        logger.error(f"Failed to save photo during agent onboarding: {e}")


# ------------------------------------------------------------------
# Profile confirmation
# ------------------------------------------------------------------

async def _show_profile_preview(
    message: Message,
    state: FSMContext,
    agent_state: OnboardingAgentState,
):
    """Show the profile preview with confirm/edit buttons."""
    cl = agent_state.get_checklist()
    lang = agent_state.lang

    header = "✨ Here's your profile:\n\n" if lang == "en" else "✨ Вот твой профиль:\n\n"
    footer = (
        "\n\nLooks good? Tap Confirm to save, or Edit to change something."
        if lang == "en"
        else "\n\nВсё верно? Нажми Подтвердить или Изменить."
    )

    text = header + cl.profile_summary_text() + footer

    sent = await message.answer(text, reply_markup=get_agent_confirm_keyboard(lang))
    await state.update_data(profile_msg_id=sent.message_id)
    await state.set_state(AgentOnboarding.confirming_profile)


@router.callback_query(AgentOnboarding.confirming_profile, F.data == "agent_confirm")
async def confirm_profile(callback: CallbackQuery, state: FSMContext):
    """User confirmed the profile."""
    await callback.answer()

    data = await state.get_data()
    agent_state = OnboardingAgentState.from_fsm_data(data)
    lang = agent_state.lang

    try:
        await callback.message.edit_text(
            "✨ Saving profile..." if lang == "en" else "✨ Сохраняю профиль..."
        )
    except Exception:
        pass

    await _do_complete_onboarding(callback.message, state, agent_state, from_user=callback.from_user)


@router.callback_query(AgentOnboarding.confirming_profile, F.data == "agent_edit")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    """User wants to edit — go back to conversation."""
    await callback.answer()

    data = await state.get_data()
    agent_state = OnboardingAgentState.from_fsm_data(data)
    agent_state.phase = "collecting"
    lang = agent_state.lang

    text = (
        "Sure! Tell me what you'd like to change." if lang == "en"
        else "Хорошо! Скажи, что хочешь изменить."
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(text)
    await state.update_data(**agent_state.to_dict())
    await state.set_state(AgentOnboarding.in_conversation)


@router.message(AgentOnboarding.confirming_profile, F.text)
async def handle_text_in_confirmation(message: Message, state: FSMContext):
    """Text during confirmation — check for confirm/edit intent."""
    if await _handle_command_in_fsm(message, state):
        return

    data = await state.get_data()
    agent_state = OnboardingAgentState.from_fsm_data(data)
    lang = agent_state.lang
    text_lower = message.text.lower().strip()

    confirmations = {"да", "yes", "ок", "ok", "верно", "correct", "подтверждаю", "confirm", "good", "хорошо", "save"}
    if text_lower in confirmations:
        await _do_complete_onboarding(message, state, agent_state)
        return

    # Treat as edit request — go back to conversation
    agent_state.phase = "collecting"
    await state.update_data(**agent_state.to_dict())
    await state.set_state(AgentOnboarding.in_conversation)

    response = await orchestrator_service.process_turn(
        agent_state,
        user_message=message.text,
        message_type="text",
    )

    await state.update_data(**agent_state.to_dict())

    if response.show_profile:
        await _show_profile_preview(message, state, agent_state)
        return

    if response.text:
        await message.answer(response.text)


@router.message(AgentOnboarding.confirming_profile, F.voice)
async def handle_voice_in_confirmation(message: Message, state: FSMContext):
    """Voice during confirmation — transcribe and treat as edit."""
    data = await state.get_data()
    agent_state = OnboardingAgentState.from_fsm_data(data)
    lang = agent_state.lang

    status = await message.answer("🎤 Processing..." if lang == "en" else "🎤 Обрабатываю...")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcription = await voice_service.download_and_transcribe(
            file_url, language=lang, prompt=_whisper_prompt(lang)
        )
        if transcription:
            transcription = await _correct_transcription(transcription)

        try:
            await status.delete()
        except Exception:
            pass

        if transcription:
            agent_state.phase = "collecting"
            await state.update_data(**agent_state.to_dict())
            await state.set_state(AgentOnboarding.in_conversation)

            response = await orchestrator_service.process_turn(
                agent_state,
                user_message=transcription,
                message_type="voice",
            )
            await state.update_data(**agent_state.to_dict())

            if response.show_profile:
                await _show_profile_preview(message, state, agent_state)
            elif response.text:
                await message.answer(response.text)
        else:
            await message.answer(
                "Couldn't hear that. Please type." if lang == "en"
                else "Не расслышал. Напиши текстом."
            )
    except Exception as e:
        logger.error(f"Voice in confirmation error: {e}")
        try:
            await status.edit_text("Please try again." if lang == "en" else "Попробуй ещё раз.")
        except Exception:
            pass


# ------------------------------------------------------------------
# Complete onboarding — reuses save logic from onboarding_audio
# ------------------------------------------------------------------

async def _do_complete_onboarding(
    message: Message,
    state: FSMContext,
    agent_state: OnboardingAgentState,
    from_user=None,
):
    """Save profile to DB, generate embeddings, run matching, show menu."""
    cl = agent_state.get_checklist()
    data = await state.get_data()
    lang = agent_state.lang

    # Resolve user identity
    if from_user:
        user_id = str(from_user.id)
        tg_username = from_user.username
    else:
        user_id = str(message.from_user.id) if message.from_user else data.get("user_first_name", "")
        tg_username = message.from_user.username if message.from_user else None

    # Build profile_data dict (same format as save_audio_profile expects)
    profile_data = cl.to_dict()
    profile_data["display_name"] = cl.display_name or agent_state.first_name

    # Build bio
    bio_lines = []
    if cl.about:
        bio_lines.append(cl.about)
    if cl.profession and cl.company:
        bio_lines.append(f"💼 {cl.profession} @ {cl.company}")
    elif cl.profession:
        bio_lines.append(f"💼 {cl.profession}")
    elif cl.company:
        bio_lines.append(f"💼 {cl.company}")
    if cl.location:
        city = cl.location.split(",")[0].strip()
        bio_lines.append(f"📍 {city}")
    bio = "\n".join(bio_lines)[:500] if bio_lines else ""

    city = cl.location
    if city:
        city = city.split(",")[0].strip()[:100]

    try:
        # Save to DB
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            user_id,
            display_name=profile_data.get("display_name") or agent_state.first_name,
            interests=(cl.interests or [])[:5],
            goals=(cl.goals or [])[:3],
            bio=bio,
            looking_for=(cl.looking_for or "")[:300] or None,
            can_help_with=(cl.can_help_with or "")[:300] or None,
            profession=cl.profession,
            company=cl.company,
            skills=(cl.skills or [])[:10],
            experience_level=cl.experience_level,
            city_current=city,
            passion_text=cl.passion_text,
            connection_mode=cl.connection_mode,
            onboarding_completed=True,
        )

        # Generate AI summary
        user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, user_id)
        if user:
            from infrastructure.ai.openai_service import OpenAIService
            ai_svc = OpenAIService()
            summary = await ai_svc.generate_user_summary(user.model_dump())
            await user_service.update_user(
                MessagePlatform.TELEGRAM, user_id, ai_summary=summary
            )

            # Background: embeddings + matching
            event_code = agent_state.event_code
            chat_id = message.chat.id

            async def _background_embeddings_and_match(user_obj, ev_code, cid):
                try:
                    result = await embedding_service.generate_embeddings(user_obj)
                    if result:
                        profile_emb, interests_emb, expertise_emb = result
                        user_repo = SupabaseUserRepository()
                        await user_repo.update_embeddings(
                            user_obj.id,
                            profile_embedding=profile_emb,
                            interests_embedding=interests_emb,
                            expertise_embedding=expertise_emb,
                        )
                        logger.info(f"Agent: embeddings generated for {user_obj.id}")

                        if ev_code:
                            updated_user = await user_repo.get_by_id(user_obj.id)
                            if updated_user and updated_user.current_event_id:
                                matches = await matching_service.find_matches_vector(
                                    user=updated_user,
                                    event_id=updated_user.current_event_id,
                                    limit=5,
                                )
                                if matches and cid:
                                    from adapters.telegram.handlers.matches import (
                                        notify_about_match,
                                        notify_admin_new_matches,
                                    )
                                    user_name = updated_user.display_name or updated_user.first_name or "Someone"
                                    for partner, result_with_id in matches[:3]:
                                        partner_name = partner.display_name or partner.first_name or "Someone"
                                        await notify_about_match(
                                            user_telegram_id=cid,
                                            partner_name=partner_name,
                                            explanation=result_with_id.explanation,
                                            icebreaker=result_with_id.icebreaker,
                                            match_id=str(result_with_id.match_id),
                                            lang=lang,
                                            partner_username=partner.username,
                                        )
                                    admin_info = [
                                        (
                                            p.display_name or p.first_name or "?",
                                            p.username,
                                            r.compatibility_score if hasattr(r, "compatibility_score") else "?",
                                            str(r.match_id),
                                        )
                                        for p, r in matches
                                    ]
                                    await notify_admin_new_matches(
                                        user_name=user_name,
                                        user_username=updated_user.username,
                                        matches_info=admin_info,
                                        event_name=ev_code,
                                    )
                except Exception as e:
                    logger.error(f"Agent background task failed for {user_obj.id}: {e}", exc_info=True)

            task = asyncio.create_task(
                _background_embeddings_and_match(user, event_code, chat_id)
            )
            task.add_done_callback(
                lambda t: _on_background_task_done(t, user_id=str(user.id))
            )

        # Handle event join
        event_code = agent_state.event_code
        if event_code:
            await event_service.join_event(
                event_code,
                MessagePlatform.TELEGRAM,
                user_id,
            )

        # Done! Show menu
        if lang == "en":
            done_text = "🎉 Profile saved! You're all set.\n\nUse the menu to find matches and explore."
        else:
            done_text = "🎉 Профиль сохранён! Всё готово.\n\nИспользуй меню для поиска и знакомств."

        await message.answer(done_text, reply_markup=get_main_menu_keyboard(lang))

    except Exception as e:
        logger.error(f"Agent onboarding save error: {e}", exc_info=True)
        await message.answer(
            "✓ Profile saved!" if lang == "en" else "✓ Профиль сохранён!",
            reply_markup=get_main_menu_keyboard(lang),
        )
    finally:
        await state.clear()
