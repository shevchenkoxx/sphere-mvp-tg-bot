"""
Profile enrichment handler.
Handles anytime voice, screenshot, and link submissions for profile enrichment.
Works ONLY when user has completed onboarding and is NOT in any FSM state.
"""

import asyncio
import json
import logging
import re
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from locales import t
from core.domain.models import MessagePlatform, UserUpdate
from core.prompts.intent_onboarding import SOCIAL_LINK_EXTRACTION, format_profile_summary
from adapters.telegram.loader import (
    user_service, bot, voice_service, ai_service, embedding_service, user_repo,
)
from core.utils.language import detect_lang

logger = logging.getLogger(__name__)

router = Router()

# Extraction prompt for enrichment voice messages
ENRICH_VOICE_PROMPT = """Analyze this voice message from an existing user and extract NEW profile information.

Current profile:
- Bio: {bio}
- Interests: {interests}
- Goals: {goals}
- Looking for: {looking_for}
- Can help with: {can_help_with}
- Skills: {skills}

Voice transcript: {transcript}

Extract ONLY new information not already in the profile. Return JSON:
{{
  "bio_addition": "new bio info to append, or null",
  "new_interests": ["interest1"],
  "new_goals": ["goal1"],
  "new_skills": ["skill1"],
  "looking_for_addition": "new info or null",
  "can_help_with_addition": "new info or null",
  "personality_vibe": "active/creative/intellectual/social or null",
  "summary": "1-sentence summary of what was added"
}}

Respond with valid JSON only."""


# ============================================================
# VOICE ENRICHMENT (anytime voice when no state)
# ============================================================

@router.message(StateFilter(None), F.voice)
async def handle_enrichment_voice(message: Message, state: FSMContext):
    """Handle voice message from onboarded user for profile enrichment."""
    user = await user_repo.get_by_platform_id(
        MessagePlatform.TELEGRAM, str(message.from_user.id)
    )

    # Only process for onboarded users
    if not user or not user.onboarding_completed:
        return

    lang = user.language or detect_lang(message)
    await message.answer(t("voice_processing", lang))

    try:
        file = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        transcript = await voice_service.download_and_transcribe(file_url)

        if not transcript:
            await message.answer(t("error_generic", lang))
            return

        # Extract new info from transcript
        prompt = ENRICH_VOICE_PROMPT.format(
            bio=user.bio or "",
            interests=", ".join(user.interests) if user.interests else "",
            goals=", ".join(user.goals) if user.goals else "",
            looking_for=user.looking_for or "",
            can_help_with=user.can_help_with or "",
            skills=", ".join(user.skills) if user.skills else "",
            transcript=transcript,
        )

        raw = await ai_service.chat(prompt)
        extracted = _safe_parse_json(raw)

        if not extracted:
            await message.answer(t("error_generic", lang))
            return

        # Merge into profile
        await _merge_enrichment_data(user, extracted)

        # Regenerate embeddings
        asyncio.create_task(_regenerate_embeddings(user))

        summary = extracted.get("summary", "new details")
        await message.answer(t("enrich_voice_done", lang, summary=summary))

    except Exception as e:
        logger.error(f"Error in voice enrichment: {e}", exc_info=True)
        await message.answer(t("error_generic", lang))


# ============================================================
# LINK ENRICHMENT (anytime URL when no state)
# ============================================================

