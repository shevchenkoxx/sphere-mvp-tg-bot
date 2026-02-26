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

from adapters.telegram.keyboards import get_main_menu_keyboard, build_ai_keyboard
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
from adapters.telegram.states.onboarding import AgentOnboarding, ProfileExpansion
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


async def _send_orchestrator_response(message: Message, state: FSMContext, response):
    """Send orchestrator response text with optional AI-chosen keyboard."""
    keyboard = None
    if response.ui and response.ui.options and response.ui.ui_type != "none":
        keyboard = build_ai_keyboard(
            options=response.ui.options,
            ui_type=response.ui.ui_type,
        )
        # Store options in FSM so callback handler can map index → label
        await state.update_data(ai_choice_options=response.ui.options)

    text = response.text
    if response.ui and response.ui.ui_type != "none":
        # If interact_with_user was called, its message_text may differ from response.text
        # The orchestrator puts the tool's text into response.text after follow-up
        pass

    if text:
        await message.answer(text, reply_markup=keyboard)
    elif keyboard:
        # AI returned only buttons with no text — shouldn't happen but handle it
        await message.answer("Choose one:", reply_markup=keyboard)


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

    # Pick up context from FSM state (set by deep link handler or story)
    fsm_data = await state.get_data()

    # When called from story CTA callback, message.from_user is the bot.
    # Use user_first_name saved during story start instead.
    first_name = fsm_data.get("user_first_name") or message.from_user.first_name or ""
    community_id = fsm_data.get("community_id")
    community_name = fsm_data.get("community_name")

    # Initialise agent state
    agent_state = OnboardingAgentState(
        event_code=event_code,
        event_name=event_name,
        community_id=community_id,
        community_name=community_name,
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
        community_id=community_id,
        community_name=community_name,
        language=lang,
        user_first_name=first_name,
    )

    # Opening message — just tell the agent who the user is
    greeting_prompt = f"Hi, I'm {first_name}. I just opened the bot."
    response = await orchestrator_service.process_turn(
        agent_state,
        user_message=greeting_prompt,
        message_type="text",
    )

    # Save updated state
    await state.update_data(**agent_state.to_dict())
    await state.set_state(AgentOnboarding.in_conversation)

    if response.show_profile:
        await _show_profile_preview(message, state, agent_state)
    elif response.text or (response.ui and response.ui.options):
        await _send_orchestrator_response(message, state, response)
    else:
        # Fallback greeting if LLM returned nothing
        fallback = (
            f"Hey {first_name}! 👋 Welcome! Tell me about yourself — what do you do and who are you looking to meet?"
            if lang == "en"
            else f"Привет, {first_name}! 👋 Расскажи о себе — чем занимаешься и кого хочешь найти?"
        )
        await message.answer(fallback)


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

    if response.text or (response.ui and response.ui.options):
        await _send_orchestrator_response(message, state, response)
    else:
        lang = agent_state.lang
        await message.answer(
            "Got it! Tell me more about yourself." if lang == "en"
            else "Понял! Расскажи ещё о себе."
        )


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

        if response.text or (response.ui and response.ui.options):
            await _send_orchestrator_response(message, state, response)
        else:
            await message.answer(
                "Got it! What else can you tell me?" if lang == "en"
                else "Понял! Что ещё расскажешь?"
            )

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
# AI-generated button callbacks
# ------------------------------------------------------------------

