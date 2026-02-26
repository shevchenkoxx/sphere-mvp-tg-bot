"""
Intent-based story onboarding content.
Stories are selected by user intent (friends/dating/activities/networking/open).
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

# ── Intent keywords for "Something specific" classification ─────────────────
INTENT_KEYWORDS: Dict[str, list] = {
    "friends": ["friend", "buddy", "people", "hangout", "company", "lonel", "social"],
    "dating": ["date", "love", "partner", "relationship", "someone special", "romance", "girlfriend", "boyfriend"],
    "activities": ["sport", "tennis", "run", "hike", "activity", "gym", "walk", "yoga", "climb", "surf", "bike", "swim", "football", "basketball"],
    "networking": ["work", "job", "cofounder", "co-founder", "startup", "network", "business", "career", "mentor", "invest", "collab"],
}


def classify_intent(text: str) -> str:
    """Classify free-text into an intent. Returns intent key or 'open'."""
    text_lower = text.lower()
    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "open"


# ── Shared content ─────────────────────────────────────────────────────────

INTENT_QUESTION = "Hey 👋\n\nWhat brings you here?"

HOW_IT_WORKS = (
    "Here's how it works:\n\n"
    "🔍  Sphere reads your chats and learns\n"
    "      what makes you — <b>you</b>\n\n"
    "🎮  Fun games reveal your personality\n\n"
    "💫  AI finds people you'd actually\n"
    "      want to meet\n\n"
    "No forms. No quizzes.\n"
    "Just the real you."
)

GAME_QUESTION = "Speaking of games — let's try one ⚡\n\nFriday night. What's your vibe?"

GAME_OPTIONS = ["🎉 Out with people", "🏠 Cozy night in"]

GAME_AFTER = (
    "{feedback}! {pct}% picked the same 🎯\n\n"
    "These little moments tell Sphere\n"
    "more than any profile ever could."
)

CTA = (
    "Your turn ✨\n\n"
    "Tell Sphere about yourself —\n"
    "one voice message or a few texts.\n\n"
    "That's all it takes."
)

# ── Per-intent: Hooks ──────────────────────────────────────────────────────

HOOKS = {
    "friends": (
        "The average adult hasn't made\n"
        "a new friend in <b>5 years</b> 😳\n\n"
        "Not because they don't want to.\n"
        "Because there's no good way.\n\n"
        "Here's how Sphere fixes that 👇"
    ),
    "dating": (
        "<b>78%</b> of people are tired of dating apps 😮‍💨\n\n"
        "Swiping. Small talk. Ghosting. Repeat.\n\n"
        "What if real connections started from\n"
        "real conversations instead? 👇"
    ),
    "activities": (
        "Running buddy? Tennis partner?\n"
        "Someone to explore the city with? 🏃‍♂️\n\n"
        "Finding people who share your vibe\n"
        "shouldn't be this hard.\n\n"
        "Here's how Sphere makes it easy 👇"
    ),
    "networking": (
        "The best opportunities come\n"
        "from <b>people</b> — not job boards 🚀\n\n"
        "Real conversations → real connections\n"
        "→ real opportunities.\n\n"
        "Here's how it works 👇"
    ),
    "open": (
        "Everyone needs their people 💛\n\n"
        "Friends. Partners. Adventure buddies.\n"
        "Mentors. Co-founders.\n\n"
        "Sphere finds them — based on\n"
        "who you really are 👇"
    ),
}

# ── Per-intent: Characters ─────────────────────────────────────────────────

CHARACTERS = {
    "friends": (
        "Meet <b>Mia</b> 👋\n\n"
        "Moved to a new city 3 months ago.\n"
        "Joined a few Telegram groups —\n"
        "hundreds of people, zero real connections.\n\n"
        "Then Sphere started watching her chats.\n"
        "No forms, no profiles — just her\n"
        "real conversations."
    ),
    "dating": (
        "Meet <b>Sarah</b> 👋\n\n"
        "Deleted Tinder for the 3rd time.\n"
        "She wanted someone who actually\n"
        "gets her humor, not just her photos.\n\n"
        "Then Sphere started watching her chats.\n"
        "No swiping — just her real personality\n"
        "showing through."
    ),
    "activities": (
        "Meet <b>Luca</b> 👋\n\n"
        "Plays tennis twice a week.\n"
        "His partner moved away last month.\n"
        "Finding someone at his level?\n"
        "Impossible in a group chat.\n\n"
        "Then Sphere started watching."
    ),
    "networking": (
        "Meet <b>Alex</b> 👋\n\n"
        "Solo founder building a SaaS product.\n"
        "Had the code, but the UI was a mess.\n"
        "Demo day in one week.\n\n"
        "He was in a startup chat with 200 people.\n"
        "Didn't know anyone who could help."
    ),
    "open": (
        "Meet <b>Kira</b> 👋\n\n"
        "New in town. Scrolling through\n"
        "Telegram groups full of strangers.\n\n"
        "Wanted to find her people —\n"
        "friends, gym buddies, maybe more.\n\n"
        "Then Sphere started watching her chats."
    ),
}

# ── Per-intent: Match cards (full card + outcome in one) ───────────────────

MATCH_CARDS = {
    "friends": (
        "And then — a private message 💫\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "🤝  <b>New match for Mia</b>\n\n"
        "<b>Nora S.</b>\n\n"
        "✦ Both love hiking\n"
        "✦ Both new in town\n"
        "✦ Both free on weekends\n\n"
        "💬 <i>\"Hey! There's a great trail\n"
        "30 min from here — Saturday morning?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "They went on that hike.\n"
        "Now it's their weekly tradition 🚶‍♀️"
    ),
    "dating": (
        "And then — a private message 💫\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "💕  <b>New match for Sarah</b>\n\n"
        "<b>Daniel K.</b>\n\n"
        "✦ Same humor\n"
        "✦ Same taste in music\n"
        "✦ Both think first dates\n"
        "   should be walks, not dinners\n\n"
        "💬 <i>\"There's a small jazz night\n"
        "Thursday — want to check it out?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "They went. Six months later —\n"
        "still together 💛"
    ),
    "activities": (
        "And then — a private message 💫\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡  <b>New match for Luca</b>\n\n"
        "<b>Marco T.</b>\n\n"
        "✦ Lives 10 min away\n"
        "✦ Plays tennis twice a week\n"
        "✦ Same level, looking for a partner\n\n"
        "💬 <i>\"Hey! Courts near the park,\n"
        "Sunday 10am — you in?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "They now play every Sunday.\n"
        "Found 2 more players through Sphere 🎾"
    ),
    "networking": (
        "And then — a private message 💫\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "💼  <b>New match for Alex</b>\n\n"
        "<b>Sara T.</b> — Product Designer\n\n"
        "✦ Redesigned 3 SaaS products this year\n"
        "✦ Looking for a founder who cares about UX\n"
        "✦ 94% compatibility\n\n"
        "💬 <i>\"Your landing page is bold.\n"
        "I have ideas — coffee this week?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "She redesigned his product in 5 days.\n"
        "Two months later — co-founder 🚀"
    ),
    "open": None,  # uses "friends"
}


def get_story(intent: str) -> dict:
    """Get story content for the given intent."""
    card_intent = intent if MATCH_CARDS.get(intent) else "friends"

    return {
        "hook": HOOKS.get(intent, HOOKS["open"]),
        "character": CHARACTERS.get(intent, CHARACTERS["open"]),
        "how_it_works": HOW_IT_WORKS,
        "game_question": GAME_QUESTION,
        "game_options": GAME_OPTIONS,
        "game_after": GAME_AFTER,
        "match_card": MATCH_CARDS[card_intent],
        "cta": CTA,
    }