@router.message(StateFilter(None), F.text, F.text.regexp(r'https?://'))
async def handle_enrichment_link(message: Message, state: FSMContext):
    """Handle URL from onboarded user — extract profile info from social media."""
    user = await user_repo.get_by_platform_id(
        MessagePlatform.TELEGRAM, str(message.from_user.id)
    )

    if not user or not user.onboarding_completed:
        return

    lang = user.language or detect_lang(message)

    # Extract URL from message
    url_match = re.search(r'https?://\S+', message.text)
    if not url_match:
        return

    url = url_match.group(0)
    await message.answer(t("social_processing", lang))

    try:
        # Fetch URL content
        from infrastructure.ai.event_parser_service import EventParserService
        parser = EventParserService()
        content = await parser.fetch_url_content(url)

        if not content:
            await message.answer(t("error_generic", lang))
            return

        # Extract profile info
        extraction_prompt = SOCIAL_LINK_EXTRACTION.format(
            url=url,
            content=content[:3000],
        )
        raw = await ai_service.chat(extraction_prompt)
        extracted = _safe_parse_json(raw)

        if not extracted:
            await message.answer(t("error_generic", lang))
            return

        # Merge into profile
        await _merge_social_data(user, extracted)

        # Regenerate embeddings
        asyncio.create_task(_regenerate_embeddings(user))

        platform = extracted.get("platform", "profile")
        summary = extracted.get("bio", "new details")[:80]
        await message.answer(t("enrich_link_done", lang, platform=platform, summary=summary))

    except Exception as e:
        logger.error(f"Error in link enrichment: {e}", exc_info=True)
        await message.answer(t("error_generic", lang))


# ============================================================
# SCREENSHOT ENRICHMENT (anytime photo when no state)
# ============================================================

@router.message(StateFilter(None), F.photo)
async def handle_enrichment_photo(message: Message, state: FSMContext):
    """Handle photo from onboarded user — ask if it's a profile photo or screenshot."""
    user = await user_repo.get_by_platform_id(
        MessagePlatform.TELEGRAM, str(message.from_user.id)
    )

    if not user or not user.onboarding_completed:
        return

    lang = user.language or detect_lang(message)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text=t("enrich_screenshot_profile", lang), callback_data="enrich_profile_photo")
    builder.button(text=t("enrich_screenshot_analyze", lang), callback_data="enrich_analyze_screenshot")
    builder.adjust(1)

    await state.update_data(enrich_photo_file_id=message.photo[-1].file_id)
    await message.answer(t("enrich_screenshot_prompt", lang), reply_markup=builder.as_markup())


@router.callback_query(F.data == "enrich_profile_photo")
async def handle_enrich_profile_photo(callback: CallbackQuery, state: FSMContext):
    """User sent a profile photo — save it."""
    await callback.answer()
    data = await state.get_data()
    file_id = data.get("enrich_photo_file_id")

    if not file_id:
        return

    user = await user_repo.get_by_platform_id(
        MessagePlatform.TELEGRAM, str(callback.from_user.id)
    )
    if not user:
        return

    lang = user.language or detect_lang(callback)

    # Get file URL
    file = await bot.get_file(file_id)
    photo_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

    await user_repo.update(user.id, UserUpdate(photo_url=photo_url))
    await callback.message.edit_text(t("photo_saved", lang))
    await state.update_data(enrich_photo_file_id=None)


@router.callback_query(F.data == "enrich_analyze_screenshot")
async def handle_enrich_analyze_screenshot(callback: CallbackQuery, state: FSMContext):
    """User sent a screenshot to analyze — extract profile info with vision."""
    await callback.answer()
    data = await state.get_data()
    file_id = data.get("enrich_photo_file_id")

    if not file_id:
        return

    user = await user_repo.get_by_platform_id(
        MessagePlatform.TELEGRAM, str(callback.from_user.id)
    )
    if not user:
        return

    lang = user.language or detect_lang(callback)
    await callback.message.edit_text(t("social_processing", lang))

    try:
        # Download and analyze with GPT-4o vision
        file = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

        from core.prompts.intent_onboarding import SOCIAL_SCREENSHOT_EXTRACTION

        response = await ai_service.client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": SOCIAL_SCREENSHOT_EXTRACTION},
                    {"type": "image_url", "image_url": {"url": file_url}},
                ],
            }],
            max_tokens=500,
        )

        raw = response.choices[0].message.content
        extracted = _safe_parse_json(raw)

        if not extracted:
            await callback.message.edit_text(t("error_generic", lang))
            return

        # Merge into profile
        await _merge_social_data(user, extracted)

        # Regenerate embeddings
        asyncio.create_task(_regenerate_embeddings(user))

        platform = extracted.get("platform", "screenshot")
        summary = extracted.get("bio", "new details")[:80]
        await callback.message.edit_text(
            t("enrich_link_done", lang, platform=platform, summary=summary)
        )

    except Exception as e:
        logger.error(f"Error analyzing screenshot: {e}", exc_info=True)
        await callback.message.edit_text(t("error_generic", lang))
    finally:
        await state.update_data(enrich_photo_file_id=None)


