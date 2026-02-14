"""
Vibe Check Handler — AI Compatibility Game.

Flow:
1. User A creates vibe check -> gets shareable link
2. AI interviews User A (5-7 fun questions)
3. User B opens link -> AI interviews User B
4. Both complete -> AI generates compatibility report -> both receive it

Viral loop: shareable link, fun result, drives new users.
"""

import asyncio
import json
import os
import re
import logging
import secrets
import string
from datetime import datetime, timezone
from uuid import UUID

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from core.domain.models import MessagePlatform
from adapters.telegram.loader import user_service, bot, voice_service
from adapters.telegram.keyboards import (
    get_main_menu_keyboard,
    get_back_to_menu_keyboard,
    get_vibe_share_keyboard,
    get_vibe_result_keyboard,
    get_vibe_waiting_keyboard,
)
from adapters.telegram.states import VibeCheckStates
from core.utils.language import detect_lang, get_language_name
from core.prompts.vibe_check import (
    VIBE_INTERVIEW_PROMPT,
    VIBE_INTERVIEW_EXTRACTION_PROMPT,
    VIBE_COMPATIBILITY_PROMPT,
)
from infrastructure.database.supabase_client import supabase, run_sync
from config.settings import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
router = Router()

# OpenAI client for vibe check conversations
_ai_client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)

MAX_VIBE_TURNS = 7
MIN_VIBE_TURNS = 5


# ============================================
# DATABASE HELPERS
# ============================================

