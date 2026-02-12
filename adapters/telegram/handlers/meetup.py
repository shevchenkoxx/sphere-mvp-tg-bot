"""
Meetup handler - proposer FSM flow + receiver accept/decline callbacks.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from core.domain.models import MessagePlatform, MatchStatus
from adapters.telegram.states.onboarding import MeetupStates
from adapters.telegram.loader import (
    user_service, matching_service, bot,
    meetup_repo, meetup_ai_service,
)
from adapters.telegram.keyboards.inline import (
    get_meetup_time_keyboard,
    get_meetup_preview_keyboard,
    get_meetup_receiver_keyboard,
    get_meetup_confirmation_keyboard,
    get_back_to_menu_keyboard,
    MEETUP_TIME_SLOTS,
)
from core.utils.language import detect_lang

logger = logging.getLogger(__name__)
router = Router()


def _format_time_slot(minutes: int, lang: str = "en") -> str:
    """Format a single time slot value for display (0 = Anytime)."""
    if minutes == 0:
        return "Anytime" if lang == "en" else "Любое время"
    return f"{minutes} min"


# ─────────────────────────────────────────────
# PROPOSER FLOW
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("meet_"))
async def start_meetup_proposal(callback: CallbackQuery, state: FSMContext):
    """Entry point: user clicks Meet on a match card"""
    lang = detect_lang(callback)
    match_id = callback.data.replace("meet_", "")

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM, str(callback.from_user.id)
    )
    if not user:
        await callback.answer("Profile not found", show_alert=True)
        return

    match = await matching_service.get_match(match_id)
    if not match:
        await callback.answer("Match not found", show_alert=True)
        return

    # Check for existing pending proposal from this user
    existing = await meetup_repo.get_pending_for_match(match.id, user.id)
    if existing:
        await callback.answer(
            "You already have a pending meetup proposal for this match!" if lang == "en"
            else "У тебя уже есть активное предложение встречи для этого матча!",
            show_alert=True,
        )
        return

    # Store match context in FSM
    partner_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    await state.update_data(
        meetup_match_id=str(match.id),
        meetup_partner_id=str(partner_id),
        meetup_event_id=str(match.event_id) if match.event_id else None,
        meetup_selected_times=[],
        meetup_ai_explanation=match.ai_explanation,
    )
    await state.set_state(MeetupStates.selecting_times)

    text = (
        "<b>☕ Propose a meetup</b>\n\n"
        "Select time slots you're available for:"
        if lang == "en" else
        "<b>☕ Предложить встречу</b>\n\n"
        "Выбери подходящие слоты времени:"
    )

    await callback.message.edit_text(
        text, reply_markup=get_meetup_time_keyboard([], lang)
    )
    await callback.answer()


@router.callback_query(MeetupStates.selecting_times, F.data.startswith("mt_"))
async def toggle_time_slot(callback: CallbackQuery, state: FSMContext):
    """Toggle a time slot on/off, or handle done/cancel"""
    lang = detect_lang(callback)
    data_str = callback.data

    # Cancel
    if data_str == "mt_cancel":
        await state.clear()
        await callback.message.edit_text(
            "Meetup cancelled." if lang == "en" else "Встреча отменена.",
            reply_markup=get_back_to_menu_keyboard(lang),
        )
        await callback.answer()
        return

    # Done selecting
    if data_str == "mt_done":
        fsm = await state.get_data()
        selected = fsm.get("meetup_selected_times", [])
        if not selected:
            await callback.answer(
                "Select at least one time slot" if lang == "en"
                else "Выбери хотя бы один слот",
                show_alert=True,
            )
            return

        await state.set_state(MeetupStates.entering_location)

        text = (
            "<b>📍 Where to meet?</b>\n\n"
            "Type a short location (e.g. \"by the bar\", \"near stage 2\"):"
            if lang == "en" else
            "<b>📍 Где встретиться?</b>\n\n"
            "Напиши место (напр. \"у бара\", \"рядом со сценой 2\"):"
        )
        await callback.message.edit_text(text)
        await callback.answer()
        return

    # Toggle slot index
    try:
        slot_idx = int(data_str.replace("mt_", ""))
    except ValueError:
        await callback.answer()
        return

    if slot_idx < 0 or slot_idx >= len(MEETUP_TIME_SLOTS):
        await callback.answer()
        return

    minutes = MEETUP_TIME_SLOTS[slot_idx]
    fsm = await state.get_data()
    selected = list(fsm.get("meetup_selected_times", []))

    if minutes in selected:
        selected.remove(minutes)
    else:
        selected.append(minutes)

    await state.update_data(meetup_selected_times=selected)

    text = (
        "<b>☕ Propose a meetup</b>\n\n"
        "Select time slots you're available for:"
        if lang == "en" else
        "<b>☕ Предложить встречу</b>\n\n"
        "Выбери подходящие слоты времени:"
    )

    await callback.message.edit_text(
        text, reply_markup=get_meetup_time_keyboard(selected, lang)
    )
    await callback.answer()


@router.message(MeetupStates.entering_location)
async def receive_location(message: Message, state: FSMContext):
    """User types location text"""
    lang = detect_lang(message)
    location = message.text.strip()[:200] if message.text else ""

    if not location:
        await message.answer(
            "Please type a location." if lang == "en" else "Напиши место встречи."
        )
        return

    await state.update_data(meetup_location=location)

    # Show "generating..." then build preview
    status_msg = await message.answer(
        "🤖 Generating your meetup invitation..." if lang == "en"
        else "🤖 Генерирую приглашение..."
    )

    fsm = await state.get_data()
    match_id = fsm["meetup_match_id"]
    partner_id = fsm["meetup_partner_id"]
    selected_times = fsm["meetup_selected_times"]
    ai_explanation = fsm.get("meetup_ai_explanation")

    # Get both users for AI
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM, str(message.from_user.id)
    )
    partner = await user_service.get_user(partner_id)

    # Generate AI content
    why_meet, topics = await meetup_ai_service.generate_meetup_content(
        proposer=user, receiver=partner, match_explanation=ai_explanation
    )

    await state.update_data(
        meetup_why_meet=why_meet,
        meetup_topics=topics,
    )
    await state.set_state(MeetupStates.previewing)

    # Build preview card
    partner_name = partner.display_name or partner.first_name or "Match"
    times_str = ", ".join([_format_time_slot(m, lang) for m in sorted(selected_times)])

    preview = (
        f"<b>☕ Meetup invitation preview</b>\n"
        f"{'─' * 20}\n\n"
        f"<b>To:</b> {partner_name}\n"
        f"<b>Time slots:</b> {times_str}\n"
        f"<b>Location:</b> {location}\n\n"
        f"<b>Why meet:</b>\n<i>{why_meet}</i>\n\n"
        f"<b>Topics:</b>\n"
    )
    for i, topic in enumerate(topics, 1):
        preview += f"  {i}. {topic}\n"

    preview += f"\n{'─' * 20}"

    await status_msg.delete()
    await message.answer(preview, reply_markup=get_meetup_preview_keyboard(lang))


@router.callback_query(MeetupStates.previewing, F.data == "mt_send")
async def send_meetup_proposal(callback: CallbackQuery, state: FSMContext):
    """Send the meetup proposal to the receiver"""
    lang = detect_lang(callback)
    fsm = await state.get_data()

    match_id = fsm["meetup_match_id"]
    partner_id = fsm["meetup_partner_id"]
    selected_times = fsm["meetup_selected_times"]
    location = fsm["meetup_location"]
    why_meet = fsm.get("meetup_why_meet", "")
    topics = fsm.get("meetup_topics", [])
    event_id = fsm.get("meetup_event_id")

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM, str(callback.from_user.id)
    )

    # Create proposal in DB
    try:
        proposal = await meetup_repo.create_proposal(
            match_id=match_id,
            proposer_id=user.id,
            receiver_id=partner_id,
            time_slots=sorted(selected_times),
            location=location,
            ai_why_meet=why_meet,
            ai_topics=topics,
            event_id=event_id,
        )
    except Exception as e:
        logger.error(f"Failed to create meetup proposal: {e}", exc_info=True)
        await callback.message.edit_text(
            "Failed to create meetup proposal. You may already have one pending."
            if lang == "en" else
            "Не удалось создать предложение. Возможно, у тебя уже есть активное предложение.",
            reply_markup=get_back_to_menu_keyboard(lang),
        )
        await state.clear()
        await callback.answer()
        return

    await state.clear()

    # Notify receiver
    partner = await user_service.get_user(partner_id)
    proposer_name = user.display_name or user.first_name or "Someone"
    partner_name = partner.display_name or partner.first_name or "Match"
    times_str = ", ".join([_format_time_slot(m, lang) for m in proposal.time_slots])

    invitation_text = (
        f"<b>☕ Meetup invitation!</b>\n"
        f"{'─' * 20}\n\n"
        f"<b>{proposer_name}</b> wants to meet you!\n\n"
        f"<b>Why meet:</b>\n<i>{why_meet}</i>\n\n"
        f"<b>Topics to discuss:</b>\n"
    )
    for i, topic in enumerate(topics, 1):
        invitation_text += f"  {i}. {topic}\n"

    invitation_text += (
        f"\n<b>Time slots:</b> {times_str}\n"
        f"<b>Location:</b> {location}\n"
        f"\n{'─' * 20}\n"
        f"<i>Pick a time to accept or decline</i>"
    )

    try:
        await bot.send_message(
            int(partner.platform_user_id),
            invitation_text,
            reply_markup=get_meetup_receiver_keyboard(
                proposal.short_id, proposal.time_slots, lang
            ),
        )
    except Exception as e:
        logger.error(f"Failed to send meetup to receiver {partner_id}: {e}")

    # Confirm to proposer
    partner_username = partner.username if partner else None
    confirm_text = (
        f"<b>✅ Meetup proposal sent to {partner_name}!</b>\n\n"
        f"They'll pick a time slot or decline.\n"
        f"You'll be notified when they respond."
    )

    await callback.message.edit_text(
        confirm_text,
        reply_markup=get_meetup_confirmation_keyboard(
            proposal.short_id, partner_username, lang
        ),
    )
    await callback.answer()


@router.callback_query(MeetupStates.previewing, F.data == "mt_editloc")
async def edit_location(callback: CallbackQuery, state: FSMContext):
    """Go back to location entry"""
    lang = detect_lang(callback)
    await state.set_state(MeetupStates.entering_location)

    text = (
        "<b>📍 Where to meet?</b>\n\n"
        "Type a new location:"
        if lang == "en" else
        "<b>📍 Где встретиться?</b>\n\n"
        "Напиши новое место:"
    )
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(MeetupStates.previewing, F.data == "mt_cancel")
async def cancel_preview(callback: CallbackQuery, state: FSMContext):
    """Cancel from preview"""
    lang = detect_lang(callback)
    await state.clear()
    await callback.message.edit_text(
        "Meetup cancelled." if lang == "en" else "Встреча отменена.",
        reply_markup=get_back_to_menu_keyboard(lang),
    )
    await callback.answer()


# ─────────────────────────────────────────────
# RECEIVER FLOW (stateless callbacks)
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("ma_"))
async def accept_meetup(callback: CallbackQuery):
    """Receiver accepts meetup with a specific time slot"""
    lang = detect_lang(callback)

    # Parse: ma_{short_id}_{slot_idx}
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("Invalid data", show_alert=True)
        return

    short_id = parts[1]
    try:
        slot_idx = int(parts[2])
    except ValueError:
        await callback.answer("Invalid data", show_alert=True)
        return

    proposal = await meetup_repo.get_by_short_id(short_id)
    if not proposal:
        await callback.answer("Proposal not found", show_alert=True)
        return

    # Check status
    if proposal.status != "pending":
        status_msg = {
            "accepted": "Already accepted" if lang == "en" else "Уже принято",
            "declined": "Already declined" if lang == "en" else "Уже отклонено",
            "expired": "This proposal has expired" if lang == "en" else "Предложение истекло",
            "cancelled": "This proposal was cancelled" if lang == "en" else "Предложение отменено",
        }
        await callback.answer(
            status_msg.get(proposal.status, "Not available"), show_alert=True
        )
        return

    # Check expiry
    if meetup_repo.is_expired(proposal):
        await callback.answer(
            "This meetup proposal has expired" if lang == "en"
            else "Предложение истекло",
            show_alert=True,
        )
        return

    # Validate slot index
    if slot_idx < 0 or slot_idx >= len(proposal.time_slots):
        await callback.answer("Invalid time slot", show_alert=True)
        return

    accepted_minutes = proposal.time_slots[slot_idx]

    # Accept in DB
    updated = await meetup_repo.accept_proposal(proposal.id, accepted_minutes)
    if not updated:
        await callback.answer("Failed to accept", show_alert=True)
        return

    # Get both users
    proposer = await user_service.get_user(proposal.proposer_id)
    receiver = await user_service.get_user(proposal.receiver_id)

    proposer_name = (proposer.display_name or proposer.first_name or "Someone") if proposer else "Someone"
    receiver_name = (receiver.display_name or receiver.first_name or "Someone") if receiver else "Someone"
    proposer_username = proposer.username if proposer else None
    receiver_username = receiver.username if receiver else None

    # Build confirmation message
    topics_text = ""
    if proposal.ai_topics:
        for i, topic in enumerate(proposal.ai_topics, 1):
            topics_text += f"  {i}. {topic}\n"

    confirmation = (
        f"<b>✅ Meetup confirmed!</b>\n"
        f"{'─' * 20}\n\n"
        f"<b>{proposer_name}</b> + <b>{receiver_name}</b>\n\n"
        f"<b>Time:</b> {_format_time_slot(accepted_minutes, lang)}\n"
        f"<b>Location:</b> {proposal.location}\n"
    )

    if proposal.ai_why_meet:
        confirmation += f"\n<b>Why meet:</b>\n<i>{proposal.ai_why_meet}</i>\n"

    if topics_text:
        confirmation += f"\n<b>Topics:</b>\n{topics_text}"

    # Add icebreaker from match
    match = await matching_service.get_match(str(proposal.match_id))
    if match and match.icebreaker:
        confirmation += f"\n<b>Icebreaker:</b> <i>{match.icebreaker}</i>\n"

    confirmation += f"\n{'─' * 20}"

    # Update receiver's message
    await callback.message.edit_text(
        confirmation,
        reply_markup=get_meetup_confirmation_keyboard(
            short_id, proposer_username, lang
        ),
    )
    await callback.answer("Meetup accepted!" if lang == "en" else "Встреча принята!")

    # Notify proposer
    try:
        proposer_notification = (
            f"<b>✅ {receiver_name} accepted your meetup!</b>\n"
            f"{'─' * 20}\n\n"
            f"<b>Time:</b> {_format_time_slot(accepted_minutes, lang)}\n"
            f"<b>Location:</b> {proposal.location}\n"
        )

        if proposal.ai_topics:
            proposer_notification += "\n<b>Topics:</b>\n"
            for i, topic in enumerate(proposal.ai_topics, 1):
                proposer_notification += f"  {i}. {topic}\n"

        if match and match.icebreaker:
            proposer_notification += f"\n<b>Icebreaker:</b> <i>{match.icebreaker}</i>\n"

        proposer_notification += f"\n{'─' * 20}"

        await bot.send_message(
            int(proposer.platform_user_id),
            proposer_notification,
            reply_markup=get_meetup_confirmation_keyboard(
                short_id, receiver_username, lang
            ),
        )
    except Exception as e:
        logger.error(f"Failed to notify proposer about acceptance: {e}")


@router.callback_query(F.data.startswith("md_"))
async def decline_meetup(callback: CallbackQuery):
    """Receiver declines meetup"""
    lang = detect_lang(callback)

    short_id = callback.data.replace("md_", "")

    proposal = await meetup_repo.get_by_short_id(short_id)
    if not proposal:
        await callback.answer("Proposal not found", show_alert=True)
        return

    if proposal.status != "pending":
        await callback.answer("Already responded", show_alert=True)
        return

    # Decline in DB
    await meetup_repo.decline_proposal(proposal.id)

    await callback.message.edit_text(
        "Meetup declined." if lang == "en" else "Встреча отклонена.",
        reply_markup=get_back_to_menu_keyboard(lang),
    )
    await callback.answer()

    # Notify proposer
    try:
        proposer = await user_service.get_user(proposal.proposer_id)
        receiver = await user_service.get_user(proposal.receiver_id)
        receiver_name = receiver.display_name or receiver.first_name or "Your match"

        await bot.send_message(
            int(proposer.platform_user_id),
            f"{receiver_name} declined the meetup. No worries — you can try again later!"
            if lang == "en" else
            f"{receiver_name} отклонил(а) встречу. Ничего — можно попробовать позже!",
            reply_markup=get_back_to_menu_keyboard(lang),
        )
    except Exception as e:
        logger.error(f"Failed to notify proposer about decline: {e}")


@router.callback_query(F.data.startswith("mc_"))
async def copy_for_dm(callback: CallbackQuery):
    """Show contact info for DM"""
    lang = detect_lang(callback)

    short_id = callback.data.replace("mc_", "")

    proposal = await meetup_repo.get_by_short_id(short_id)
    if not proposal:
        await callback.answer("Proposal not found", show_alert=True)
        return

    # Determine who the partner is
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM, str(callback.from_user.id)
    )
    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    if user.id == proposal.proposer_id:
        partner = await user_service.get_user(proposal.receiver_id)
    else:
        partner = await user_service.get_user(proposal.proposer_id)

    if not partner or not partner.username:
        await callback.answer(
            "Partner has no username set" if lang == "en"
            else "У партнёра не указан username",
            show_alert=True,
        )
        return

    # Build message for DM
    topics_text = ""
    if proposal.ai_topics:
        topics_text = "\n".join([f"• {t}" for t in proposal.ai_topics])

    dm_text = (
        f"Hey! We matched and I'd love to chat.\n\n"
        f"Meetup: {_format_time_slot(proposal.accepted_time_slot if proposal.accepted_time_slot is not None else proposal.time_slots[0])} @ {proposal.location}\n"
    )
    if topics_text:
        dm_text += f"\nTopics:\n{topics_text}"

    await callback.answer(
        f"Message @{partner.username} on Telegram!"
        if lang == "en" else
        f"Напиши @{partner.username} в Telegram!",
        show_alert=True,
    )