@router.callback_query(AgentOnboarding.in_conversation, F.data.startswith("ai_choice:"))
async def handle_ai_choice(callback: CallbackQuery, state: FSMContext):
    """Handle user pressing an AI-generated button."""
    await callback.answer()

    data = await state.get_data()
    agent_state = OnboardingAgentState.from_fsm_data(data)
    options = data.get("ai_choice_options", [])

    # Map callback index to label text
    try:
        idx = int(callback.data.split(":")[1])
        chosen_label = options[idx] if idx < len(options) else callback.data
    except (ValueError, IndexError):
        chosen_label = callback.data

    # Remove the keyboard from the message
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Feed the chosen option back to the orchestrator as a user message
    response = await orchestrator_service.process_turn(
        agent_state,
        user_message=f"User selected: {chosen_label}",
        message_type="text",
    )

    await state.update_data(**agent_state.to_dict())

    if response.is_complete:
        await _do_complete_onboarding(callback.message, state, agent_state, from_user=callback.from_user)
        return

    if response.show_profile:
        await _show_profile_preview(callback.message, state, agent_state)
        return

    if response.text or (response.ui and response.ui.options):
        await _send_orchestrator_response(callback.message, state, response)
    else:
        lang = agent_state.lang
        await callback.message.answer(
            "Got it! Tell me more." if lang == "en" else "Понял! Расскажи ещё."
        )


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

    sent = await message.answer(text, reply_markup=get_agent_confirm_keyboard(lang), parse_mode="HTML")
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
    """Save profile to DB, generate embeddings, run matching, show results directly."""
    cl = agent_state.get_checklist()
    data = await state.get_data()
    lang = agent_state.lang

    # Resolve user identity
    if from_user:
        user_id = str(from_user.id)
        tg_username = from_user.username
    elif message.from_user:
        user_id = str(message.from_user.id)
        tg_username = message.from_user.username
    else:
        # Last resort — should never happen
        user_id = data.get("agent_user_id", "")
        tg_username = None

    if not user_id:
        logger.error("Cannot resolve user_id in _do_complete_onboarding")
        await message.answer("Something went wrong. Please try /start again.")
        await state.clear()
        return

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
            matching_scope=cl.matching_scope or "global",
            meeting_preference=cl.meeting_preference or "both",
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

            # AWAIT embeddings + matching (not background) — show results immediately
            chat_id = message.chat.id
            loading_msg = await message.answer(
                "🔍 Finding your people..." if lang == "en" else "🔍 Ищу подходящих людей..."
            )

            matches_found = []
            try:
                result = await embedding_service.generate_embeddings(user)
                if result:
                    profile_emb, interests_emb, expertise_emb = result
                    user_repo = SupabaseUserRepository()
                    await user_repo.update_embeddings(
                        user.id,
                        profile_embedding=profile_emb,
                        interests_embedding=interests_emb,
                        expertise_embedding=expertise_emb,
                    )
                    logger.info(f"Agent: embeddings generated for {user.id}")

                    # Join event BEFORE matching so current_event_id is set
                    event_code = agent_state.event_code
                    if event_code:
                        await event_service.join_event(
                            event_code,
                            MessagePlatform.TELEGRAM,
                            user_id,
                        )

                    # Mark community member as onboarded
                    community_id_str = agent_state.community_id
                    if community_id_str:
                        try:
                            from adapters.telegram.loader import community_repo
                            from uuid import UUID as _UUID
                            await community_repo.set_member_onboarded(
                                _UUID(community_id_str), user.id
                            )
                        except Exception as e:
                            logger.warning(f"Failed to mark community member onboarded: {e}")

                    # Run matching (community-scoped if from community, otherwise global)
                    updated_user = await user_repo.get_by_id(user.id)
                    if updated_user:
                        if community_id_str:
                            # Community-scoped matching first
                            from uuid import UUID as _UUID
                            matches_found = await matching_service.find_community_matches(
                                user=updated_user,
                                community_id=_UUID(community_id_str),
                                limit=5,
                            ) or []
                        else:
                            # Global matching
                            matches_found = await matching_service.find_global_matches(
                                user=updated_user,
                                limit=5,
                            ) or []

                        # Also match event if present
                        if event_code and updated_user.current_event_id:
                            event_matches = await matching_service.find_matches_vector(
                                user=updated_user,
                                event_id=updated_user.current_event_id,
                                limit=5,
                            ) or []
                            matches_found.extend(event_matches)
            except Exception as e:
                logger.error(f"Embeddings/matching failed for {user.id}: {e}", exc_info=True)

            # Delete loading message
            try:
                await loading_msg.delete()
            except Exception:
                pass

            # Show results
            match_count = len(matches_found)

            if match_count > 0:
                # Notify about matches + show the match card
                from adapters.telegram.handlers.matches import (
                    notify_about_match,
                    notify_admin_new_matches,
                    show_matches as show_matches_view,
                )

                admin_info = []
                for partner, result_with_id in matches_found[:3]:
                    partner_name = partner.display_name or partner.first_name or "Someone"
                    admin_info.append((
                        partner_name,
                        partner.username,
                        result_with_id.compatibility_score if hasattr(result_with_id, "compatibility_score") else "?",
                        str(result_with_id.match_id),
                    ))

                user_name = user.display_name or user.first_name or "Someone"
                await notify_admin_new_matches(
                    user_name=user_name,
                    user_username=user.username,
                    matches_info=admin_info,
                )

                done_text = (
                    f"🎉 Found {match_count} match{'es' if match_count != 1 else ''}!"
                    if lang == "en" else
                    f"🎉 Найдено {match_count} {'матчей' if match_count > 1 else 'матч'}!"
                )
                await message.answer(done_text)

                # Generate personality card in background
                asyncio.create_task(_send_personality_card(message.chat.id, user))

                # Show first match card directly
                await state.clear()
                await show_matches_view(message, user.id, lang=lang, edit=False, match_scope="global")

                # Offer Sphere Global for DM users not from a community
                if not community_id_str:
                    asyncio.create_task(_offer_sphere_global(message.chat.id, user, lang))
                return

            else:
                # No matches — generate personality card, then expansion
                asyncio.create_task(_send_personality_card(message.chat.id, user))

                # Offer Sphere Global for DM users not from a community
                if not community_id_str:
                    asyncio.create_task(_offer_sphere_global(message.chat.id, user, lang))

                await state.clear()
                await _start_expansion_flow(message, state, user, lang)
                return

        # Fallback if user fetch failed
        await message.answer(
            "🎉 Profile saved!" if lang == "en" else "🎉 Профиль сохранён!",
            reply_markup=get_main_menu_keyboard(lang),
        )

    except Exception as e:
        logger.error(f"Agent onboarding save error: {e}", exc_info=True)
        await message.answer(
            "✓ Profile saved!" if lang == "en" else "✓ Профиль сохранён!",
            reply_markup=get_main_menu_keyboard(lang),
        )
        await state.clear()


