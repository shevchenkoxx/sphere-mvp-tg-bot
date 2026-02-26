# Story Onboarding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the static /start welcome with a branded cinematic story that shows users how Sphere works through narrative, with context-aware LLM generation per community/event/language.

**Architecture:** New `StoryService` generates and caches stories via LLM. New `story_onboarding.py` handler plays the story with timed delays and 2 interactive callbacks. `start.py` redirects new users to story before agent onboarding. Stories are cached in-memory by (mode, context_id, lang).

**Tech Stack:** aiogram 3.x (handlers, FSM, callbacks), OpenAI GPT-4o-mini (story generation + translation), asyncio (delays)

---

### Task 1: FSM States for Story

**Files:**
- Modify: `adapters/telegram/states/onboarding.py:109-113`

**Step 1: Add StoryOnboarding states**

Add this class BEFORE `AgentOnboarding` (before line 109):

```python
class StoryOnboarding(StatesGroup):
    """FSM states for branded story onboarding"""
    playing = State()           # Story is auto-playing with delays
    waiting_game_tap = State()  # Interactive #1: mini-game choice
    waiting_next_tap = State()  # Interactive #2: "see what happened"
```

**Step 2: Verify**

Run: `python3 -m py_compile adapters/telegram/states/onboarding.py`
Expected: no errors

**Step 3: Commit**

```bash
git add adapters/telegram/states/onboarding.py
git commit -m "feat(story): add StoryOnboarding FSM states"
```

---

### Task 2: Story Service — Core Generation + Caching

**Files:**
- Create: `core/services/story_service.py`

**Step 1: Create the story service**

```python
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
```

**Step 2: Verify**

Run: `python3 -m py_compile core/services/story_service.py`

**Step 3: Commit**

```bash
git add core/services/story_service.py
git commit -m "feat(story): add StoryService — generation, translation, caching"
```

---

### Task 3: Story Handler — Message Playback + Interactive Callbacks

**Files:**
- Create: `adapters/telegram/handlers/story_onboarding.py`

**Step 1: Create the handler**

