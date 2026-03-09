"""
Profile Editing Handler - Two modes:
1. Quick Edit: Select field → Type/voice new value → Confirm
2. Conversational: "Add X to interests" → LLM interprets → Preview → Confirm
"""

import asyncio
import json
import logging
import os
import tempfile

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from adapters.telegram.keyboards.inline import (
    get_edit_confirm_keyboard,
    get_edit_continue_keyboard,
    get_edit_field_keyboard,
    get_edit_mode_keyboard,
    get_goals_keyboard,
    get_interests_keyboard,
)
from adapters.telegram.loader import ai_service, bot, embedding_service, user_repo, user_service, voice_service
from adapters.telegram.states.onboarding import ProfileEditStates
from core.domain.models import MessagePlatform
from core.utils.language import detect_lang

logger = logging.getLogger(__name__)
router = Router()

# detect_lang works for both Message and CallbackQuery
detect_lang_message = detect_lang


# === LLM PROMPT FOR CONVERSATIONAL EDIT ===

PROFILE_EDIT_PROMPT = """You are helping a user edit their networking profile.
They will describe what changes they want in natural language.

CURRENT PROFILE:
- Name: {display_name}
- About: {bio}
- Looking for: {looking_for}
- Can help with: {can_help_with}
- Interests: {interests}
- Goals: {goals}

USER REQUEST: {request}

Analyze the request and generate the EXACT changes needed.
Return JSON with ONLY the fields that should change:

{{
  "bio": "new bio text" or null,
  "looking_for": "new looking for text" or null,
  "can_help_with": "new can help with text" or null,
  "interests": ["updated", "list"] or null,
  "goals": ["updated", "list"] or null,
  "action_type": "add|remove|replace|update",
  "summary": "brief description of changes in {language}"
}}

RULES:
- If user says "add X to interests", add X to existing interests list
- If user says "remove X from goals", remove X from existing goals
- If user says "change my bio to X", replace entire bio
- If user says "update looking_for with X", merge/update text
- Keep existing values for fields not mentioned
- Return null for unchanged fields
- INTERESTS must be from: tech, AI, ML, product, business, startups, crypto, web3, design, art, music, books, travel, sport, fitness, wellness, psychology, gaming, ecology, cooking, cinema
- GOALS must be from: networking, friends, business, mentorship, cofounders, creative, learning, dating

Return ONLY valid JSON."""


async def generate_embeddings_background(user_obj):
    """Background task to regenerate embeddings after profile edit"""
    try:
        result = await embedding_service.generate_embeddings(user_obj)
        if result:
            profile_emb, interests_emb, expertise_emb = result
            await user_repo.update_embeddings(
                user_obj.id,
                profile_embedding=profile_emb,
                interests_embedding=interests_emb,
                expertise_embedding=expertise_emb
            )
            logger.info(f"Regenerated embeddings for user {user_obj.id}")
    except Exception as e:
        logger.error(f"Background embedding regeneration failed: {e}")


# === EDIT MODE SELECTION ===

@router.callback_query(F.data == "edit_my_profile")
async def start_profile_edit(callback: CallbackQuery, state: FSMContext):
    """Start profile editing - choose mode"""
    lang = detect_lang(callback)

    if lang == "ru":
        text = "✏️ <b>Редактирование профиля</b>\n\nКак хочешь внести изменения?"
    else:
        text = "✏️ <b>Edit Profile</b>\n\nHow would you like to make changes?"

    await state.set_state(ProfileEditStates.choosing_mode)
    await callback.message.edit_text(text, reply_markup=get_edit_mode_keyboard(lang))
    await callback.answer()


# === QUICK EDIT MODE ===

