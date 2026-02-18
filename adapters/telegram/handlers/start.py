"""
Start handler - /start command and main menu.
Fast, friendly, conversational.
Multilingual: English default, Russian supported.
"""

import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext

from core.domain.models import MessagePlatform
from core.domain.constants import get_interest_display, get_goal_display
from adapters.telegram.loader import user_service, event_service, bot, meetup_repo
from adapters.telegram.keyboards import (
    get_main_menu_keyboard,
    get_join_event_keyboard,
    get_back_to_menu_keyboard,
    get_profile_with_edit_keyboard,
)
from adapters.telegram.states import OnboardingStates
from adapters.telegram.config import ONBOARDING_VERSION
from core.utils.language import detect_lang

router = Router()


async def _increment_referral_count(referrer_telegram_id: str):
    """Increment referral_count for the referrer user."""
    from infrastructure.database.supabase_client import supabase
    try:
        # Get current count
        resp = supabase.table("users").select("referral_count").eq(
            "platform_user_id", referrer_telegram_id
        ).eq("platform", "telegram").execute()

        if resp.data:
            current = resp.data[0].get("referral_count", 0) or 0
            supabase.table("users").update(
                {"referral_count": current + 1}
            ).eq("platform_user_id", referrer_telegram_id).eq("platform", "telegram").execute()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to increment referral count: {e}")


