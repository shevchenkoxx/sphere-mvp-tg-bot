"""
Story generation service for branded onboarding.
Generates context-aware stories via LLM, caches per (mode, context_id, lang).
"""

import json
import logging
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from config.settings import settings

logger = logging.getLogger(__name__)

# In-memory cache: key = "{mode}_{context_id}_{lang}" -> dict of steps
_story_cache: Dict[str, dict] = {}
_MAX_CACHE = 100

# Category pool for bonus examples
CATEGORIES = ["professional", "friendship", "dating", "mentorship", "relocation", "activity"]


def _cache_key(mode: str, context_id: str, lang: str) -> str:
    return f"{mode}_{context_id}_{lang}"


# Lazy singleton OpenAI client
_client: Optional[AsyncOpenAI] = None

def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
    return _client


# ── Hardcoded EN global default ────────────────────────────────────────────
GLOBAL_DEFAULT_EN = {
    "mode": "global",
    "main_category": "professional",
    "bonus_categories": ["activity", "dating"],
    "steps": [
        # Step 1: Hook
        (
            "Sphere\n\n"
            "Where meaningful connections happen.\n\n"
            "Last month, two strangers in a Telegram group\n"
            "discovered they were building the same dream.\n\n"
            "This is how it happened."
        ),
        # Step 2: Character 1
        (
            "Meet Alex — a solo founder building a SaaS product.\n"
            "He had the code, but the UI was a mess.\n"
            "Demo day in one week.\n\n"
            "He was in a startup chat with 200 people.\n"
            "He didn't know anyone who could help."
        ),
        # Step 3: Feature: Observation
        (
            "While Alex vented about UI struggles\n"
            "and asked for feedback on his landing page —\n\n"
            "Sphere quietly mapped his skills, needs,\n"
            "and what he was looking for.\n\n"
            "No forms. No quizzes. Just real conversations."
        ),
        # Step 4: Feature: Games (text before interactive)
        (
            "Then a game appeared in the group:\n\n"
            "<b>This or That?</b>\n\n"
            "Build in public or stealth mode?"
        ),
        # Step 4b: After interaction
        (
            "{feedback}! {pct}% of the group picked the same.\n\n"
            "These micro-interactions reveal more about\n"
            "people than any profile ever could.\n\n"
            "Alex picked {choice} too."
        ),
        # Step 5: Character 2
        (
            "Meanwhile, Kira — a freelance product designer —\n"
            "had just moved to the city.\n\n"
            "She was looking for an interesting project\n"
            "to sink her teeth into.\n\n"
            "Sphere noticed: Alex needs design help.\n"
            "Kira needs a meaningful project.\n"
            "Different skills. Same drive."
        ),
        # Step 6: Feature: AI Matching
        (
            "Sphere's AI connected the dots:\n\n"
            "✦ Both obsessed with product quality\n"
            "✦ Alex needs a designer — yesterday\n"
            "✦ Kira wants a real project, not another landing page\n"
            "✦ 94% compatibility\n\n"
            "It sent them both a private message."
        ),
        # Step 7: Match preview (before interactive)
        (
            "Here's what Alex saw:\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💫 <b>New match</b>\n\n"
            "<b>Kira M.</b> — Product Designer\n\n"
            "<i>✨ Why you'd click:</i>\n"
            "She's redesigned 3 SaaS products this year.\n"
            "You need exactly that — and she's looking for\n"
            "a founder who cares about UX as much as code.\n\n"
            "💬 <i>Start with:</i>\n"
            "\"Kira, saw your portfolio — your onboarding\n"
            "flows are insane. I have a demo in 7 days\n"
            "and my UI needs saving. Coffee?\"\n\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        ),
        # Step 8: Resolution (after interaction)
        (
            "She redesigned his product in 5 days.\n"
            "The demo went perfectly.\n\n"
            "Three investors asked for a follow-up.\n\n"
            "Two months later, Kira became co-founder.\n\n"
            "None of this would have happened\n"
            "in a 200-person group chat."
        ),
        # Step 9: Bonus use cases
        (
            "And it's not just about work:\n\n"
            "🚶 A Sunday walk in the park — 3 strangers joined,\n"
            "turned into a weekly tradition\n\n"
            "💕 Two people in a book club turned out to share\n"
            "the same taste in everything — not just books.\n"
            "They've been dating for 4 months."
        ),
        # Step 10: CTA
        (
            "Your turn.\n\n"
            "Tell me about yourself and I'll find\n"
            "people you should know.\n\n"
            "One voice message or a few texts —\n"
            "that's all it takes."
        ),
    ],
    "game_options": ["🚀 Build in public", "🥷 Stealth mode"],
}

# ── Hardcoded EN events default ────────────────────────────────────────────
EVENTS_DEFAULT_EN = {
    "mode": "event",
    "steps": [
        # Step 1: Hook
        (
            "What if your next event ran itself?\n\n"
            "Last month, Sasha organized a meetup for 40 people.\n"
            "He spent zero time on introductions.\n\n"
            "Everyone already knew who to talk to\n"
            "before they walked in."
        ),
        # Step 2: Create
        (
            "It started with one message:\n\n"
            "  <code>/quickevent AI &amp; Coffee Warsaw</code>\n\n"
            "That's it. Sphere created the event page,\n"
            "generated a QR code, and gave Sasha\n"
            "a link to share.\n\n"
            "30 seconds. Done."
        ),
        # Step 3: Share & Fill
        (
            "Sasha dropped the link in 3 group chats.\n\n"
            "People clicked → quick voice intro → profile ready.\n\n"
            "In 2 days: 40 people signed up.\n\n"
            "Sphere was already analyzing who\n"
            "should meet whom."
        ),
        # Step 4: Match Preview (before interactive)
        (
            "Here's what attendees saw the morning of the event:\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 <b>Your Top 3 at AI & Coffee</b>\n\n"
            "1. <b>Maria K.</b> — building AI for healthcare\n"
            "   <i>\"You both think LLMs will reshape diagnostics\"</i>\n\n"
            "2. <b>Dan R.</b> — ex-Google, launching a startup\n"
            "   <i>\"He's looking for exactly your skillset\"</i>\n\n"
            "3. <b>Yuki T.</b> — AI researcher → founder\n"
            "   <i>\"Same journey, 6 months apart\"</i>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Imagine walking in and already knowing\n"
            "the 3 most interesting people to find."
        ),
        # Step 5: Resolution (after interactive)
        (
            "40 people. 94 meaningful connections made.\n\n"
            "<i>\"Best networking event I've been to.\n"
            "I didn't waste a single conversation.\"</i>\n"
            "— attendee feedback\n\n"
            "Sasha didn't plan a single icebreaker.\n"
            "Sphere did all the matching."
        ),
        # Step 6: Bonus examples
        (
            "People create all kinds of events:\n\n"
            "🚶 Sunday walk in the park — 3 strangers joined,\n"
            "turned into a weekly tradition\n\n"
            "🎾 A couple looking for tennis partners —\n"
            "found 4 people nearby, now they play every Sunday\n\n"
            "🎵 Going to a concert alone?\n"
            "Sphere finds people with the same taste\n"
            "who are also going"
        ),
        # Step 7a: Value message
        (
            "Here's the thing:\n\n"
            "You create an event in 30 seconds.\n"
            "Share the link.\n\n"
            "Then forget about it.\n\n"
            "Sphere works in the background —\n"
            "finding the right people,\n"
            "matching them by interests,\n"
            "telling everyone who to talk to.\n\n"
            "You show up. The connections are already there."
        ),
        # Step 7b: CTA
        "Your turn.",
    ],
}


COMMUNITY_STORY_PROMPT = """You are a storytelling engine for Sphere — a Telegram bot that connects people in communities through AI matching.

Generate a branded onboarding story for a new user joining a community.

COMMUNITY: {community_name}
MEMBERS: {member_count}
TOP TOPICS: {topics}
LANGUAGE: {lang}

You must generate a story following this EXACT structure. Output valid JSON with these keys:

{{
  "main_category": "one of: professional, friendship, dating, mentorship, relocation, activity",
  "bonus_categories": ["category1", "category2"],
  "steps": [
    "step_1_hook",
    "step_2_character1",
    "step_3_observation",
    "step_4_game_before",
    "step_4b_game_after",
    "step_5_character2",
    "step_6_matching",
    "step_7_match_preview",
    "step_8_resolution",
    "step_9_bonus",
    "step_10_cta"
  ],
  "game_options": ["Option A", "Option B"]
}}

RULES:
- Each step: 2-5 lines max. Short, punchy, cinematic.
- Characters: realistic names fitting the community's likely demographic
- Main story: pick the category most relevant to this community's topics
- Bonus examples (step 9): MUST be different categories from main story. Include at least one casual/simple example (walk, sports). Start with the simplest activity.
- step_4_game_before: a "This or That?" question relevant to the community
- step_4b_game_after: use {{feedback}}, {{pct}}, {{choice}} placeholders
- step_7_match_preview: format as a realistic match card with name, role, "Why you'd click", and icebreaker
- step_10_cta: always end with "tell me about yourself" + "voice message or texts"
- Tone: warm, confident, premium. Not corporate, not casual.
- If LANGUAGE is not "en": write naturally in that language, don't transliterate.
- All text uses Telegram HTML formatting (<b>, <i>, <code>).
- Do NOT include step labels like "Step 1:" — just the narrative text.
"""

TRANSLATION_PROMPT = """Translate this onboarding story to {lang}. Keep the tone warm, confident, premium.
Preserve all HTML tags (<b>, <i>, <code>), placeholders ({{feedback}}, {{pct}}, {{choice}}), and emoji exactly as-is.
Translate naturally — don't transliterate.

Story JSON:
{story_json}

Output: same JSON structure, all text translated to {lang}."""


class StoryService:
    """Generates and caches branded onboarding stories."""

    async def get_story(self, mode: str, context_id: str, lang: str,
                        community_name: str = None, member_count: int = None,
                        topics: List[str] = None,
                        event_name: str = None) -> dict:
        """Get or generate a story. Returns dict with 'steps', 'game_options', etc."""
        key = _cache_key(mode, context_id, lang)

        # Check cache
        if key in _story_cache:
            return _story_cache[key]

        # Global EN — hardcoded, no LLM call
        if mode == "global" and lang == "en":
            _story_cache[key] = GLOBAL_DEFAULT_EN
            return GLOBAL_DEFAULT_EN

        # Events EN — hardcoded
        if mode == "event" and lang == "en" and context_id == "default":
            _story_cache[key] = EVENTS_DEFAULT_EN
            return EVENTS_DEFAULT_EN

        # Need LLM generation
        story = None

        if mode == "community" and lang == "en":
            # Generate community-specific story in EN
            story = await self._generate_community_story(
                community_name or "Community",
                member_count or 0,
                topics or [],
                "en",
            )
        elif lang != "en":
            # Get EN version first, then translate
            en_key = _cache_key(mode, context_id, "en")
            if en_key not in _story_cache:
                if mode == "community":
                    en_story = await self._generate_community_story(
                        community_name or "Community",
                        member_count or 0,
                        topics or [],
                        "en",
                    )
                elif mode == "event":
                    en_story = EVENTS_DEFAULT_EN
                else:
                    en_story = GLOBAL_DEFAULT_EN
                _story_cache[en_key] = en_story

            en_story = _story_cache[en_key]
            story = await self._translate_story(en_story, lang)

        if not story:
            # Fallback
            story = GLOBAL_DEFAULT_EN

        # Cache with LRU eviction
        if len(_story_cache) >= _MAX_CACHE:
            oldest_key = next(iter(_story_cache))
            del _story_cache[oldest_key]
        _story_cache[key] = story
        return story

    async def _generate_community_story(self, name: str, count: int,
                                         topics: List[str], lang: str) -> dict:
        """Generate a community-specific story via LLM."""
        try:
            client = _get_client()
            prompt = COMMUNITY_STORY_PROMPT.format(
                community_name=name,
                member_count=count or "unknown",
                topics=", ".join(topics[:10]) if topics else "general",
                lang=lang,
            )
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)

            # Validate structure
            if "steps" not in data or len(data["steps"]) < 10:
                logger.warning(f"LLM story missing steps, falling back to default")
                return GLOBAL_DEFAULT_EN

            if "game_options" not in data:
                data["game_options"] = ["Option A", "Option B"]

            data["mode"] = "community"
            return data

        except Exception as e:
            logger.error(f"Story generation failed: {e}")
            return GLOBAL_DEFAULT_EN

    async def _translate_story(self, en_story: dict, lang: str) -> dict:
        """Translate a story to another language via LLM."""
        try:
            client = _get_client()
            # Prepare a clean version for translation
            to_translate = {
                "steps": en_story["steps"],
                "game_options": en_story.get("game_options", []),
            }
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": TRANSLATION_PROMPT.format(
                    lang=lang,
                    story_json=json.dumps(to_translate, ensure_ascii=False),
                )}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            translated = json.loads(resp.choices[0].message.content)

            # Merge with metadata from original
            result = {**en_story, **translated}
            result["mode"] = en_story.get("mode", "global")
            return result

        except Exception as e:
            logger.error(f"Story translation to {lang} failed: {e}")
            return en_story  # Fallback to EN