@router.callback_query(F.data == "edit_mode_quick")
async def quick_edit_choose_field(callback: CallbackQuery, state: FSMContext):
    """Quick edit - choose field"""
    lang = detect_lang(callback)

    if lang == "ru":
        text = "📝 Выбери поле для редактирования:"
    else:
        text = "📝 Choose a field to edit:"

    await state.set_state(ProfileEditStates.choosing_field)
    await state.update_data(language=lang)
    await callback.message.edit_text(text, reply_markup=get_edit_field_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field_"))
async def edit_field_selected(callback: CallbackQuery, state: FSMContext):
    """Field selected - ask for new value"""
    lang = detect_lang(callback)
    field = callback.data.replace("edit_field_", "")

    # Get current user data
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    await state.update_data(edit_field=field, language=lang)

    # Handle special fields (interests, goals, photo)
    if field == "interests":
        await state.set_state(ProfileEditStates.entering_value)
        current = user.interests if user and user.interests else []
        await state.update_data(selected_interests=current)

        if lang == "ru":
            text = "🏷️ Выбери интересы (нажми чтобы добавить/убрать):"
        else:
            text = "🏷️ Select interests (tap to add/remove):"

        await callback.message.edit_text(text, reply_markup=get_interests_keyboard(current, lang))
        await callback.answer()
        return

    if field == "goals":
        await state.set_state(ProfileEditStates.entering_value)
        current = user.goals if user and user.goals else []
        await state.update_data(selected_goals=current)

        if lang == "ru":
            text = "🎯 Выбери цели (нажми чтобы добавить/убрать):"
        else:
            text = "🎯 Select goals (tap to add/remove):"

        await callback.message.edit_text(text, reply_markup=get_goals_keyboard(current, lang))
        await callback.answer()
        return

    if field == "photo":
        await state.set_state(ProfileEditStates.entering_value)
        if lang == "ru":
            text = "📸 Отправь новое фото (селфи или портрет):"
        else:
            text = "📸 Send a new photo (selfie or portrait):"

        await callback.message.edit_text(text)
        await callback.answer()
        return

    # Text fields
    field_names = {
        "bio": ("О себе", "About me"),
        "looking_for": ("Кого/что ищу", "Looking for"),
        "can_help": ("Чем могу помочь", "Can help with"),
    }

    current_value = ""
    if user:
        if field == "bio":
            current_value = user.bio or ""
        elif field == "looking_for":
            current_value = user.looking_for or ""
        elif field == "can_help":
            current_value = user.can_help_with or ""

    name_ru, name_en = field_names.get(field, (field, field))
    field_name = name_ru if lang == "ru" else name_en

    if lang == "ru":
        text = f"📝 <b>{field_name}</b>\n\nТекущее значение:\n<i>{current_value or '(пусто)'}</i>\n\nОтправь новый текст или голосовое сообщение:"
    else:
        text = f"📝 <b>{field_name}</b>\n\nCurrent value:\n<i>{current_value or '(empty)'}</i>\n\nSend new text or voice message:"

    await state.set_state(ProfileEditStates.entering_value)
    await callback.message.edit_text(text)
    await callback.answer()


# Handle interest selection during edit
@router.callback_query(F.data.startswith("interest_"), ProfileEditStates.entering_value)
async def toggle_interest_edit(callback: CallbackQuery, state: FSMContext):
    """Toggle interest during edit"""
    data = await state.get_data()
    if data.get("edit_field") != "interests":
        return

    lang = data.get("language", "en")
    interest = callback.data.replace("interest_", "")
    selected = data.get("selected_interests", [])

    if interest in selected:
        selected.remove(interest)
    else:
        selected.append(interest)

    await state.update_data(selected_interests=selected)

    if lang == "ru":
        text = f"🏷️ Выбрано: {len(selected)}\nНажми чтобы добавить/убрать:"
    else:
        text = f"🏷️ Selected: {len(selected)}\nTap to add/remove:"

    await callback.message.edit_text(text, reply_markup=get_interests_keyboard(selected, lang))
    await callback.answer()


@router.callback_query(F.data == "interests_done", ProfileEditStates.entering_value)
async def interests_edit_done(callback: CallbackQuery, state: FSMContext):
    """Interests selection complete"""
    data = await state.get_data()
    if data.get("edit_field") != "interests":
        return

    lang = data.get("language", "en")
    selected = data.get("selected_interests", [])

    # Show preview
    interests_display = ", ".join(selected) if selected else ("(пусто)" if lang == "ru" else "(empty)")

    if lang == "ru":
        text = f"🏷️ <b>Новые интересы:</b>\n{interests_display}\n\nСохранить?"
    else:
        text = f"🏷️ <b>New interests:</b>\n{interests_display}\n\nSave changes?"

    await state.update_data(new_value=selected)
    await state.set_state(ProfileEditStates.confirming_changes)
    await callback.message.edit_text(text, reply_markup=get_edit_confirm_keyboard(lang))
    await callback.answer()


# Handle goal selection during edit
@router.callback_query(F.data.startswith("goal_"), ProfileEditStates.entering_value)
async def toggle_goal_edit(callback: CallbackQuery, state: FSMContext):
    """Toggle goal during edit"""
    data = await state.get_data()
    if data.get("edit_field") != "goals":
        return

    lang = data.get("language", "en")
    goal = callback.data.replace("goal_", "")
    selected = data.get("selected_goals", [])

    if goal in selected:
        selected.remove(goal)
    else:
        selected.append(goal)

    await state.update_data(selected_goals=selected)

    if lang == "ru":
        text = f"🎯 Выбрано: {len(selected)}\nНажми чтобы добавить/убрать:"
    else:
        text = f"🎯 Selected: {len(selected)}\nTap to add/remove:"

    await callback.message.edit_text(text, reply_markup=get_goals_keyboard(selected, lang))
    await callback.answer()


@router.callback_query(F.data == "goals_done", ProfileEditStates.entering_value)
async def goals_edit_done(callback: CallbackQuery, state: FSMContext):
    """Goals selection complete"""
    data = await state.get_data()
    if data.get("edit_field") != "goals":
        return

    lang = data.get("language", "en")
    selected = data.get("selected_goals", [])

    goals_display = ", ".join(selected) if selected else ("(пусто)" if lang == "ru" else "(empty)")

    if lang == "ru":
        text = f"🎯 <b>Новые цели:</b>\n{goals_display}\n\nСохранить?"
    else:
        text = f"🎯 <b>New goals:</b>\n{goals_display}\n\nSave changes?"

    await state.update_data(new_value=selected)
    await state.set_state(ProfileEditStates.confirming_changes)
    await callback.message.edit_text(text, reply_markup=get_edit_confirm_keyboard(lang))
    await callback.answer()


# Handle text/voice input for field edit
@router.message(ProfileEditStates.entering_value)
async def receive_field_value(message: Message, state: FSMContext):
    """Receive new value for field (text or voice)"""
    data = await state.get_data()
    field = data.get("edit_field")
    lang = data.get("language", "en")

    if not field:
        return

    # Handle photo
    if field == "photo":
        if message.photo:
            photo = message.photo[-1]  # Best quality

            await state.update_data(new_value=photo.file_id)

            if lang == "ru":
                text = "📸 Новое фото получено!\n\nСохранить?"
            else:
                text = "📸 New photo received!\n\nSave changes?"

            await state.set_state(ProfileEditStates.confirming_changes)
            await message.answer(text, reply_markup=get_edit_confirm_keyboard(lang))
        else:
            if lang == "ru":
                await message.answer("📸 Пожалуйста, отправь фото")
            else:
                await message.answer("📸 Please send a photo")
        return

    # Handle voice message
    if message.voice:
        try:
            voice_file = await bot.get_file(message.voice.file_id)
            voice_data = await bot.download_file(voice_file.file_path)
            voice_bytes = voice_data.read()

            # Save to temp file for whisper
            fd, temp_path = tempfile.mkstemp(suffix='.ogg')
            try:
                os.write(fd, voice_bytes)
            finally:
                os.close(fd)

            new_value = await voice_service.transcribe(temp_path)
            if not new_value:
                if lang == "ru":
                    await message.answer("❌ Не удалось распознать голос. Попробуй текстом.")
                else:
                    await message.answer("❌ Couldn't transcribe voice. Try text instead.")
                return
        except Exception as e:
            logger.error(f"Voice transcription error: {e}")
            if lang == "ru":
                await message.answer("❌ Ошибка распознавания. Попробуй текстом.")
            else:
                await message.answer("❌ Transcription error. Try text instead.")
            return
    else:
        new_value = message.text

    if not new_value:
        return

    # Show preview
    field_names = {
        "bio": ("О себе", "About me"),
        "looking_for": ("Кого/что ищу", "Looking for"),
        "can_help": ("Чем могу помочь", "Can help with"),
    }

    name_ru, name_en = field_names.get(field, (field, field))
    field_name = name_ru if lang == "ru" else name_en

    preview = new_value[:300] + ("..." if len(new_value) > 300 else "")

    if lang == "ru":
        text = f"📝 <b>{field_name}</b>\n\nНовое значение:\n{preview}\n\nСохранить?"
    else:
        text = f"📝 <b>{field_name}</b>\n\nNew value:\n{preview}\n\nSave changes?"

    await state.update_data(new_value=new_value)
    await state.set_state(ProfileEditStates.confirming_changes)
    await message.answer(text, reply_markup=get_edit_confirm_keyboard(lang))


# === CONVERSATIONAL EDIT MODE ===

@router.callback_query(F.data == "edit_mode_chat")
async def conversational_edit_start(callback: CallbackQuery, state: FSMContext):
    """Start conversational edit mode"""
    lang = detect_lang(callback)

    if lang == "ru":
        text = """💬 <b>Опиши изменения</b>

Напиши или скажи голосом что хочешь изменить:

Примеры:
• "Добавь crypto в интересы"
• "Убери dating из целей"
• "Измени bio на: Строю AI продукты"
• "Добавь в looking_for: инвесторы seed раунда"

Жду твоё сообщение:"""
    else:
        text = """💬 <b>Describe changes</b>

Type or say what you want to change:

Examples:
• "Add crypto to my interests"
• "Remove dating from goals"
• "Change my bio to: Building AI products"
• "Add to looking_for: seed round investors"

Send your message:"""

    await state.set_state(ProfileEditStates.conversational)
    await state.update_data(language=lang)
    await callback.message.edit_text(text)
    await callback.answer()


@router.message(ProfileEditStates.conversational)
async def process_conversational_edit(message: Message, state: FSMContext):
    """Process conversational edit request"""
    data = await state.get_data()
    lang = data.get("language", "en")

    # Handle voice
    if message.voice:
        try:
            voice_file = await bot.get_file(message.voice.file_id)
            voice_data = await bot.download_file(voice_file.file_path)
            voice_bytes = voice_data.read()

            # Save to temp file for whisper
            fd, temp_path = tempfile.mkstemp(suffix='.ogg')
            try:
                os.write(fd, voice_bytes)
            finally:
                os.close(fd)

            request_text = await voice_service.transcribe(temp_path)
            if not request_text:
                if lang == "ru":
                    await message.answer("❌ Не удалось распознать. Попробуй текстом.")
                else:
                    await message.answer("❌ Couldn't transcribe. Try text.")
                return
        except Exception as e:
            logger.error(f"Voice transcription error: {e}")
            if lang == "ru":
                await message.answer("❌ Ошибка. Попробуй текстом.")
            else:
                await message.answer("❌ Error. Try text.")
            return
    else:
        request_text = message.text

    if not request_text:
        return

    # Get current profile
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )

    if not user:
        if lang == "ru":
            await message.answer("❌ Профиль не найден")
        else:
            await message.answer("❌ Profile not found")
        await state.clear()
        return

    # Send thinking message
    if lang == "ru":
        thinking_msg = await message.answer("🤔 Анализирую...")
    else:
        thinking_msg = await message.answer("🤔 Analyzing...")

    # Call LLM to interpret changes
    try:
        prompt = PROFILE_EDIT_PROMPT.format(
            display_name=user.display_name or user.first_name or "User",
            bio=user.bio or "(empty)",
            looking_for=user.looking_for or "(empty)",
            can_help_with=user.can_help_with or "(empty)",
            interests=", ".join(user.interests) if user.interests else "(none)",
            goals=", ".join(user.goals) if user.goals else "(none)",
            request=request_text,
            language="Russian" if lang == "ru" else "English"
        )

        response = await ai_service.chat(prompt=prompt, model="gpt-4o-mini")

        # Parse JSON response
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]

        changes = json.loads(json_str)

    except Exception as e:
        logger.error(f"LLM edit error: {e}")
        await thinking_msg.delete()
        if lang == "ru":
            await message.answer("❌ Не удалось понять запрос. Попробуй по-другому.")
        else:
            await message.answer("❌ Couldn't understand request. Try rephrasing.")
        return

    await thinking_msg.delete()

    # Build preview
    summary = changes.get("summary", "Changes detected")
    preview_parts = []

    if changes.get("bio"):
        bio_preview = changes["bio"][:100] + ("..." if len(changes["bio"]) > 100 else "")
        preview_parts.append(f"📝 About: {bio_preview}")

    if changes.get("looking_for"):
        lf_preview = changes["looking_for"][:100] + ("..." if len(changes["looking_for"]) > 100 else "")
        preview_parts.append(f"🔍 Looking for: {lf_preview}")

    if changes.get("can_help_with"):
        ch_preview = changes["can_help_with"][:100] + ("..." if len(changes["can_help_with"]) > 100 else "")
        preview_parts.append(f"💡 Can help: {ch_preview}")

    if changes.get("interests"):
        preview_parts.append(f"#️⃣ Interests: {', '.join(changes['interests'])}")

    if changes.get("goals"):
        preview_parts.append(f"🎯 Goals: {', '.join(changes['goals'])}")

    if not preview_parts:
        if lang == "ru":
            await message.answer("🤔 Не нашёл изменений в запросе. Попробуй по-другому.")
        else:
            await message.answer("🤔 No changes detected. Try rephrasing.")
        return

    preview_text = "\n".join(preview_parts)

    if lang == "ru":
        text = f"✨ <b>{summary}</b>\n\n{preview_text}\n\nПрименить изменения?"
    else:
        text = f"✨ <b>{summary}</b>\n\n{preview_text}\n\nApply changes?"

    await state.update_data(pending_changes=changes)
    await state.set_state(ProfileEditStates.confirming_changes)
    await message.answer(text, reply_markup=get_edit_confirm_keyboard(lang))