@router.message(CommandStart(deep_link=True))
async def start_with_deep_link(message: Message, command: CommandObject, state: FSMContext):
    """Handle /start with deep link (QR code entry)"""
    args = command.args

    # Get or create user
    try:
        user = await user_service.get_or_create_user(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id=str(message.from_user.id),
            username=message.from_user.username,
            first_name=message.from_user.first_name
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to get/create user (deep link): {e}", exc_info=True)
        lang = detect_lang(message)
        await message.answer(
            "⚠️ Something went wrong connecting to the server. Please try again in a minute."
            if lang == "en" else
            "⚠️ Ошибка подключения к серверу. Попробуй через минуту."
        )
        return

    # Handle vibe check deep link: vibe_<short_code>
    if args and args.startswith("vibe_"):
        short_code = args[5:]  # strip "vibe_" prefix
        from adapters.telegram.handlers.vibe_check import handle_vibe_deep_link
        await handle_vibe_deep_link(message, state, short_code)
        return

    # Handle referral deep link (no event): ref_<tg_id>
    if args and args.startswith("ref_") and not args.startswith("ref_event"):
        referrer_tg_id = args.replace("ref_", "")
        if not user.onboarding_completed and referrer_tg_id:
            try:
                await user_service.update_user(
                    platform=MessagePlatform.TELEGRAM,
                    platform_user_id=str(message.from_user.id),
                    referred_by=referrer_tg_id
                )
                await _increment_referral_count(referrer_tg_id)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Referral tracking failed: {e}")
        # Continue to normal /start flow
        await start_command(message, state)
        return

    # Check if deep link is for event
    if args and args.startswith("event_"):
        raw_code = args.replace("event_", "")

        # Parse referral: event_SXN_ref_44420077 → event=SXN, referrer=44420077
        referrer_tg_id = None
        if "_ref_" in raw_code:
            parts = raw_code.split("_ref_")
            event_code = parts[0]
            referrer_tg_id = parts[1] if len(parts) > 1 else None
        else:
            event_code = raw_code

        # Track referral for new users
        if referrer_tg_id and not user.onboarding_completed:
            try:
                await user_service.update_user(
                    platform=MessagePlatform.TELEGRAM,
                    platform_user_id=str(message.from_user.id),
                    referred_by=referrer_tg_id
                )
                await _increment_referral_count(referrer_tg_id)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Referral tracking failed: {e}")
        event = await event_service.get_event_by_code(event_code)

        if event:
            lang = detect_lang(message)
            if not user.onboarding_completed:
                # Start onboarding with event context
                if ONBOARDING_VERSION == "agent":
                    from adapters.telegram.handlers.onboarding_agent import start_agent_onboarding
                    await start_agent_onboarding(
                        message, state,
                        event_name=event.name,
                        event_code=event_code
                    )
                elif ONBOARDING_VERSION == "intent":
                    from adapters.telegram.handlers.onboarding_intent import start_intent_onboarding
                    await start_intent_onboarding(
                        message, state,
                        event_name=event.name,
                        event_code=event_code
                    )
                elif ONBOARDING_VERSION == "audio":
                    from adapters.telegram.handlers.onboarding_audio import start_audio_onboarding
                    await start_audio_onboarding(
                        message, state,
                        event_name=event.name,
                        event_code=event_code
                    )
                elif ONBOARDING_VERSION == "v2":
                    from adapters.telegram.handlers.onboarding_v2 import start_conversational_onboarding
                    await start_conversational_onboarding(
                        message, state,
                        event_name=event.name,
                        event_code=event_code
                    )
                else:
                    # Legacy v1 flow
                    await state.update_data(pending_event=event_code, language=lang)
                    if lang == "ru":
                        text = f"👋 Привет! Ты на <b>{event.name}</b>\n\nДавай познакомимся! Как тебя зовут?"
                    else:
                        text = f"👋 Hi! You're at <b>{event.name}</b>\n\nLet's get to know each other! What's your name?"
                    await message.answer(text)
                    await state.set_state(OnboardingStates.waiting_name)
            else:
                if lang == "ru":
                    text = f"🎉 <b>{event.name}</b>\n\n📍 {event.location or ''}\n\nПрисоединяйся!"
                else:
                    text = f"🎉 <b>{event.name}</b>\n\n📍 {event.location or ''}\n\nJoin the event!"
                await message.answer(text, reply_markup=get_join_event_keyboard(event_code))
        else:
            lang = detect_lang(message)
            await message.answer("Event not found 😕" if lang == "en" else "Ивент не найден 😕")
    else:
        await start_command(message, state)


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Handle regular /start - quick and friendly. Clears any stuck state."""
    # Always clear previous state to unstick users
    await state.clear()

    lang = detect_lang(message)

    try:
        user = await user_service.get_or_create_user(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id=str(message.from_user.id),
            username=message.from_user.username,
            first_name=message.from_user.first_name
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to get/create user: {e}", exc_info=True)
        await message.answer(
            "⚠️ Something went wrong connecting to the server. Please try again in a minute."
            if lang == "en" else
            "⚠️ Ошибка подключения к серверу. Попробуй через минуту."
        )
        return

    if user.onboarding_completed:
        name = user.display_name or message.from_user.first_name or ("friend" if lang == "en" else "друг")
        text = f"👋 {name}!\n\n" + ("What would you like to do?" if lang == "en" else "Что делаем?")
        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
    else:
        # Start onboarding
        if ONBOARDING_VERSION == "agent":
            from adapters.telegram.handlers.onboarding_agent import start_agent_onboarding
            await start_agent_onboarding(message, state)
        elif ONBOARDING_VERSION == "intent":
            from adapters.telegram.handlers.onboarding_intent import start_intent_onboarding
            await start_intent_onboarding(message, state)
        elif ONBOARDING_VERSION == "audio":
            from adapters.telegram.handlers.onboarding_audio import start_audio_onboarding
            await start_audio_onboarding(message, state)
        elif ONBOARDING_VERSION == "v2":
            from adapters.telegram.handlers.onboarding_v2 import start_conversational_onboarding
            await start_conversational_onboarding(message, state)
        else:
            # Legacy v1 flow
            await state.update_data(language=lang)
            if lang == "ru":
                text = "👋 Привет! Я помогу найти интересных людей.\n\nКак тебя зовут?"
            else:
                text = "👋 Hi! I help you find interesting people to meet.\n\nWhat's your name?"
            await message.answer(text)
            await state.set_state(OnboardingStates.waiting_name)


@router.message(Command("stats_url"))
async def stats_url_command(message: Message):
    """Show the stats dashboard URL (admin only)."""
    from config.settings import settings
    if message.from_user.id not in settings.admin_telegram_ids:
        await message.answer("Admin only")
        return

    import os
    stats_token = os.environ.get("STATS_TOKEN", "")
    if not stats_token:
        await message.answer("STATS_TOKEN not set — token was auto-generated. Check Railway logs for the URL.")
        return

    port = os.environ.get("PORT", "8080")
    # On Railway the public URL is the service domain
    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    if railway_domain:
        url = f"https://{railway_domain}/stats?token={stats_token}"
    else:
        url = f"http://localhost:{port}/stats?token={stats_token}"

    await message.answer(f"<b>Stats Dashboard</b>\n\n<code>{url}</code>", parse_mode="HTML")


@router.message(Command("menu"))
async def menu_command(message: Message):
    """Show main menu"""
    lang = detect_lang(message)
    text = "What would you like to do?" if lang == "en" else "Что делаем?"
    await message.answer(text, reply_markup=get_main_menu_keyboard(lang))


@router.message(Command("help"))
async def help_command(message: Message):
    """Show help - short and clear"""
    lang = detect_lang(message)
    if lang == "ru":
        text = (
            "<b>Sphere</b> — умные знакомства на ивентах\n\n"
            "📱 Сканируй QR → получай матчи → общайся\n\n"
            "/start — начать\n"
            "/menu — меню\n"
            "/demo — интерактивный тур\n"
            "/reset — сбросить профиль"
        )
    else:
        text = (
            "<b>Sphere</b> — smart networking at events\n\n"
            "📱 Scan QR → get matches → connect\n\n"
            "/start — start\n"
            "/menu — menu\n"
            "/demo — interactive walkthrough\n"
            "/reset — reset profile"
        )
    await message.answer(text)


@router.message(Command("reset"))
async def reset_command(message: Message, state: FSMContext):
    """Full reset of user profile for testing"""
    from config.settings import settings

    lang = detect_lang(message)
    user_id = str(message.from_user.id)

    # Check if admin or debug mode
    is_admin = message.from_user.id in settings.admin_telegram_ids
    is_debug = settings.debug

    if not is_admin and not is_debug:
        text = "⛔ Admin only command" if lang == "en" else "⛔ Команда доступна только админам"
        await message.answer(text)
        return

    # FULL profile reset - clear all fields using dedicated reset method
    await user_service.reset_user(MessagePlatform.TELEGRAM, user_id)

    # Clear FSM state
    await state.clear()

    if lang == "ru":
        text = "🔄 Профиль полностью очищен!\n\nВсе данные удалены. Напиши /start чтобы начать заново."
    else:
        text = "🔄 Profile fully reset!\n\nAll data cleared. Type /start to begin again."
    await message.answer(text)


@router.message(Command("demo"))
async def demo_command(message: Message):
    """
    Interactive demo - walks through all bot features automatically.
    Great for presentations and onboarding new users.
    """
    import asyncio

    # Demo data — themed for SXN event
    demo_profile = {
        "name": "Alex Lindholm",
        "profession": "Founder & CEO",
        "company": "InspireXchange",
        "bio": "Building LoveTech products. 10 years in dating industry. Investor in 3 social apps.",
        "looking_for": "Product designers, investors, dating app founders",
        "can_help": "Business models, monetization, LoveTech market insights",
        "interests": ["LoveTech", "Dating Apps", "Startups", "Product"],
    }

    demo_match = {
        "name": "Song Kim",
        "profession": "Founder & CEO",
        "company": "Zeya Social",
        "bio": "Building the anti-dating app. Connecting people through real experiences, not swipes.",
        "score": 0.91,
        "reason": "Both are founders in the dating/social space with complementary visions — Alex focuses on business models while Song is reimagining the product side. Perfect for a strategic conversation.",
        "icebreaker": "Song, I loved your take on why dating apps are broken — I've been experimenting with alternative business models for LoveTech. Would love to compare notes!",
    }

    # Step 1: Welcome
    await message.answer(
        "🎬 <b>SPHERE DEMO</b>\n\n"
        "Welcome! I'll show you how Sphere works at tonight's event.\n"
        "This is a quick interactive walkthrough.\n\n"
        "<i>Starting in 2 seconds...</i>"
    )
    await asyncio.sleep(2)

    # Step 2: QR Scan simulation
    await message.answer(
        "📱 <b>Step 1: Scan QR at Event</b>\n\n"
        "You scan the QR code at the venue — it brings you here.\n"
        "Tonight's event code: <code>SXN</code>\n\n"
        "Deep link:\n"
        "<code>t.me/Spheresocial_bot?start=event_SXN</code>"
    )
    await asyncio.sleep(3)

    # Step 3: Onboarding
    await message.answer(
        "🎤 <b>Step 2: Quick Voice Intro (30-60 sec)</b>\n\n"
        "Record a voice message about yourself:\n\n"
        "   🙋 <i>Who are you and what do you do?</i>\n"
        "   🔍 <i>What kind of people do you want to meet?</i>\n"
        "   💡 <i>How can you help others?</i>\n\n"
        "<i>AI extracts your profile automatically from voice...</i>"
    )
    await asyncio.sleep(3)

    # Step 4: Profile created
    profile_text = f"""✅ <b>Step 3: Profile Created</b>

<b>{demo_profile['name']}</b>
💼 {demo_profile['profession']} @ {demo_profile['company']}

{demo_profile['bio']}

<b>🔍 Looking for:</b>
{demo_profile['looking_for']}

<b>💡 Can help with:</b>
{demo_profile['can_help']}

#{' #'.join(demo_profile['interests'])}

<i>All extracted automatically from your voice!</i>"""

    await message.answer(profile_text)
    await asyncio.sleep(4)

    # Step 5: Matching
    await message.answer(
        "🔄 <b>Step 4: AI Matching</b>\n\n"
        "Our AI analyzes all participants:\n"
        "• Semantic similarity between profiles\n"
        "• Deep compatibility analysis with GPT-4\n"
        "• Who can help whom — mutual value exchange\n\n"
        "⏳ <i>Usually takes 10-15 seconds...</i>"
    )
    await asyncio.sleep(3)

    # Step 6: Match found
    match_text = f"""💫 <b>Step 5: Match Found!</b>

<b>{demo_match['name']}</b>  •  @songkim
💼 {demo_match['profession']} @ {demo_match['company']}

{demo_match['bio']}

#DatingApps #Social #Startups #Product

────────────────────

<b>✨ Why this match</b>
<i>{demo_match['reason']}</i>

<b>💬 Start with</b>
<i>{demo_match['icebreaker']}</i>

<b>Score:</b> {demo_match['score']:.0%} compatibility
📍 You're both here!"""

    await message.answer(match_text)
    await asyncio.sleep(4)

    # Step 7: Match notification (what the other person sees)
    await message.answer(
        "🔔 <b>Step 6: Match Notification</b>\n\n"
        "<i>This is what your match receives at the same time:</i>"
    )
    await asyncio.sleep(1.5)

    notification_text = (
        f"<b>You have a new match!</b>\n\n"
        f"Meet <b>{demo_profile['name']}</b>\n\n"
        f"<i>{demo_match['reason']}</i>\n\n"
        f"<b>Start with:</b> {demo_match['icebreaker']}"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder as DemoBuilder
    notif_kb = DemoBuilder()
    notif_kb.button(text="💬 Write @alexlindholm", callback_data="demo_noop")
    notif_kb.button(text="👤 View Profile", callback_data="demo_noop")
    notif_kb.button(text="⚡ AI Speed Dating", callback_data="demo_noop")
    notif_kb.adjust(1)

    await message.answer(notification_text, reply_markup=notif_kb.as_markup())
    await asyncio.sleep(4)

    # Step 8: Features overview
    await message.answer(
        "⚡ <b>More Features</b>\n\n"
        "• <b>AI Speed Dating</b> — preview a simulated conversation with your match\n"
        "• <b>Deep Link Chat</b> — tap to open a DM directly in Telegram\n"
        "• <b>Profile Edit</b> — just type what to change, AI updates it\n"
        "• <b>Feedback</b> — rate matches 👍/👎 to improve recommendations\n\n"
        "🎁 <b>Tonight's bonus:</b> successful matches enter a draw for a <b>free dinner date from Sphere</b> in Warsaw!"
    )
    await asyncio.sleep(4)

    # Step 9: CTA
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Try it now!", callback_data="start_real_onboarding")
    builder.button(text="📋 Main Menu", callback_data="back_to_menu")
    builder.adjust(1)

    await message.answer(
        "🎉 <b>That's Sphere!</b>\n\n"
        "Smart networking powered by AI.\n"
        "No more awkward small talk — we match you with the right people.\n\n"
        "Ready to create your profile?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "demo_noop")
async def demo_noop_handler(callback: CallbackQuery):
    """Demo buttons — just acknowledge"""
    await callback.answer("This is a demo preview", show_alert=False)


@router.callback_query(F.data == "start_real_onboarding")
async def start_real_onboarding_from_demo(callback: CallbackQuery, state: FSMContext):
    """Start real onboarding after demo.
    Note: callback.message.from_user is the bot, not the user.
    We patch first_name from callback.from_user so onboarding identifies the real user.
    """
    from adapters.telegram.config import ONBOARDING_VERSION

    # Patch: callback.message.from_user is the bot. Override with real user info.
    msg = callback.message
    msg.from_user = callback.from_user

    if ONBOARDING_VERSION == "agent":
        from adapters.telegram.handlers.onboarding_agent import start_agent_onboarding
        await start_agent_onboarding(msg, state)
    elif ONBOARDING_VERSION == "audio":
        from adapters.telegram.handlers.onboarding_audio import start_audio_onboarding
        await start_audio_onboarding(msg, state)
    else:
        from adapters.telegram.handlers.onboarding_v2 import start_conversational_onboarding
        await start_conversational_onboarding(msg, state)

    await callback.answer()


# === MAIN MENU CALLBACKS ===

# detect_lang works for both Message and CallbackQuery
detect_lang_callback = detect_lang


@router.callback_query(F.data == "giveaway_info")
async def giveaway_info(callback: CallbackQuery):
    """Show Giveaway rules"""
    lang = detect_lang_callback(callback)

    if lang == "ru":
        text = (
            "🎁 <b>Sphere Giveaway</b>\n\n"
            "Собери шансы и выиграй Date Dinner в топовом ресторане Варшавы!\n\n"
            '✅ 1 шанс — зарегистрируйся в Sphere\n'
            '🎟🎟🎟🎟🎟 +5 шансов — репост Stories с <a href="https://www.instagram.com/sphere.match">@sphere.match</a>\n'
            '🎟🎟🎟 +3 шанса — приведи друга, каждый считается!\n'
            '🎟🎟 +2 шанса — оцени свой match\n\n'
            "Удачи! 🍀"
        )
    else:
        text = (
            "🎁 <b>Sphere Giveaway</b>\n\n"
            "Collect chances and win a Date Dinner in top Warsaw dining place!\n\n"
            '✅ 1 chance — register in Sphere\n'
            '🎟🎟🎟🎟🎟 +5 chances — repost Stories with <a href="https://www.instagram.com/sphere.match">@sphere.match</a>\n'
            '🎟🎟🎟 +3 chances — refer a friend, each friend counts!\n'
            '🎟🎟 +2 chances — rate your match\n\n'
            "Good luck! 🍀"
        )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Refer a Friend", callback_data="refer_a_friend")
    builder.button(text="← Menu" if lang == "en" else "← Меню", callback_data="back_to_menu")
    builder.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "refer_a_friend")
async def refer_a_friend(callback: CallbackQuery):
    """Show Refer a Friend page with referral link (no QR, no event deep link)"""
    lang = detect_lang_callback(callback)
    user_tg_id = callback.from_user.id

    bot_username = os.getenv("BOT_USERNAME", "Spheresocial_bot")
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_tg_id}"

    if lang == "ru":
        text = (
            "🔥 <b>Сделай свои матчи точнее</b>\n\n"
            "Sphere становится умнее с каждым новым участником.\n"
            "Сейчас мы особенно ищем людей из:\n\n"
            "🤖 AI & Tech · 🚀 Venture & Startups\n"
            "🪙 Crypto & Web3 · 🎨 Creative & Design\n"
            "🧬 Health & Biohacking · 📊 Finance & Trading\n\n"
            "Знаешь кого-то интересного из этих миров?\n"
            "Пригласи их — качество твоих матчей вырастет.\n\n"
            "🎟🎟🎟 +3 шанса в Giveaway за каждого друга!\n\n"
            f"Отправь эту магическую ссылку:\n<a href=\"{ref_link}\">{ref_link}</a>"
        )
    else:
        text = (
            "🔥 <b>Make your matches sharper</b>\n\n"
            "Sphere gets smarter with every person who joins.\n"
            "Right now we're especially looking for people in:\n\n"
            "🤖 AI & Tech · 🚀 Venture & Startups\n"
            "🪙 Crypto & Web3 · 🎨 Creative & Design\n"
            "🧬 Health & Biohacking · 📊 Finance & Trading\n\n"
            "Know someone interesting from these worlds?\n"
            "Invite them — your match quality goes up.\n\n"
            "🎟🎟🎟 +3 chances in the Giveaway per friend!\n\n"
            f"Share this magic link:\n<a href=\"{ref_link}\">{ref_link}</a>"
        )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Back", callback_data="giveaway_info")
    builder.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup(), disable_web_page_preview=True)

    await callback.answer()