def _generate_short_code(length: int = 6) -> str:
    """Generate a short alphanumeric code for deep links."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


@run_sync
def _create_vibe_check_sync(short_code: str, initiator_id: str) -> dict:
    resp = supabase.table("vibe_checks").insert({
        "short_code": short_code,
        "initiator_id": initiator_id,
    }).execute()
    return resp.data[0] if resp.data else None


@run_sync
def _get_vibe_by_code_sync(short_code: str) -> dict:
    resp = supabase.table("vibe_checks").select("*").eq(
        "short_code", short_code
    ).execute()
    return resp.data[0] if resp.data else None


@run_sync
def _update_vibe_check_sync(vibe_id: str, data: dict) -> dict:
    resp = supabase.table("vibe_checks").update(data).eq(
        "id", vibe_id
    ).execute()
    return resp.data[0] if resp.data else None


@run_sync
def _get_vibe_by_id_sync(vibe_id: str) -> dict:
    resp = supabase.table("vibe_checks").select("*").eq(
        "id", vibe_id
    ).execute()
    return resp.data[0] if resp.data else None


async def create_vibe_check(initiator_id: str) -> dict:
    for _ in range(5):
        code = _generate_short_code()
        try:
            result = await _create_vibe_check_sync(code, initiator_id)
            if result:
                return result
        except Exception:
            continue
    return None


async def get_vibe_by_code(short_code: str) -> dict:
    return await _get_vibe_by_code_sync(short_code)


async def update_vibe_check(vibe_id: str, data: dict) -> dict:
    return await _update_vibe_check_sync(vibe_id, data)


async def get_vibe_by_id(vibe_id: str) -> dict:
    return await _get_vibe_by_id_sync(vibe_id)


# ============================================
# AI HELPERS
# ============================================

async def _ai_interview_message(
    user_name: str,
    role: str,
    conversation_history: list,
    turn_count: int,
    lang: str,
) -> str:
    history_text = ""
    if conversation_history:
        for msg in conversation_history:
            speaker = "You" if msg["role"] == "assistant" else user_name
            history_text += f"{speaker}: {msg['content']}\n"
    else:
        history_text = "(Starting the conversation -- ask your first question)"

    role_context = (
        "started this vibe check and invited someone"
        if role == "initiator"
        else "were invited to this vibe check by someone"
    )

    prompt = VIBE_INTERVIEW_PROMPT.format(
        language_name=get_language_name(lang),
        user_name=user_name,
        role=role,
        role_context=role_context,
        conversation_history=history_text,
        turn_count=turn_count,
    )

    try:
        response = await _ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Vibe interview AI error: {e}", exc_info=True)
        if lang == "ru":
            return "Отличный ответ! А расскажи, что тебя больше всего вдохновляет в людях?"
        return "Great answer! So tell me, what inspires you most about people?"


async def _extract_personality(conversation: list) -> dict:
    conv_text = "\n".join(
        f"{'AI' if m['role'] == 'assistant' else 'User'}: {m['content']}"
        for m in conversation
    )
    prompt = VIBE_INTERVIEW_EXTRACTION_PROMPT.format(conversation=conv_text)

    try:
        response = await _ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.error(f"Personality extraction failed: {e}", exc_info=True)

    return {}


async def _generate_compatibility(
    name_a: str, data_a: dict, conv_a: list,
    name_b: str, data_b: dict, conv_b: list,
    lang: str,
) -> dict:
    conv_a_text = "\n".join(
        f"{'AI' if m['role'] == 'assistant' else name_a}: {m['content']}"
        for m in conv_a
    )
    conv_b_text = "\n".join(
        f"{'AI' if m['role'] == 'assistant' else name_b}: {m['content']}"
        for m in conv_b
    )

    prompt = VIBE_COMPATIBILITY_PROMPT.format(
        name_a=name_a,
        data_a=json.dumps(data_a, ensure_ascii=False),
        conversation_a=conv_a_text,
        name_b=name_b,
        data_b=json.dumps(data_b, ensure_ascii=False),
        conversation_b=conv_b_text,
        language_name=get_language_name(lang),
    )

    try:
        response = await _ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.7,
        )
        content = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.error(f"Compatibility analysis failed: {e}", exc_info=True)

    return {
        "score": 65,
        "connection_type": "Kindred Spirits",
        "common_ground": ["Both interesting people!"],
        "potential_friction": [],
        "conversation_starter": "What's something unexpected about you?",
        "vibe_summary": "You two have interesting energy!",
    }


def _format_result(result: dict, name_a: str, name_b: str, lang: str) -> str:
    score = result.get("score", 65)
    conn_type = result.get("connection_type", "Kindred Spirits")
    common = result.get("common_ground", [])
    friction = result.get("potential_friction", [])
    starter = result.get("conversation_starter", "")
    summary = result.get("vibe_summary", "")

    text = f"🔮 <b>Vibe Check: {name_a} & {name_b}</b>\n\n"
    text += f"💯 <b>{'Совместимость' if lang == 'ru' else 'Compatibility'}: {score}%</b>\n\n"

    if summary:
        text += f"<i>{summary}</i>\n\n"

    if common:
        header = "🔥 Что вас связывает:" if lang == "ru" else "🔥 What connects you:"
        text += f"<b>{header}</b>\n"
        for item in common[:5]:
            text += f"  • {item}\n"
        text += "\n"

    if friction:
        header = "💡 Возможные трения:" if lang == "ru" else "💡 Potential friction:"
        text += f"<b>{header}</b>\n"
        for item in friction[:3]:
            text += f"  • {item}\n"
        text += "\n"

    conn_label = "🎯 Тип связи" if lang == "ru" else "🎯 Best connection type"
    text += f"<b>{conn_label}:</b> {conn_type}\n\n"

    if starter:
        starter_label = "💬 Начните с:" if lang == "ru" else "💬 Conversation starter:"
        text += f"<b>{starter_label}</b>\n<i>\"{starter}\"</i>"

    return text


# ============================================
# HANDLER: CREATE NEW VIBE CHECK
# ============================================

@router.callback_query(F.data == "vibe_new")
async def create_vibe_check_handler(callback: CallbackQuery, state: FSMContext):
    """Create a new vibe check and start interviewing the initiator."""
    lang = detect_lang(callback)
    await callback.answer()

    try:
        user = await user_service.get_or_create_user(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id=str(callback.from_user.id),
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
    except Exception as e:
        logger.error(f"Failed to get/create user for vibe check: {e}", exc_info=True)
        user = None

    if not user:
        msg = "Something went wrong. Try /start" if lang == "en" else "Что-то пошло не так. Попробуй /start"
        await callback.message.edit_text(msg)
        return

    # Create vibe check
    vibe = await create_vibe_check(str(user.id))
    if not vibe:
        msg = "Could not create vibe check. Try again later." if lang == "en" else "Не удалось создать. Попробуй позже."
        await callback.message.edit_text(msg)
        return

    short_code = vibe["short_code"]
    bot_username = os.getenv("BOT_USERNAME", "Spheresocial_bot")
    link = f"https://t.me/{bot_username}?start=vibe_{short_code}"

    if lang == "ru":
        text = (
            f"🔮 <b>Vibe Check создан!</b>\n\n"
            f"Отправь эту ссылку кому-нибудь, чтобы проверить вашу совместимость:\n\n"
            f"<code>{link}</code>\n\n"
            f"А пока — давай я задам тебе несколько веселых вопросов..."
        )
    else:
        text = (
            f"🔮 <b>Vibe Check created!</b>\n\n"
            f"Share this link with someone to check your compatibility:\n\n"
            f"<code>{link}</code>\n\n"
            f"While you wait — let me ask you a few fun questions..."
        )

    await callback.message.edit_text(text, reply_markup=get_vibe_share_keyboard(short_code, lang))

    # Set FSM state for interview
    await state.set_state(VibeCheckStates.interviewing)
    await state.update_data(
        vibe_id=vibe["id"],
        vibe_code=short_code,
        vibe_role="initiator",
        vibe_history=[],
        vibe_turn_count=0,
        vibe_lang=lang,
    )

    # Send first AI question after a short delay
    await asyncio.sleep(1.5)
    user_name = user.display_name or callback.from_user.first_name or "Friend"
    first_message = await _ai_interview_message(
        user_name=user_name,
        role="initiator",
        conversation_history=[],
        turn_count=0,
        lang=lang,
    )

    await bot.send_message(callback.message.chat.id, first_message)

    await state.update_data(
        vibe_history=[{"role": "assistant", "content": first_message}],
        vibe_turn_count=1,
    )


# ============================================
# HANDLER: DEEP LINK (TARGET USER)
# ============================================

async def handle_vibe_deep_link(message: Message, state: FSMContext, short_code: str):
    """Handle when User B opens a vibe check deep link."""
    lang = detect_lang(message)

    try:
        user = await user_service.get_or_create_user(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id=str(message.from_user.id),
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    except Exception as e:
        logger.error(f"Failed to get/create user for vibe deep link: {e}", exc_info=True)
        user = None

    if not user:
        await message.answer("Something went wrong. Try /start")
        return

    vibe = await get_vibe_by_code(short_code)
    if not vibe:
        not_found = "🔮 Этот Vibe Check не найден или устарел.\n\nЧто делаем?" if lang == "ru" else "🔮 This Vibe Check wasn't found or has expired.\n\nWhat would you like to do?"
        await message.answer(not_found, reply_markup=get_main_menu_keyboard(lang))
        return

    # Can't vibe-check yourself
    if vibe.get("initiator_id") == str(user.id):
        if lang == "ru":
            text = "Ты не можешь проверить совместимость сам с собой! 😄 Отправь ссылку другу."
        else:
            text = "You can't vibe check yourself! 😄 Share the link with someone else."
        await message.answer(text)
        return

    # Check if target slot is already taken
    existing_target = vibe.get("target_id")
    if existing_target and existing_target != str(user.id):
        if lang == "ru":
            text = "Этот Vibe Check уже используется кем-то другим. Попроси друга создать новый!"
        else:
            text = "This Vibe Check is already taken by someone else. Ask your friend to create a new one!"
        await message.answer(text)
        return

    # Check if target already completed
    if vibe.get("target_completed"):
        if lang == "ru":
            text = "Ты уже прошел этот Vibe Check! ✨"
        else:
            text = "You've already completed this Vibe Check! ✨"
        await message.answer(text)

        if vibe.get("initiator_completed") and vibe.get("result"):
            await _deliver_result(vibe, message.chat.id, lang)
        return

    # Set target_id
    if not existing_target:
        await update_vibe_check(vibe["id"], {"target_id": str(user.id)})

    # Get initiator name
    initiator_name = "Someone"
    try:
        initiator = await user_service.get_user(UUID(vibe["initiator_id"]))
        if initiator:
            initiator_name = initiator.display_name or initiator.first_name or "Someone"
    except Exception:
        pass

    if lang == "ru":
        text = (
            f"🔮 <b>{initiator_name}</b> приглашает тебя на Vibe Check!\n\n"
            f"Я задам тебе несколько веселых вопросов — это займет 2-3 минуты.\n"
            f"Потом вы оба получите отчет о совместимости ✨"
        )
    else:
        text = (
            f"🔮 <b>{initiator_name}</b> invited you to a Vibe Check!\n\n"
            f"I'll ask you a few fun questions — takes 2-3 minutes.\n"
            f"Then you'll both get a compatibility report ✨"
        )

    await message.answer(text)

    await state.set_state(VibeCheckStates.interviewing)
    await state.update_data(
        vibe_id=vibe["id"],
        vibe_code=short_code,
        vibe_role="target",
        vibe_history=[],
        vibe_turn_count=0,
        vibe_lang=lang,
    )

    await asyncio.sleep(1)
    user_name = user.display_name or message.from_user.first_name or "Friend"
    first_message = await _ai_interview_message(
        user_name=user_name,
        role="target",
        conversation_history=[],
        turn_count=0,
        lang=lang,
    )

    await message.answer(first_message)

    await state.update_data(
        vibe_history=[{"role": "assistant", "content": first_message}],
        vibe_turn_count=1,
    )


# ============================================
# HANDLER: TEXT MESSAGES DURING INTERVIEW
# ============================================

@router.message(VibeCheckStates.interviewing, F.text)
async def handle_vibe_text(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        if message.text.startswith("/start"):
            from adapters.telegram.handlers.start import start_command
            await start_command(message, state)
        elif message.text.startswith("/menu"):
            from adapters.telegram.handlers.start import menu_command
            await menu_command(message)
        else:
            await message.answer("Vibe check cancelled. Send the command again.")
        return

    await _process_vibe_answer(message, state, message.text)


async def _process_vibe_answer(message: Message, state: FSMContext, text: str):
    data = await state.get_data()
    vibe_id = data.get("vibe_id")
    role = data.get("vibe_role", "initiator")
    history = data.get("vibe_history", [])
    turn_count = data.get("vibe_turn_count", 0)
    lang = data.get("vibe_lang", "en")

    if not vibe_id:
        await state.clear()
        await message.answer("Something went wrong. Try /start")
        return

    history.append({"role": "user", "content": text})
    turn_count += 1

    if turn_count >= MAX_VIBE_TURNS * 2:
        await _finish_interview(message, state, history, lang)
        return

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM, str(message.from_user.id)
    )
    user_name = "Friend"
    if user:
        user_name = user.display_name or message.from_user.first_name or "Friend"

    ai_turn_count = len([m for m in history if m["role"] == "assistant"])

    ai_response = await _ai_interview_message(
        user_name=user_name,
        role=role,
        conversation_history=history,
        turn_count=ai_turn_count,
        lang=lang,
    )

    is_wrapping = ai_turn_count >= MIN_VIBE_TURNS and any(
        signal in ai_response.lower()
        for signal in ["good read", "great vibes", "got a good", "отличное впечатление", "хорошо тебя понял", "✨", "got you figured"]
    )

    history.append({"role": "assistant", "content": ai_response})
    await state.update_data(vibe_history=history, vibe_turn_count=turn_count + 1)

    await message.answer(ai_response)

    if is_wrapping or ai_turn_count >= MAX_VIBE_TURNS:
        await asyncio.sleep(1)
        await _finish_interview(message, state, history, lang)


@router.message(VibeCheckStates.interviewing, F.voice)
async def handle_vibe_voice(message: Message, state: FSMContext):
    """Process voice message during vibe interview — transcribe using download_and_transcribe."""
    lang_data = await state.get_data()
    lang = lang_data.get("vibe_lang", "en")

    try:
        file_info = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        text = await voice_service.download_and_transcribe(file_url)

        if not text or not text.strip():
            hint = "Не удалось распознать. Попробуй текстом!" if lang == "ru" else "Couldn't understand that. Try typing instead!"
            await message.answer(hint)
            return

        await _process_vibe_answer(message, state, text.strip())

    except Exception as e:
        logger.error(f"Vibe voice error: {e}", exc_info=True)
        hint = "Не удалось обработать голос. Попробуй текстом!" if lang == "ru" else "Couldn't process voice. Try typing instead!"
        await message.answer(hint)


# ============================================
# HANDLER: WAITING STATE
# ============================================

@router.message(VibeCheckStates.waiting_for_partner, F.text)
async def handle_waiting_text(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        if message.text.startswith("/start"):
            from adapters.telegram.handlers.start import start_command
            await start_command(message, state)
        elif message.text.startswith("/menu"):
            from adapters.telegram.handlers.start import menu_command
            await menu_command(message)
        return

    data = await state.get_data()
    lang = data.get("vibe_lang", "en")
    if lang == "ru":
        await message.answer(
            "Ты уже ответил на вопросы! Жди, пока второй участник закончит ✨",
            reply_markup=get_vibe_waiting_keyboard(lang),
        )
    else:
        await message.answer(
            "You've already answered the questions! Waiting for the other person to finish ✨",
            reply_markup=get_vibe_waiting_keyboard(lang),
        )


# ============================================
# INTERNAL: FINISH INTERVIEW
# ============================================

async def _finish_interview(message: Message, state: FSMContext, history: list, lang: str):
    data = await state.get_data()
    vibe_id = data.get("vibe_id")
    role = data.get("vibe_role", "initiator")

    extracted = await _extract_personality(history)

    if role == "initiator":
        update_data = {
            "initiator_data": extracted,
            "initiator_conversation": history,
            "initiator_completed": True,
        }
    else:
        update_data = {
            "target_data": extracted,
            "target_conversation": history,
            "target_completed": True,
        }

    try:
        await update_vibe_check(vibe_id, update_data)
    except Exception as e:
        logger.error(f"Failed to save vibe interview data: {e}", exc_info=True)

    vibe = await get_vibe_by_id(vibe_id)
    both_done = vibe and vibe.get("initiator_completed") and vibe.get("target_completed")

    if both_done and not vibe.get("result"):
        if lang == "ru":
            await message.answer("🔮 Оба закончили! Генерирую отчет о совместимости...")
        else:
            await message.answer("🔮 Both done! Generating your compatibility report...")

        await state.clear()
        await _generate_and_deliver_result(vibe, lang)
    elif both_done and vibe.get("result"):
        await state.clear()
    else:
        if lang == "ru":
            text = (
                "Отлично! Я запомнил твои ответы ✨\n\n"
                "Я дам тебе знать, когда второй участник закончит.\n"
                "А пока — можешь вернуться в меню."
            )
        else:
            text = (
                "Great answers! I've got a good read on you ✨\n\n"
                "I'll let you know when the other person finishes.\n"
                "In the meantime — you can go back to the menu."
            )

        await message.answer(text, reply_markup=get_vibe_waiting_keyboard(lang))
        await state.set_state(VibeCheckStates.waiting_for_partner)
        await state.update_data(vibe_id=vibe_id, vibe_lang=lang)


# ============================================
# INTERNAL: GENERATE AND DELIVER RESULT
# ============================================

async def _generate_and_deliver_result(vibe: dict, lang: str):
    initiator = None
    target = None
    try:
        initiator = await user_service.get_user(UUID(vibe["initiator_id"]))
        target = await user_service.get_user(UUID(vibe["target_id"]))
    except Exception as e:
        logger.error(f"Failed to get vibe check users: {e}")
        return

    if not initiator or not target:
        logger.error("Vibe check users not found")
        return

    name_a = initiator.display_name or initiator.first_name or "User A"
    name_b = target.display_name or target.first_name or "User B"

    data_a = vibe.get("initiator_data", {})
    data_b = vibe.get("target_data", {})
    conv_a = vibe.get("initiator_conversation", [])
    conv_b = vibe.get("target_conversation", [])

    # Parse if stored as JSON strings
    def _parse_json(val, default):
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return default
        return val

    data_a = _parse_json(data_a, {})
    data_b = _parse_json(data_b, {})
    conv_a = _parse_json(conv_a, [])
    conv_b = _parse_json(conv_b, [])

    result = await _generate_compatibility(
        name_a, data_a, conv_a,
        name_b, data_b, conv_b,
        lang,
    )

    await update_vibe_check(vibe["id"], {
        "result": result,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })

    result_text = _format_result(result, name_a, name_b, lang)

    initiator_tg_id = initiator.platform_user_id
    target_tg_id = target.platform_user_id

    try:
        await bot.send_message(
            int(initiator_tg_id),
            result_text,
            reply_markup=get_vibe_result_keyboard(partner_username=target.username, lang=lang),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Failed to send vibe result to initiator {initiator_tg_id}: {e}")

    try:
        await bot.send_message(
            int(target_tg_id),
            result_text,
            reply_markup=get_vibe_result_keyboard(partner_username=initiator.username, lang=lang),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Failed to send vibe result to target {target_tg_id}: {e}")

    asyncio.create_task(_enrich_profiles(initiator, data_a, target, data_b))


async def _deliver_result(vibe: dict, chat_id: int, lang: str):
    result = vibe.get("result", {})
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            result = {}

    if not result:
        return

    try:
        initiator = await user_service.get_user(UUID(vibe["initiator_id"]))
    except (ValueError, TypeError):
        initiator = None
    try:
        target_id = vibe.get("target_id")
        target = await user_service.get_user(UUID(target_id)) if target_id else None
    except (ValueError, TypeError):
        target = None

    name_a = (initiator.display_name or initiator.first_name or "User A") if initiator else "User A"
    name_b = (target.display_name or target.first_name or "User B") if target else "User B"

    result_text = _format_result(result, name_a, name_b, lang)

    partner_username = None
    if initiator and target:
        if str(chat_id) == initiator.platform_user_id:
            partner_username = target.username
        else:
            partner_username = initiator.username

    await bot.send_message(
        chat_id,
        result_text,
        reply_markup=get_vibe_result_keyboard(partner_username=partner_username, lang=lang),
        parse_mode="HTML",
    )


# ============================================
# INTERNAL: PROFILE ENRICHMENT
# ============================================

async def _enrich_profiles(initiator, data_a: dict, target, data_b: dict):
    try:
        for user, data in [(initiator, data_a), (target, data_b)]:
            if not data:
                continue

            update = {}

            deep_interests = data.get("interests_deep", [])
            if deep_interests and user.interests:
                existing = set(user.interests)
                new_interests = [i for i in deep_interests if i not in existing]
                if new_interests:
                    update["interests"] = user.interests + new_interests[:3]

            values = data.get("values", [])
            if values and not user.bio:
                update["bio"] = f"Values: {', '.join(values[:3])}"

            if update:
                await user_service.update_user(
                    platform=MessagePlatform.TELEGRAM,
                    platform_user_id=user.platform_user_id,
                    **update,
                )

    except Exception as e:
        logger.error(f"Profile enrichment from vibe check failed: {e}", exc_info=True)