# === CONFIRM / CANCEL ===

@router.callback_query(F.data == "edit_confirm")
async def confirm_edit(callback: CallbackQuery, state: FSMContext):
    """Confirm and save edit"""
    data = await state.get_data()
    lang = data.get("language", "en")

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer("Profile not found", show_alert=True)
        await state.clear()
        return

    try:
        # Check if conversational edit (multiple fields)
        pending_changes = data.get("pending_changes")

        if pending_changes:
            # Conversational edit - apply all changes
            update_data = {}

            if pending_changes.get("bio"):
                update_data["bio"] = pending_changes["bio"]
            if pending_changes.get("looking_for"):
                update_data["looking_for"] = pending_changes["looking_for"]
            if pending_changes.get("can_help_with"):
                update_data["can_help_with"] = pending_changes["can_help_with"]
            if pending_changes.get("interests"):
                update_data["interests"] = pending_changes["interests"]
            if pending_changes.get("goals"):
                update_data["goals"] = pending_changes["goals"]

            if update_data:
                updated_user = await user_service.update_user(
                    MessagePlatform.TELEGRAM,
                    str(callback.from_user.id),
                    **update_data
                )
            else:
                updated_user = None
        else:
            # Quick edit - single field
            field = data.get("edit_field")
            new_value = data.get("new_value")

            if not field or new_value is None:
                await callback.answer("No changes to save", show_alert=True)
                await state.clear()
                return

            update_data = {}
            if field == "bio":
                update_data["bio"] = new_value
            elif field == "looking_for":
                update_data["looking_for"] = new_value
            elif field == "can_help":
                update_data["can_help_with"] = new_value
            elif field == "interests":
                update_data["interests"] = new_value
            elif field == "goals":
                update_data["goals"] = new_value
            elif field == "photo":
                update_data["photo_url"] = new_value

            updated_user = await user_service.update_user(
                MessagePlatform.TELEGRAM,
                str(callback.from_user.id),
                **update_data
            )

        # Regenerate embeddings in background
        if updated_user:
            asyncio.create_task(generate_embeddings_background(updated_user))

        if lang == "ru":
            text = "✅ Профиль обновлён!"
        else:
            text = "✅ Profile updated!"

        await callback.message.edit_text(text, reply_markup=get_edit_continue_keyboard(lang))
        await callback.answer()

    except Exception as e:
        logger.error(f"Profile update error: {e}")
        if lang == "ru":
            await callback.answer("❌ Ошибка сохранения", show_alert=True)
        else:
            await callback.answer("❌ Save error", show_alert=True)

    finally:
        await state.clear()