```python
"""
Story onboarding handler — plays branded cinematic story with interactive moments.
"""

import asyncio
import random
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from adapters.telegram.states.onboarding import StoryOnboarding

logger = logging.getLogger(__name__)
router = Router(name="story_onboarding")

# Delay between auto-play steps (seconds)
STEP_DELAY = 2.5
SHORT_DELAY = 2.0
LONG_DELAY = 3.0


async def start_story(message: Message, state: FSMContext, mode: str,
                       context_id: str = "default", lang: str = "en",
                       community_name: str = None, member_count: int = None,
                       topics: list = None, event_name: str = None,
                       event_code: str = None, community_id: str = None):
    """Entry point: generate story and start playing it."""
    from adapters.telegram.loader import story_service

    # Preserve context for onboarding later
    fsm_data = {}
    if community_id:
        fsm_data["community_id"] = community_id
    if community_name:
        fsm_data["community_name"] = community_name
    if event_code:
        fsm_data["pending_event"] = event_code
    fsm_data["story_lang"] = lang
    fsm_data["story_mode"] = mode
    await state.update_data(**fsm_data)

    # Get story
    story = await story_service.get_story(
        mode=mode,
        context_id=context_id,
        lang=lang,
        community_name=community_name,
        member_count=member_count,
        topics=topics,
        event_name=event_name,
    )

    steps = story.get("steps", [])
    game_options = story.get("game_options", ["Option A", "Option B"])

    await state.update_data(story_steps=steps, story_game_options=game_options)
    await state.set_state(StoryOnboarding.playing)

    if mode == "event":
        await _play_event_story(message, state, steps)
    else:
        await _play_community_story(message, state, steps, game_options)


async def _play_community_story(message: Message, state: FSMContext,
                                 steps: list, game_options: list):
    """Play the 10-step community/global story."""
    chat_id = message.chat.id

    from adapters.telegram.loader import bot

    # Step 1: Hook
    await bot.send_message(chat_id, steps[0], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 2: Character 1
    await bot.send_message(chat_id, steps[1], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 3: Observation
    await bot.send_message(chat_id, steps[2], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 4: Game — INTERACTIVE #1
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=game_options[0], callback_data="story_game_0"),
            InlineKeyboardButton(text=game_options[1], callback_data="story_game_1"),
        ]
    ])
    await bot.send_message(chat_id, steps[3], reply_markup=kb, parse_mode="HTML")
    await state.set_state(StoryOnboarding.waiting_game_tap)
    # Flow continues in handle_game_tap callback


async def _continue_after_game(callback: CallbackQuery, state: FSMContext):
    """Continue community story after game interaction."""
    data = await state.get_data()
    steps = data.get("story_steps", [])
    chat_id = callback.message.chat.id

    from adapters.telegram.loader import bot

    # Step 5: Character 2
    await bot.send_message(chat_id, steps[5], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 6: AI Matching
    await bot.send_message(chat_id, steps[6], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 7: Match Preview — INTERACTIVE #2
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👀 See what happened next", callback_data="story_next")]
    ])
    await bot.send_message(chat_id, steps[7], reply_markup=kb, parse_mode="HTML")
    await state.set_state(StoryOnboarding.waiting_next_tap)
    # Flow continues in handle_next_tap callback


async def _continue_after_match(callback: CallbackQuery, state: FSMContext):
    """Continue community story after match preview interaction."""
    data = await state.get_data()
    steps = data.get("story_steps", [])
    chat_id = callback.message.chat.id
    lang = data.get("story_lang", "en")

    from adapters.telegram.loader import bot

    # Step 8: Resolution
    await bot.send_message(chat_id, steps[8], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 9: Bonus use cases
    await bot.send_message(chat_id, steps[9], parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Step 10: CTA
    cta_text = "🚀 Let's go" if lang == "en" else "🚀 Поехали"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cta_text, callback_data="story_start_onboarding")]
    ])
    await bot.send_message(chat_id, steps[10], reply_markup=kb, parse_mode="HTML")
    # Wait for CTA tap — handled by callback


async def _play_event_story(message: Message, state: FSMContext, steps: list):
    """Play the 7-step events story."""
    chat_id = message.chat.id
    data = await state.get_data()
    lang = data.get("story_lang", "en")

    from adapters.telegram.loader import bot

    # Step 1: Hook
    await bot.send_message(chat_id, steps[0], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 2: Create
    await bot.send_message(chat_id, steps[1], parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Step 3: Share & Fill
    await bot.send_message(chat_id, steps[2], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 4: Match Preview — INTERACTIVE
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⚡ See what happened" if lang == "en" else "⚡ Что произошло",
            callback_data="story_next"
        )]
    ])
    await bot.send_message(chat_id, steps[3], reply_markup=kb, parse_mode="HTML")
    await state.set_state(StoryOnboarding.waiting_next_tap)


async def _continue_event_after_match(callback: CallbackQuery, state: FSMContext):
    """Continue events story after match preview interaction."""
    data = await state.get_data()
    steps = data.get("story_steps", [])
    chat_id = callback.message.chat.id
    lang = data.get("story_lang", "en")

    from adapters.telegram.loader import bot

    # Step 5: Resolution
    await bot.send_message(chat_id, steps[4], parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Step 6: Bonus examples
    await bot.send_message(chat_id, steps[5], parse_mode="HTML")
    await asyncio.sleep(STEP_DELAY)

    # Step 7a: Value message
    await bot.send_message(chat_id, steps[6], parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Step 7b: CTA
    cta_text_create = "🚀 Create an event" if lang == "en" else "🚀 Создать ивент"
    cta_text_join = "🎫 Join one" if lang == "en" else "🎫 Присоединиться"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=cta_text_create, callback_data="story_create_event"),
            InlineKeyboardButton(text=cta_text_join, callback_data="story_start_onboarding"),
        ]
    ])
    await bot.send_message(chat_id, steps[7], reply_markup=kb, parse_mode="HTML")


# ── Callback handlers ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("story_game_"), StoryOnboarding.waiting_game_tap)
async def handle_game_tap(callback: CallbackQuery, state: FSMContext):
    """Interactive #1: user tapped a game option."""
    await callback.answer()

    choice_idx = int(callback.data.split("_")[-1])
    data = await state.get_data()
    steps = data.get("story_steps", [])
    game_options = data.get("story_game_options", ["Option A", "Option B"])

    chosen = game_options[choice_idx] if choice_idx < len(game_options) else "that"
    pct = random.randint(58, 78)
    feedbacks = ["Nice", "Great choice", "Interesting", "Good pick"]
    feedback = random.choice(feedbacks)

    # Format step 4b with placeholders
    after_text = steps[4] if len(steps) > 4 else "Nice! Most people agree."
    after_text = after_text.replace("{feedback}", feedback)
    after_text = after_text.replace("{pct}", str(pct))
    after_text = after_text.replace("{choice}", chosen)

    # Remove the keyboard from the game message
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    from adapters.telegram.loader import bot
    await bot.send_message(callback.message.chat.id, after_text, parse_mode="HTML")
    await asyncio.sleep(SHORT_DELAY)

    # Continue story
    await _continue_after_game(callback, state)


@router.callback_query(F.data == "story_next", StoryOnboarding.waiting_next_tap)
async def handle_next_tap(callback: CallbackQuery, state: FSMContext):
    """Interactive #2: user tapped 'see what happened next'."""
    await callback.answer()

    # Remove keyboard
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()
    mode = data.get("story_mode", "global")

    if mode == "event":
        await _continue_event_after_match(callback, state)
    else:
        await _continue_after_match(callback, state)


@router.callback_query(F.data == "story_start_onboarding")
async def handle_start_onboarding(callback: CallbackQuery, state: FSMContext):
    """CTA: user tapped 'Let's go' — transition to real onboarding."""
    await callback.answer()

    # Remove keyboard
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()
    event_code = data.get("pending_event")
    event_name = data.get("event_name")
    community_id = data.get("community_id")
    community_name = data.get("community_name")

    # Clear story-specific FSM data but keep context
    await state.update_data(story_steps=None, story_game_options=None, story_mode=None, story_lang=None)

    # Dispatch to the configured onboarding version
    from adapters.telegram.handlers.start import _start_onboarding_with_context
    await _start_onboarding_with_context(
        callback.message, state,
        event_name=event_name,
        event_code=event_code,
        community_id=community_id,
        community_name=community_name,
    )


@router.callback_query(F.data == "story_create_event")
async def handle_create_event(callback: CallbackQuery, state: FSMContext):
    """Events CTA: user wants to create an event."""
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()

    # If user is not onboarded, onboard first
    from adapters.telegram.loader import user_service
    from core.domain.models import MessagePlatform
    user = await user_service.get_or_create_user(
        platform=MessagePlatform.TELEGRAM,
        platform_user_id=str(callback.from_user.id),
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )

    if not user.onboarding_completed:
        await state.update_data(post_onboarding_action="create_event")
        from adapters.telegram.handlers.start import _start_onboarding_with_context
        await _start_onboarding_with_context(callback.message, state)
    else:
        # Go directly to event creation
        lang = data.get("story_lang", "en")
        await callback.message.answer(
            "Let's create your event! Send me the event name:" if lang == "en"
            else "Создаем ивент! Отправь мне название:",
        )
        from adapters.telegram.states.onboarding import EventStates
        await state.set_state(EventStates.waiting_name)
```