# ------------------------------------------------------------------
# Profile Expansion Flow — "No matches? Let me learn more about you"
# ------------------------------------------------------------------

EXPANSION_PROMPT = """\
You are Sphere — a sharp, curious friend helping someone find their people.

The user just finished onboarding but we found NO matches for them (or very few). Your job: ask 2-3 targeted questions that will BROADEN their matchability. The answers will be added to their profile and matching will run again.

Language: {language}
User's name: {first_name}

Current profile:
- About: {about}
- Looking for: {looking_for}
- Can help with: {can_help_with}
- Interests: {interests}
- Profession: {profession}

## Strategy
Ask questions that reveal NEW dimensions of this person — things that create unexpected connections:
- "What kind of conversations light you up?"
- "Is there something you'd love to teach someone?"
- "What's a random skill or hobby people are always surprised you have?"
- "If you could spend a day with anyone in our community, what would you want to do?"

## Rules
- 1-2 sentences per message. Casual, warm, NOT interview-y.
- Ask ONE question at a time.
- After 2-3 answers, say something like "Let me search again with this!" and stop.
- NEVER use: "leverage", "robust", "innovative", "passionate about", "like-minded"
- Extract as much as you can from each answer.
"""

EXPANSION_QUESTIONS = [
    "What kind of conversations get you excited? Like the ones where you lose track of time.",
    "Is there something you'd love to teach someone — or learn from someone?",
    "What's a random thing people are always surprised about you?",
]


async def _start_expansion_flow(message: Message, state: FSMContext, user, lang: str):
    """Start the expansion flow when no/few matches are found after onboarding."""
    if lang == "ru":
        text = (
            "Пока не нашёл идеальных матчей — но это не страшно!\n\n"
            "Расскажи мне чуть больше о себе, и я поищу снова 🔍"
        )
    else:
        text = (
            "Haven't found the perfect matches yet — but that's okay!\n\n"
            "Tell me a bit more about yourself and I'll search again 🔍"
        )
    await message.answer(text)

    # Ask first expansion question
    q_index = 0
    question = EXPANSION_QUESTIONS[q_index]
    if lang == "ru":
        # Simple Russian translations
        ru_questions = [
            "Какие разговоры тебя по-настоящему увлекают? Такие, где теряешь счёт времени.",
            "Есть что-то, чему ты хотел бы научить кого-то — или научиться у кого-то?",
            "Что-то необычное, чему люди всегда удивляются, узнав о тебе?",
        ]
        question = ru_questions[q_index]

    await message.answer(question)

    await state.set_state(ProfileExpansion.in_conversation)
    await state.update_data(
        expansion_user_id=str(user.id),
        expansion_lang=lang,
        expansion_q_index=0,
        expansion_answers=[],
        expansion_platform_user_id=str(message.from_user.id) if message.from_user else "",
    )


