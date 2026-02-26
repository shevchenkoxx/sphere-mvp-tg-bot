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


# ── Shared content (same for all intents) ──────────────────────────────────

INTENT_QUESTION = "Hey 👋\n\nWhat brings you here?"

HOW_IT_WORKS = (
    "Here's how it works:\n\n"
    "🔍  Sphere reads group chats\n"
    "      and learns what makes you tick\n\n"
    "🎮  Fun games reveal your personality\n\n"
    "💫  AI matches you with people\n"
    "      you'd actually want to meet\n\n"
    "No forms. No quizzes. Just the real you."
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

# ── Per-intent content ─────────────────────────────────────────────────────

HOOKS = {
    "friends": (
        "Did you know? 😳\n\n"
        "The average adult hasn't made\n"
        "a new friend in <b>5 years</b>.\n\n"
        "Not because they don't want to.\n"
        "Because there's no good way."
    ),
    "dating": (
        "<b>78%</b> of people are tired of dating apps.\n\n"
        "Swiping. Small talk. Ghosting.\n"
        "Repeat 🔄\n\n"
        "What if it started from\n"
        "real conversations instead?"
    ),
    "activities": (
        "Running buddy? Tennis partner?\n"
        "Someone to explore the city with? 🏃‍♂️\n\n"
        "Finding people who share your vibe\n"
        "shouldn't be this hard."
    ),
    "networking": (
        "The best opportunities\n"
        "come from <b>people</b>.\n\n"
        "Not job boards. Not cold DMs.\n\n"
        "Real conversations → real connections\n"
        "→ real opportunities 🚀"
    ),
    "open": (
        "Everyone needs their people 💛\n\n"
        "Friends. Partners. Adventure buddies.\n"
        "Mentors. Co-founders.\n\n"
        "What if there was a way to find them\n"
        "based on who you really are?"
    ),
}

MATCH_CARDS = {
    "friends": (
        "Then this happens 💫\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "🤝  <b>New match</b>\n\n"
        "<b>Mia R.</b>\n\n"
        "Both love hiking, both new in town,\n"
        "both free on weekends.\n\n"
        "💬 <i>\"Hey! There's a great trail 30 min\n"
        "from here — Saturday morning?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━"
    ),
    "dating": (
        "Then this happens 💫\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "💕  <b>New match</b>\n\n"
        "<b>Daniel K.</b>\n\n"
        "Same humor, same taste in music.\n"
        "Both think first dates should be\n"
        "walks, not dinners.\n\n"
        "💬 <i>\"There's a small jazz night Thursday —\n"
        "want to check it out?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━"
    ),
    "activities": (
        "Then this happens 💫\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡  <b>New match</b>\n\n"
        "<b>Luca M.</b>\n\n"
        "Lives 10 min away. Plays tennis\n"
        "twice a week. Looking for a partner.\n\n"
        "💬 <i>\"Hey! Courts near the park,\n"
        "Sunday 10am — you in?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━"
    ),
    "networking": (
        "Then this happens 💫\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "💼  <b>New match</b>\n\n"
        "<b>Sara T.</b> — Product Designer\n\n"
        "You need design help.\n"
        "She's looking for a founder who\n"
        "cares about UX. 94% match.\n\n"
        "💬 <i>\"Your landing page is bold.\n"
        "I have ideas — coffee this week?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━"
    ),
    "open": None,  # uses "friends" as default
}

MATCH_OUTCOMES = {
    "friends": "Two strangers went on that hike.\nNow it's their weekly tradition 🚶‍♀️",
    "dating": "They went. Six months later —\nstill together 💛",
    "activities": "They now play every Sunday.\nFound 2 more players through Sphere 🎾",
    "networking": "She redesigned the product.\nTwo months later — co-founder 🚀",
    "open": None,  # uses "friends"
}


def get_story(intent: str) -> dict:
    """Get story content for the given intent."""
    # Normalize — "open" uses friends content for card/outcome
    card_intent = intent if MATCH_CARDS.get(intent) else "friends"
    outcome_intent = intent if MATCH_OUTCOMES.get(intent) else "friends"

    return {
        "hook": HOOKS.get(intent, HOOKS["open"]),
        "how_it_works": HOW_IT_WORKS,
        "game_question": GAME_QUESTION,
        "game_options": GAME_OPTIONS,
        "game_after": GAME_AFTER,
        "match_card": MATCH_CARDS[card_intent],
        "match_outcome": MATCH_OUTCOMES[outcome_intent],
        "cta": CTA,
    }