@router.callback_query(F.data == "edit_cancel")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Cancel edit"""
    data = await state.get_data()
    lang = data.get("language", "en")

    await state.clear()

    if lang == "ru":
        text = "❌ Изменения отменены"
    else:
        text = "❌ Changes cancelled"

    await callback.message.edit_text(text, reply_markup=get_edit_continue_keyboard(lang))
    await callback.answer()


# === INLINE EDIT FROM PROFILE VIEW ===

@router.message(ProfileEditStates.viewing_profile, F.text, ~F.text.startswith("/"))
async def inline_profile_edit(message: Message, state: FSMContext, text_override: str = None):
    """User typed while viewing profile — auto-interpret and apply changes."""
    data = await state.get_data()
    lang = data.get("language", "en")
    request_text = text_override or message.text

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )
    if not user:
        return

    status = await message.answer("🤔 ..." if lang == "ru" else "🤔 ...")

    try:
        prompt = PROFILE_EDIT_PROMPT.format(
            display_name=user.display_name or user.first_name or "User",
            bio=user.bio or "(empty)",
            looking_for=user.looking_for or "(empty)",
            can_help_with=user.can_help_with or "(empty)",
            interests=", ".join(user.interests) if user.interests else "(none)",
            goals=", ".join(user.goals) if user.goals else "(none)",
            request=request_text,
            language="Russian" if lang == "ru" else "English"
        )

        response = await ai_service.chat(prompt=prompt, model="gpt-4o-mini")

        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]

        changes = json.loads(json_str)
    except Exception as e:
        logger.error(f"Inline edit LLM error: {e}")
        await status.edit_text(
            "Не удалось понять. Попробуй по-другому." if lang == "ru"
            else "Couldn't understand. Try rephrasing."
        )
        return

    # Build update dict
    update_data = {}
    if changes.get("bio"):
        update_data["bio"] = changes["bio"]
    if changes.get("looking_for"):
        update_data["looking_for"] = changes["looking_for"]
    if changes.get("can_help_with"):
        update_data["can_help_with"] = changes["can_help_with"]
    if changes.get("interests"):
        update_data["interests"] = changes["interests"]
    if changes.get("goals"):
        update_data["goals"] = changes["goals"]

    if not update_data:
        await status.edit_text(
            "Не нашёл изменений. Попробуй по-другому." if lang == "ru"
            else "No changes detected. Try rephrasing."
        )
        return

    # Apply changes
    try:
        updated_user = await user_service.update_user(
            MessagePlatform.TELEGRAM,
            str(message.from_user.id),
            **update_data
        )

        # Regenerate embeddings in background
        if updated_user:
            asyncio.create_task(generate_embeddings_background(updated_user))

        summary = changes.get("summary", "Updated" if lang == "en" else "Обновлено")
        await status.edit_text(f"✅ {summary}")

    except Exception as e:
        logger.error(f"Inline edit save error: {e}")
        await status.edit_text(
            "Ошибка сохранения." if lang == "ru" else "Save error."
        )


@router.message(ProfileEditStates.viewing_profile, F.voice)
async def inline_profile_edit_voice(message: Message, state: FSMContext):
    """User sent voice while viewing profile — transcribe and apply."""
    data = await state.get_data()
    lang = data.get("language", "en")

    try:
        voice_file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{voice_file.file_path}"
        transcription = await voice_service.download_and_transcribe(file_url, language=lang)
        if not transcription:
            await message.answer(
                "Не расслышал. Попробуй текстом." if lang == "ru"
                else "Couldn't hear that. Try typing."
            )
            return
    except Exception as e:
        logger.error(f"Inline voice edit error: {e}")
        await message.answer(
            "Ошибка. Попробуй текстом." if lang == "ru" else "Error. Try typing."
        )
        return

    # Reuse text handler with transcript
    await inline_profile_edit(message, state, text_override=transcription)