@router.message(ProfileExpansion.in_conversation, F.text)
async def handle_expansion_text(message: Message, state: FSMContext):
    """Handle text during expansion flow."""
    if message.text and message.text.startswith("/"):
        await state.clear()
        if message.text.startswith("/start"):
            from adapters.telegram.handlers.start import start_command
            await start_command(message, state)
        return

    data = await state.get_data()
    lang = data.get("expansion_lang", "en")
    q_index = data.get("expansion_q_index", 0)
    answers = data.get("expansion_answers", [])
    user_id = data.get("expansion_user_id")
    platform_user_id = data.get("expansion_platform_user_id", "")

    # Save answer
    answers.append(message.text)
    q_index += 1

    if q_index >= len(EXPANSION_QUESTIONS):
        # Done collecting — merge answers into profile and rematch
        await state.clear()
        await _finish_expansion(message, user_id, platform_user_id, answers, lang)
        return

    # Ask next question
    question = EXPANSION_QUESTIONS[q_index]
    if lang == "ru":
        ru_questions = [
            "Какие разговоры тебя по-настоящему увлекают? Такие, где теряешь счёт времени.",
            "Есть что-то, чему ты хотел бы научить кого-то — или научиться у кого-то?",
            "Что-то необычное, чему люди всегда удивляются, узнав о тебе?",
        ]
        question = ru_questions[q_index]

    await message.answer(question)
    await state.update_data(expansion_q_index=q_index, expansion_answers=answers)


@router.message(ProfileExpansion.in_conversation, F.voice)
async def handle_expansion_voice(message: Message, state: FSMContext):
    """Handle voice during expansion — transcribe and treat as text."""
    data = await state.get_data()
    lang = data.get("expansion_lang", "en")

    status = await message.answer("🎤 ..." if lang == "en" else "🎤 ...")
    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcription = await voice_service.download_and_transcribe(
            file_url, language=lang, prompt=_whisper_prompt(lang)
        )
        try:
            await status.delete()
        except Exception:
            pass

        if transcription and len(transcription) > 5:
            # Fake a text message with the transcription
            message.text = transcription
            await handle_expansion_text(message, state)
        else:
            await message.answer(
                "Couldn't hear that. Please try again or type." if lang == "en"
                else "Не расслышал. Попробуй ещё раз или напиши."
            )
    except Exception as e:
        logger.error(f"Expansion voice error: {e}")
        try:
            await status.edit_text("Please try again." if lang == "en" else "Попробуй ещё раз.")
        except Exception:
            pass


async def _finish_expansion(message: Message, user_id: str, platform_user_id: str, answers: list, lang: str):
    """Merge expansion answers into profile, regenerate embeddings, and rematch."""
    loading = await message.answer(
        "🔍 Searching again with your new info..." if lang == "en"
        else "🔍 Ищу снова с новой информацией..."
    )

    try:
        # Use LLM to extract enrichment from answers
        from infrastructure.ai.openai_service import OpenAIService
        ai_svc = OpenAIService()

        combined_text = "\n".join(answers)
        extraction_prompt = (
            "Extract profile enrichment from these answers. Return JSON with any of these fields "
            "that you can extract: interests (array), can_help_with (string), looking_for (string addition), "
            "skills (array), passion_text (string). Only include fields with real content.\n\n"
            f"Answers:\n{combined_text}"
        )

        import json
        response = await ai_svc.chat(extraction_prompt)
        enrichment = {}
        try:
            # Try to parse JSON from response
            json_str = response
            if "```" in json_str:
                json_str = json_str.split("```")[1].strip()
                if json_str.startswith("json"):
                    json_str = json_str[4:].strip()
            enrichment = json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"Failed to parse expansion enrichment JSON: {response[:200]}")

        # Get current user
        user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, platform_user_id)
        if not user:
            await loading.edit_text("Something went wrong." if lang == "en" else "Что-то пошло не так.")
            return

        # Merge enrichment into profile
        update_kwargs = {}
        if enrichment.get("interests"):
            current = user.interests or []
            new_interests = list(set(current + enrichment["interests"]))[:10]
            update_kwargs["interests"] = new_interests
        if enrichment.get("can_help_with"):
            current = user.can_help_with or ""
            addition = enrichment["can_help_with"]
            update_kwargs["can_help_with"] = f"{current}; {addition}".strip("; ")[:300]
        if enrichment.get("looking_for"):
            current = user.looking_for or ""
            addition = enrichment["looking_for"]
            update_kwargs["looking_for"] = f"{current}; {addition}".strip("; ")[:300]
        if enrichment.get("skills"):
            current = getattr(user, 'skills', None) or []
            new_skills = list(set(current + enrichment["skills"]))[:10]
            update_kwargs["skills"] = new_skills
        if enrichment.get("passion_text"):
            update_kwargs["passion_text"] = enrichment["passion_text"][:200]

        if update_kwargs:
            await user_service.update_user(
                MessagePlatform.TELEGRAM, platform_user_id, **update_kwargs
            )

        # Regenerate embeddings
        user = await user_service.get_user_by_platform(MessagePlatform.TELEGRAM, platform_user_id)
        if user:
            result = await embedding_service.generate_embeddings(user)
            if result:
                user_repo = SupabaseUserRepository()
                await user_repo.update_embeddings(
                    user.id,
                    profile_embedding=result[0],
                    interests_embedding=result[1],
                    expertise_embedding=result[2],
                )

            # Rematch
            updated_user = await user_repo.get_by_id(user.id)
            matches_found = []
            if updated_user:
                matches_found = await matching_service.find_global_matches(
                    user=updated_user, limit=5
                ) or []

            try:
                await loading.delete()
            except Exception:
                pass

            match_count = len(matches_found)
            if match_count > 0:
                from adapters.telegram.handlers.matches import show_matches as show_matches_view

                done_text = (
                    f"🎉 Found {match_count} match{'es' if match_count != 1 else ''}!"
                    if lang == "en" else
                    f"🎉 Нашёл {match_count} {'матчей' if match_count > 1 else 'матч'}!"
                )
                await message.answer(done_text)
                await show_matches_view(message, user.id, lang=lang, edit=False, match_scope="global")
            else:
                if lang == "ru":
                    text = (
                        "Пока матчей нет — но твой профиль уже работает!\n"
                        "Как только появятся подходящие люди, ты получишь уведомление 🔔"
                    )
                else:
                    text = (
                        "No matches yet — but your profile is live!\n"
                        "You'll get notified as soon as someone great joins 🔔"
                    )
                await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
        else:
            try:
                await loading.delete()
            except Exception:
                pass
            await message.answer(
                "Profile updated!" if lang == "en" else "Профиль обновлён!",
                reply_markup=get_main_menu_keyboard(lang),
            )

    except Exception as e:
        logger.error(f"Expansion finish error: {e}", exc_info=True)
        try:
            await loading.delete()
        except Exception:
            pass
        await message.answer(
            "Profile updated! Check back later for matches." if lang == "en"
            else "Профиль обновлён! Заходи позже за матчами.",
            reply_markup=get_main_menu_keyboard(lang),
        )