**Step 2: Verify**

Run: `python3 -m py_compile adapters/telegram/handlers/story_onboarding.py`

**Step 3: Commit**

```bash
git add adapters/telegram/handlers/story_onboarding.py
git commit -m "feat(story): add story handler — playback, interactions, callbacks"
```

---

### Task 4: Wire Story Service into Loader

**Files:**
- Modify: `adapters/telegram/loader.py:30-97`

**Step 1: Add import after line 35 (BingoService import)**

```python
from core.services.story_service import StoryService
```

**Step 2: Add service instantiation after `bingo_service` (after line 97)**

```python
story_service = StoryService()
```

**Step 3: Verify**

Run: `python3 -m py_compile adapters/telegram/loader.py`

**Step 4: Commit**

```bash
git add adapters/telegram/loader.py
git commit -m "feat(story): wire StoryService into loader"
```

---

### Task 5: Register Story Router

**Files:**
- Modify: `adapters/telegram/loader.py` (router registration section, after line 97)

Find where routers are included (look for `dp.include_router`). Add:

```python
from adapters.telegram.handlers.story_onboarding import router as story_router
dp.include_router(story_router)
```

Place it BEFORE the start router, so story callbacks get priority over generic start handlers.

**Step 1: Verify**

Run: `python3 -m py_compile adapters/telegram/loader.py`