# === INVITATIONS ===

@router.callback_query(F.data == "my_invitations")
async def show_invitations(callback: CallbackQuery):
    """Show pending meetup invitations received by this user."""
    lang = detect_lang_callback(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM, str(callback.from_user.id)
    )
    if not user:
        await callback.answer("Profile not found", show_alert=True)
        return

    invitations = await meetup_repo.get_received_pending(user.id)

    # Filter out expired
    invitations = [inv for inv in invitations if not meetup_repo.is_expired(inv)]

    if not invitations:
        text = (
            "<b>📩 Invitations</b>\n\n"
            "No pending invitations right now.\n"
            "When someone sends you a meetup proposal, it will appear here!"
            if lang == "en" else
            "<b>📩 Приглашения</b>\n\n"
            "Нет активных приглашений.\n"
            "Когда кто-то отправит тебе предложение встречи, оно появится здесь!"
        )
        await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard(lang))
        await callback.answer()
        return

    # Show each invitation with accept/decline buttons
    text = (
        f"<b>📩 Invitations ({len(invitations)})</b>\n\n"
        if lang == "en" else
        f"<b>📩 Приглашения ({len(invitations)})</b>\n\n"
    )

    await callback.message.edit_text(text.strip(), reply_markup=get_back_to_menu_keyboard(lang))
    await callback.answer()

    # Send each invitation as a separate message with buttons
    from adapters.telegram.keyboards.inline import get_meetup_receiver_keyboard
    for inv in invitations:
        proposer = await user_service.get_user(inv.proposer_id)
        proposer_name = (proposer.display_name or proposer.first_name or "Someone") if proposer else "Someone"

        times_str = ", ".join([
            ("Anytime" if lang == "en" else "Любое время") if m == 0 else f"{m} min"
            for m in inv.time_slots
        ])

        inv_text = (
            f"<b>☕ {proposer_name}</b> wants to meet!\n"
            f"{'─' * 20}\n"
        )
        if inv.ai_why_meet:
            inv_text += f"\n<i>{inv.ai_why_meet}</i>\n"
        if inv.ai_topics:
            inv_text += "\n<b>Topics:</b>\n"
            for i, topic in enumerate(inv.ai_topics, 1):
                inv_text += f"  {i}. {topic}\n"
        inv_text += (
            f"\n<b>Time:</b> {times_str}\n"
            f"<b>Location:</b> {inv.location}\n"
        )

        try:
            await bot.send_message(
                callback.message.chat.id,
                inv_text,
                reply_markup=get_meetup_receiver_keyboard(inv.short_id, inv.time_slots, lang),
                parse_mode="HTML"
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to send invitation card {inv.short_id}: {e}")


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Return to main menu"""
    # Delete profile photo message if it exists
    data = await state.get_data()
    photo_msg_id = data.get("profile_photo_msg_id")
    if photo_msg_id:
        try:
            await bot.delete_message(callback.message.chat.id, photo_msg_id)
        except Exception:
            pass

    # Clear any active FSM state
    await state.clear()

    lang = detect_lang_callback(callback)
    text = "What would you like to do?" if lang == "en" else "Что делаем?"

    # Get pending invitations count for badge
    pending_inv = 0
    try:
        user = await user_service.get_user_by_platform(
            MessagePlatform.TELEGRAM, str(callback.from_user.id)
        )
        if user:
            invitations = await meetup_repo.get_received_pending(user.id)
            pending_inv = len([inv for inv in invitations if not meetup_repo.is_expired(inv)])
    except Exception:
        pass

    # Handle photo messages (from profile view or refer QR)
    if callback.message.photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await bot.send_message(
            callback.message.chat.id, text,
            reply_markup=get_main_menu_keyboard(lang, pending_invitations=pending_inv),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=get_main_menu_keyboard(lang, pending_invitations=pending_inv)
        )
    await callback.answer()


@router.callback_query(F.data == "my_profile")
async def show_profile(callback: CallbackQuery, state: FSMContext):
    """Show user profile - detailed with hashtags"""
    lang = detect_lang_callback(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer("Profile not found" if lang == "en" else "Профиль не найден", show_alert=True)
        return

    # Build beautiful profile display
    name = user.display_name or user.first_name or ("Anonymous" if lang == "en" else "Аноним")

    # Header with name and contact
    text = f"<b>{name}</b>"
    if user.username:
        text += f"  •  @{user.username}"
    text += "\n"

    # City
    if user.city_current:
        text += f"📍 {user.city_current}\n"

    # Bio - the main description
    if user.bio:
        text += f"\n{user.bio}\n"

    # Interests as hashtags - compact
    if user.interests:
        hashtags = " ".join([f"#{i}" for i in user.interests[:5]])
        text += f"\n{hashtags}\n"

    # Divider
    text += "\n" + "─" * 20 + "\n"

    # Looking for - what they want (key for matching!)
    if user.looking_for:
        label = "🔍 Looking for" if lang == "en" else "🔍 Ищу"
        text += f"\n<b>{label}</b>\n{user.looking_for}\n"

    # Can help with - their value prop
    if user.can_help_with:
        label = "💡 Can help with" if lang == "en" else "💡 Могу помочь"
        text += f"\n<b>{label}</b>\n{user.can_help_with}\n"

    # Goals - compact at bottom
    if user.goals:
        goals_display = " • ".join([get_goal_display(g, lang) for g in user.goals[:3]])
        text += f"\n🎯 {goals_display}\n"

    # Photo status - subtle
    if not user.photo_url:
        add_photo = "📸 Add photo to help matches find you" if lang == "en" else "📸 Добавь фото, чтобы тебя узнали"
        text += f"\n<i>{add_photo}</i>"

    # Inline edit hint
    hint = (
        "\n\n<i>💡 Просто напиши что изменить, например:\n"
        "\"добавь crypto в интересы\" или \"ищу инвесторов\"</i>"
        if lang == "ru" else
        "\n\n<i>💡 Just type what to change, e.g.:\n"
        "\"add crypto to interests\" or \"looking for investors\"</i>"
    )
    text += hint

    # Show photo if available
    if user.photo_url:
        try:
            await callback.message.delete()
            photo_msg = await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=user.photo_url,
                caption=f"👤 {name}"
            )
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=get_profile_with_edit_keyboard(lang)
            )
            # Save photo message ID so we can delete it when leaving profile
            from adapters.telegram.states.onboarding import ProfileEditStates
            await state.set_state(ProfileEditStates.viewing_profile)
            await state.update_data(language=lang, profile_photo_msg_id=photo_msg.message_id)
            await callback.answer()
            return
        except Exception:
            await callback.message.edit_text(text, reply_markup=get_profile_with_edit_keyboard(lang))
    else:
        await callback.message.edit_text(text, reply_markup=get_profile_with_edit_keyboard(lang))

    # Set state so typing auto-edits profile
    from adapters.telegram.states.onboarding import ProfileEditStates
    await state.set_state(ProfileEditStates.viewing_profile)
    await state.update_data(language=lang)

    await callback.answer()


@router.callback_query(F.data == "my_events")
async def show_events(callback: CallbackQuery):
    """Show user's events with mode toggle"""
    from adapters.telegram.keyboards.inline import get_events_keyboard

    lang = detect_lang_callback(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    events = await event_service.get_user_events(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    # Current mode
    mode = getattr(user, 'matching_mode', 'event') or 'event' if user else 'event'

    if lang == "ru":
        mode_text = "🎉 Event" if mode == "event" else "🏙️ Sphere City"
        text = f"<b>Режим матчинга:</b> {mode_text}\n\n"
    else:
        mode_text = "🎉 Event" if mode == "event" else "🏙️ Sphere City"
        text = f"<b>Matching mode:</b> {mode_text}\n\n"

    if not events:
        if lang == "ru":
            text += "Пока нет ивентов.\nСканируй QR-коды чтобы присоединиться!"
        else:
            text += "No events yet.\nScan QR codes to join!"
    else:
        text += "<b>Your events:</b>\n\n" if lang == "en" else "<b>Твои ивенты:</b>\n\n"
        for event in events[:5]:
            text += f"• {event.name}\n"

    try:
        await callback.message.edit_text(text, reply_markup=get_events_keyboard(mode, lang))
    except Exception:
        pass  # "message is not modified" is harmless
    await callback.answer()


@router.callback_query(F.data == "my_matches")
async def show_matches(callback: CallbackQuery, state: FSMContext):
    """Show matches — defaults to Sphere City (city-based matching)"""
    from adapters.telegram.handlers.sphere_city import sphere_city_entry

    lang = detect_lang_callback(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer()
        await callback.message.edit_text(
            "Profile not found" if lang == "en" else "Профиль не найден"
        )
        return

    # Route to Sphere City (handles its own callback.answer)
    await sphere_city_entry(callback, state)


@router.callback_query(F.data == "vibe_check")
async def vibe_check_entry(callback: CallbackQuery, state: FSMContext):
    """Vibe Check — coming soon in v1.1."""
    lang = detect_lang_callback(callback)
    if lang == "ru":
        text = (
            "🔮 <b>Check Our Vibe</b>\n\n"
            "Эта фича скоро будет доступна!\n"
            "Ты сможешь проверить совместимость с любым человеком через AI-интервью."
        )
    else:
        text = (
            "🔮 <b>Check Our Vibe</b>\n\n"
            "This feature is coming soon!\n"
            "You'll be able to check your compatibility with anyone through an AI interview."
        )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="← Menu" if lang == "en" else "← Меню", callback_data="back_to_menu")
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "agent_chat")
async def agent_chat_entry(callback: CallbackQuery, state: FSMContext):
    """Start AI agent chat from main menu."""
    await callback.answer()
    lang = detect_lang_callback(callback)

    from adapters.telegram.handlers.agent_chat import start_agent_chat
    await start_agent_chat(callback, state, lang=lang)


@router.callback_query(F.data == "toggle_matching_mode")
async def toggle_matching_mode(callback: CallbackQuery):
    """Toggle between event and city matching modes"""
    lang = detect_lang_callback(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        msg = "Profile not found" if lang == "en" else "Профиль не найден"
        await callback.answer(msg, show_alert=True)
        return

    current_mode = getattr(user, 'matching_mode', 'event') or 'event'
    new_mode = "city" if current_mode == "event" else "event"

    # If switching to city mode and no city set, ask for city first
    if new_mode == "city" and not user.city_current:
        from adapters.telegram.handlers.sphere_city import sphere_city_entry
        # Set mode first, then ask for city
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            str(callback.from_user.id),
            matching_mode=new_mode
        )
        await sphere_city_entry(callback, None)
        return

    # Update mode
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id),
        matching_mode=new_mode
    )

    # Show confirmation and refresh events view
    if lang == "ru":
        msg = "🏙️ Режим: Sphere City" if new_mode == "city" else "🎉 Режим: Event"
    else:
        msg = "🏙️ Mode: Sphere City" if new_mode == "city" else "🎉 Mode: Event"

    await callback.answer(msg)

    # Refresh the events screen
    await show_events(callback)