# ------------------------------------------------------------------
# Sphere Global offer — sent after onboarding for non-community users
# ------------------------------------------------------------------

async def _offer_sphere_global(chat_id: int, user, lang: str):
    """Offer to join Sphere Global community after DM onboarding."""
    try:
        from adapters.telegram.loader import community_service, community_repo
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        # Skip if user already in a community
        communities = await community_repo.get_user_communities(user.id)
        if communities:
            return

        if lang == "ru":
            text = (
                "🌍 <b>Sphere Global</b>\n\n"
                "Присоединяйся к глобальному сообществу!\n"
                "Найди интересных людей за пределами своей группы."
            )
            btn_join = "🌍 Присоединиться"
            btn_skip = "⏩ Пропустить"
        else:
            text = (
                "🌍 <b>Sphere Global</b>\n\n"
                "Join the global community!\n"
                "Meet interesting people beyond your group."
            )
            btn_join = "🌍 Join Sphere Global"
            btn_skip = "⏩ Skip"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn_join, callback_data="join_sphere_global")],
            [InlineKeyboardButton(text=btn_skip, callback_data="skip_sphere_global")],
        ])
        await bot.send_message(chat_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"[GLOBAL] Failed to offer Sphere Global: {e}")


# ------------------------------------------------------------------
# Personality Card — sent after onboarding as a shareable image
# ------------------------------------------------------------------

async def _send_personality_card(chat_id: int, user):
    """Generate and send a personality card image to the user in DM."""
    try:
        from core.utils.personality_card import generate_personality_summary, render_personality_card
        from aiogram.types import BufferedInputFile

        personality = await generate_personality_summary(user)
        bot_info = await bot.get_me()
        qr_url = f"https://t.me/{bot_info.username}"

        png_bytes = render_personality_card(
            name=user.display_name or user.first_name or "You",
            personality=personality,
            interests=user.interests,
            qr_url=qr_url,
        )

        caption = (
            f"✨ Your Sphere Card: <b>{personality.get('type', 'Explorer')}</b>\n\n"
            f"Share this in your group to help others find you!"
        )

        photo = BufferedInputFile(png_bytes, filename="sphere_card.png")
        await bot.send_photo(chat_id, photo=photo, caption=caption)
    except Exception as e:
        logger.warning(f"[CARD] Failed to send personality card: {e}")