**Step 2: Commit**

```bash
git add adapters/telegram/loader.py
git commit -m "feat(story): register story_onboarding router"
```

---

### Task 6: Redirect New Users to Story in start.py

**Files:**
- Modify: `adapters/telegram/handlers/start.py:161-211` (`_start_onboarding_with_context`)
- Modify: `adapters/telegram/handlers/start.py:328-380` (`start_command`)
- Modify: `adapters/telegram/handlers/start.py:262-293` (community deep link)
- Modify: `adapters/telegram/handlers/start.py:300-322` (event deep link)

**Step 1: Modify `_start_onboarding_with_context` (line 161)**

Replace the entire function body to route through story first:

```python
async def _start_onboarding_with_context(message, state, event_name=None, event_code=None,
                                          community_id=None, community_name=None,
                                          skip_story=False):
    """Start onboarding with optional event/community context.
    Shows story first (unless skip_story=True), then dispatches to onboarding."""
    lang = detect_lang(message)

    # Store context in FSM state
    state_data = {}
    if event_code:
        state_data["pending_event"] = event_code
    if event_name:
        state_data["event_name"] = event_name
    if community_id:
        state_data["community_id"] = community_id
    if community_name:
        state_data["community_name"] = community_name
    if state_data:
        await state.update_data(**state_data)

    # Check if we should skip story (called from story CTA callback)
    if skip_story:
        await _dispatch_onboarding(message, state, lang, event_name, event_code)
        return

    # Route through story onboarding
    from adapters.telegram.handlers.story_onboarding import start_story

    if event_code:
        # Events story
        await start_story(
            message, state, mode="event",
            context_id=event_code or "default", lang=lang,
            event_name=event_name, event_code=event_code,
            community_id=community_id,
        )
    elif community_id:
        # Community story — get topics from observation service if available
        topics = []
        try:
            from adapters.telegram.loader import community_repo
            community = await community_repo.get_by_id(community_id) if community_id else None
        except Exception:
            community = None

        await start_story(
            message, state, mode="community",
            context_id=community_id, lang=lang,
            community_name=community_name,
            member_count=community.member_count if community else None,
            topics=topics,
            community_id=community_id,
        )
    else:
        # Global story
        await start_story(
            message, state, mode="global",
            context_id="default", lang=lang,
        )


async def _dispatch_onboarding(message, state, lang, event_name=None, event_code=None):
    """Dispatch to the configured onboarding version (called after story completes)."""
    if ONBOARDING_VERSION == "agent":
        from adapters.telegram.handlers.onboarding_agent import start_agent_onboarding
        await start_agent_onboarding(message, state, event_name=event_name, event_code=event_code)
    elif ONBOARDING_VERSION == "intent":
        from adapters.telegram.handlers.onboarding_intent import start_intent_onboarding
        await start_intent_onboarding(message, state, event_name=event_name, event_code=event_code)
    elif ONBOARDING_VERSION == "audio":
        from adapters.telegram.handlers.onboarding_audio import start_audio_onboarding
        await start_audio_onboarding(message, state, event_name=event_name, event_code=event_code)
    elif ONBOARDING_VERSION == "v2":
        from adapters.telegram.handlers.onboarding_v2 import start_conversational_onboarding
        await start_conversational_onboarding(message, state, event_name=event_name, event_code=event_code)
    else:
        await state.update_data(language=lang)
        text = "👋 Привет! Как тебя зовут?" if lang == "ru" else "👋 Hi! What's your name?"
        await message.answer(text)
        from adapters.telegram.states.onboarding import OnboardingStates
        await state.set_state(OnboardingStates.waiting_name)
```