# === FALLBACK FOR OLD/STALE CALLBACKS ===
# Note: Audio callbacks (audio_ready, audio_confirm, etc.) are handled by onboarding_audio.py
# Only catch them here if user is NOT in any onboarding state

@router.callback_query(F.data.in_(["audio_ready", "audio_confirm", "audio_retry", "audio_add_details", "switch_to_text"]))
async def stale_audio_callback(callback: CallbackQuery, state: FSMContext):
    """Handle clicks on old audio onboarding buttons - only when NOT in onboarding"""
    current_state = await state.get_state()

    # If user is in any onboarding state, don't handle here - let onboarding handlers do it
    if current_state and ("AudioOnboarding" in current_state or "Onboarding" in current_state):
        return  # Let the actual onboarding handler process this

    # Otherwise it's a stale button
    lang = detect_lang_callback(callback)
    msg = "This button expired. Type /start" if lang == "en" else "Эта кнопка устарела. Напиши /start"
    await callback.answer(msg, show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass


# === CATCH-ALL: Users stuck without active state ===

@router.message(StateFilter(None), F.text)
async def catch_stuck_user(message: Message, state: FSMContext):
    """Handle messages from users with no active FSM state.
    If onboarding not completed — prompt to restart. Otherwise show menu."""
    # Skip commands — they have their own handlers
    if message.text and message.text.startswith("/"):
        return

    lang = detect_lang(message)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )

    if not user or not user.onboarding_completed:
        # User hasn't finished onboarding
        text = (
            "Похоже ты не завершил регистрацию.\n"
            "Нажми /start чтобы начать заново!"
        ) if lang == "ru" else (
            "Looks like you haven't finished setting up.\n"
            "Tap /start to begin!"
        )
        await message.answer(text)
    else:
        # User completed onboarding but sent random text
        text = "What would you like to do?" if lang == "en" else "Что делаем?"
        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))