# ============================================================
# HELPERS
# ============================================================

async def _merge_enrichment_data(user, extracted: dict):
    """Merge extracted enrichment data into user profile."""
    try:
        update = UserUpdate()
        changed = False

        new_interests = extracted.get("new_interests", [])
        if new_interests:
            current = set(user.interests or [])
            added = [i for i in new_interests if i.lower() not in {x.lower() for x in current}]
            if added:
                update.interests = list(current) + added
                changed = True

        new_goals = extracted.get("new_goals", [])
        if new_goals:
            current = set(user.goals or [])
            added = [g for g in new_goals if g.lower() not in {x.lower() for x in current}]
            if added:
                update.goals = list(current) + added
                changed = True

        new_skills = extracted.get("new_skills", [])
        if new_skills:
            current = set(user.skills or [])
            added = [s for s in new_skills if s.lower() not in {x.lower() for x in current}]
            if added:
                update.skills = list(current) + added
                changed = True

        lf_add = extracted.get("looking_for_addition")
        if lf_add:
            current = user.looking_for or ""
            if lf_add.lower() not in current.lower():
                update.looking_for = f"{current}. {lf_add}" if current else lf_add
                changed = True

        ch_add = extracted.get("can_help_with_addition")
        if ch_add:
            current = user.can_help_with or ""
            if ch_add.lower() not in current.lower():
                update.can_help_with = f"{current}. {ch_add}" if current else ch_add
                changed = True

        vibe = extracted.get("personality_vibe")
        if vibe and not user.personality_vibe:
            update.personality_vibe = vibe
            changed = True

        if changed:
            await user_repo.update(user.id, update)
            logger.info(f"Merged enrichment data for user {user.id}")

    except Exception as e:
        logger.error(f"Error merging enrichment data: {e}", exc_info=True)


async def _merge_social_data(user, extracted: dict):
    """Merge social media extracted data into user profile."""
    try:
        update = UserUpdate()
        changed = False

        bio = extracted.get("bio")
        if bio and not user.bio:
            update.bio = bio
            changed = True

        profession = extracted.get("profession")
        if profession and not user.profession:
            update.profession = profession
            changed = True

        company = extracted.get("company")
        if company and not user.company:
            update.company = company
            changed = True

        interests = extracted.get("interests", [])
        if interests:
            current = set(user.interests or [])
            added = [i for i in interests if i.lower() not in {x.lower() for x in current}]
            if added:
                update.interests = list(current) + added
                changed = True

        skills = extracted.get("skills", [])
        if skills:
            current = set(user.skills or [])
            added = [s for s in skills if s.lower() not in {x.lower() for x in current}]
            if added:
                update.skills = list(current) + added
                changed = True

        looking_for = extracted.get("looking_for")
        if looking_for and not user.looking_for:
            update.looking_for = looking_for
            changed = True

        city = extracted.get("city_current")
        if city and not user.city_current:
            update.city_current = city
            changed = True

        if changed:
            await user_repo.update(user.id, update)
            logger.info(f"Merged social data for user {user.id}")

    except Exception as e:
        logger.error(f"Error merging social data: {e}", exc_info=True)


async def _regenerate_embeddings(user):
    """Regenerate embeddings after profile change."""
    try:
        fresh_user = await user_repo.get_by_id(user.id)
        if not fresh_user:
            return
        result = await embedding_service.generate_embeddings(fresh_user)
        if result:
            await user_repo.update_embeddings(fresh_user.id, *result)
            logger.info(f"Regenerated embeddings for user {fresh_user.id}")
    except Exception as e:
        logger.error(f"Error regenerating embeddings: {e}", exc_info=True)


def _safe_parse_json(raw: str) -> Optional[dict]:
    """Parse JSON from LLM response."""
    if not raw:
        return None
    try:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"Failed to parse enrichment JSON: {raw[:200]}")
        return None