**Step 2: Update `start_command` (line 353-379)**

Replace the `else` block (new users) with:

```python
    else:
        # New user — start story onboarding
        await _start_onboarding_with_context(message, state)
```

This replaces the large if/elif ONBOARDING_VERSION block in start_command. The version dispatch now lives in `_dispatch_onboarding`.

**Step 3: Update story_onboarding.py — change `_start_onboarding_with_context` call to pass `skip_story=True`**

In `story_onboarding.py`, find the `handle_start_onboarding` callback and update:

```python
    await _start_onboarding_with_context(
        callback.message, state,
        event_name=event_name,
        event_code=event_code,
        community_id=community_id,
        community_name=community_name,
        skip_story=True,  # Don't loop back into story!
    )
```

**Step 4: Verify all modified files**

```bash
python3 -m py_compile adapters/telegram/handlers/start.py
python3 -m py_compile adapters/telegram/handlers/story_onboarding.py
```

**Step 5: Commit**

```bash
git add adapters/telegram/handlers/start.py adapters/telegram/handlers/story_onboarding.py
git commit -m "feat(story): redirect new users through story before onboarding"
```

---

### Task 7: Integration Test + Edge Cases

**Files:**
- Modify: `adapters/telegram/handlers/story_onboarding.py` (add text handler for ignoring messages during story)

**Step 1: Add a catch-all text handler for story states**

Add to `story_onboarding.py` before the callback handlers:

```python
@router.message(StoryOnboarding.playing)
@router.message(StoryOnboarding.waiting_game_tap)
@router.message(StoryOnboarding.waiting_next_tap)
async def ignore_text_during_story(message: Message, state: FSMContext):
    """Ignore text messages while story is playing. User should tap buttons."""
    pass  # Silently ignore — story auto-plays or waits for button tap
```

**Step 2: Verify the full compilation**

```bash
python3 -m py_compile adapters/telegram/states/onboarding.py
python3 -m py_compile core/services/story_service.py
python3 -m py_compile adapters/telegram/handlers/story_onboarding.py
python3 -m py_compile adapters/telegram/handlers/start.py
python3 -m py_compile adapters/telegram/loader.py
```

**Step 3: Commit**

```bash
git add adapters/telegram/handlers/story_onboarding.py
git commit -m "feat(story): ignore text messages during story playback"
```

---

### Task 8: Final Commit + Push

**Step 1: Git status**

```bash
git status
```

Verify all files are committed, no untracked changes.

**Step 2: Push to deploy**

```bash
git push origin community-v1
```

Railway auto-deploys. Wait ~1-2 min, then test:
1. Send `/start` to @Matchd_bot (as a new user or after `/reset`)
2. Verify the story plays: hook → characters → game interaction → match preview → CTA
3. Tap "Let's go" → verify agent onboarding starts with preserved context

---

## File Summary

| Action | File | Purpose |
|--------|------|---------|
| Modify | `adapters/telegram/states/onboarding.py` | Add `StoryOnboarding` FSM states |
| Create | `core/services/story_service.py` | Story generation, LLM calls, caching |
| Create | `adapters/telegram/handlers/story_onboarding.py` | Story playback, delays, callbacks |
| Modify | `adapters/telegram/loader.py` | Wire `StoryService` + register router |
| Modify | `adapters/telegram/handlers/start.py` | Redirect new users to story first |