@router.message(StateFilter(None))
async def catch_any_content(message: Message, state: FSMContext):
    """Catch-all for non-text content (photos, stickers, voice, video, etc.)
    when user has no active FSM state. Routes to a helpful response."""
    lang = detect_lang(message)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )

    if not user or not user.onboarding_completed:
        text = (
            "Похоже ты не завершил регистрацию.\n"
            "Нажми /start чтобы начать заново!"
        ) if lang == "ru" else (
            "Looks like you haven't finished setting up.\n"
            "Tap /start to begin!"
        )
        await message.answer(text)
        return

    # Determine what type was sent and guide the user
    if message.voice:
        hint = ("Чтобы обновить профиль голосом, нажми ✏️ Edit в профиле."
                if lang == "ru" else
                "To update your profile by voice, tap Edit in your profile.")
    elif message.photo:
        hint = ("Чтобы обновить фото, нажми ✏️ Edit в профиле."
                if lang == "ru" else
                "To update your photo, tap Edit in your profile.")
    elif message.sticker:
        hint = "😄" if lang == "ru" else "😄"
        await message.answer(hint)
        return
    else:
        hint = ("Что делаем?" if lang == "ru" else "What would you like to do?")

    await message.answer(hint, reply_markup=get_main_menu_keyboard(lang))
