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
    "Here's what happened next:\n\n"
    "🎙  She shared a bit about herself\n"
    "      voice message or a few texts\n\n"
    "🧠  AI built a deep profile — not just\n"
    "      interests, but intentions and values\n\n"
    "💫  Found people she'd actually\n"
    "      want to meet\n\n"
    "No swiping. No algorithms.\n"
    "Just real understanding."
)

GAME_QUESTION = "Quick one ⚡\n\nFriday night. What's your vibe?"

GAME_OPTIONS = ["🎉 Out with people", "🏠 Cozy night in"]

GAME_AFTER = (
    "{feedback}! {pct}% picked the same 🎯\n\n"
    "These little choices tell Sphere\n"
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
        "Because there's no good way."
    ),
    "dating": (
        "<b>78%</b> of people are tired of dating apps 😮‍💨\n\n"
        "Swiping. Small talk. Ghosting. Repeat.\n\n"
        "What if it started differently?"
    ),
    "activities": (
        "Running buddy? Tennis partner?\n"
        "Someone to explore the city with? 🏃‍♂️\n\n"
        "Finding people who share your energy\n"
        "shouldn't be this hard."
    ),
    "networking": (
        "The best opportunities come\n"
        "from <b>people</b> — not job boards 🚀\n\n"
        "Real conversations lead to\n"
        "real opportunities."
    ),
    "open": (
        "Everyone needs their people 💛\n\n"
        "Friends. Partners. Adventure buddies.\n"
        "Mentors. Co-founders.\n\n"
        "What if finding them was effortless?"
    ),
}

# ── Per-intent: Characters ─────────────────────────────────────────────────

CHARACTERS = {
    "friends": (
        "Meet <b>Mia</b> 👋\n\n"
        "Moved to a new city 3 months ago.\n"
        "Hundreds of people in group chats —\n"
        "zero real connections.\n\n"
        "She sent Sphere a voice message\n"
        "about herself. 2 minutes. That's it."
    ),
    "dating": (
        "Meet <b>Sarah</b> 👋\n\n"
        "Deleted Tinder for the 3rd time.\n"
        "She wanted someone who actually\n"
        "gets her — not just her photos.\n\n"
        "She told Sphere what she's really\n"
        "looking for. No forms, no quizzes."
    ),
    "activities": (
        "Meet <b>Luca</b> 👋\n\n"
        "Plays tennis twice a week.\n"
        "His partner moved away last month.\n"
        "Finding someone at his level?\n"
        "Impossible in a group chat.\n\n"
        "He told Sphere about his game\n"
        "and what he's looking for."
    ),
    "networking": (
        "Meet <b>Alex</b> 👋\n\n"
        "Solo founder building a SaaS product.\n"
        "Great code, but the UI was a mess.\n"
        "Demo day in one week.\n\n"
        "He told Sphere exactly what kind\n"
        "of person could save his demo."
    ),
    "open": (
        "Meet <b>Kira</b> 👋\n\n"
        "New in town. Wanted to find\n"
        "her people — friends, gym buddies,\n"
        "maybe something more.\n\n"
        "She recorded a voice message.\n"
        "Just being herself."
    ),
}

# ── Per-intent: Mechanism reveals (how Sphere matched) ─────────────────────

MECHANISMS = {
    "friends": (
        "Here's what Sphere picked up 🧠\n\n"
        "Mia mentioned loving morning hikes\n"
        "and how she's a bit of an introvert\n"
        "who just needs her people.\n\n"
        "In another chat, <b>Nora</b> talked\n"
        "about the same trail — and how\n"
        "she'd love a hiking buddy who\n"
        "doesn't need to fill every silence.\n\n"
        "A regular app would match them on\n"
        "\"both like hiking.\"\n\n"
        "Sphere saw something deeper ✨"
    ),
    "dating": (
        "Here's what Sphere picked up 🧠\n\n"
        "Sarah mentioned that jazz place\n"
        "she's been wanting to try.\n"
        "First dates should feel spontaneous,\n"
        "not staged — she said.\n\n"
        "<b>Daniel</b> had been eyeing\n"
        "the same place for weeks. He thinks\n"
        "the best conversations happen\n"
        "when you're walking, not sitting.\n\n"
        "A dating app would say:\n"
        "\"Both like music.\"\n\n"
        "Sphere saw the real connection ✨"
    ),
    "activities": (
        "Here's what Sphere picked up 🧠\n\n"
        "Luca plays at 7am — loves\n"
        "empty courts. Competitive\n"
        "but friendly.\n\n"
        "<b>Marco</b> lives 10 minutes away.\n"
        "Same schedule, same level. Described\n"
        "his ideal partner as \"someone who\n"
        "takes it seriously but doesn't\n"
        "take themselves seriously.\"\n\n"
        "A forum would match on\n"
        "\"both play tennis.\"\n\n"
        "Sphere matched the vibe ✨"
    ),
    "networking": (
        "Here's what Sphere picked up 🧠\n\n"
        "Alex described his problem —\n"
        "powerful backend, terrible UX.\n"
        "Needs someone who thinks in\n"
        "user flows, not features.\n\n"
        "<b>Sara</b> redesigned 3 SaaS products\n"
        "this year. She's looking for a founder\n"
        "who actually cares about design —\n"
        "not just wants a \"pretty UI.\"\n\n"
        "LinkedIn would say: \"Both in tech.\"\n\n"
        "Sphere found the real fit ✨"
    ),
    "open": None,  # uses "friends"
}

# ── Per-intent: Match cards (with bold outcomes) ───────────────────────────

MATCH_CARDS = {
    "friends": (
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "🤝  <b>New match for Mia</b>\n\n"
        "<b>Nora S.</b>\n\n"
        "✦ Morning hiker who loves quiet trails\n"
        "✦ Also new in town, building her circle\n"
        "✦ Free weekends, same neighborhood\n\n"
        "💬 <i>\"Hey! There's a great trail\n"
        "30 min from here — Saturday morning?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>They went on that hike.\n"
        "Now it's their weekly tradition</b> 🚶‍♀️"
    ),
    "dating": (
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "💕  <b>New match for Sarah</b>\n\n"
        "<b>Daniel K.</b>\n\n"
        "✦ Loves spontaneous plans\n"
        "✦ Has been eyeing the same jazz spot\n"
        "✦ Thinks walks > fancy dinners\n\n"
        "💬 <i>\"There's a small jazz night\n"
        "Thursday — want to check it out?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>They went. Six months later —\n"
        "still together</b> 💛"
    ),
    "activities": (
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡  <b>New match for Luca</b>\n\n"
        "<b>Marco T.</b>\n\n"
        "✦ Lives 10 min away, same courts\n"
        "✦ Plays early morning, competitive & chill\n"
        "✦ Looking for a regular partner\n\n"
        "💬 <i>\"Courts near the park,\n"
        "Sunday 7am — you in?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>They now play every Sunday.\n"
        "Found 2 more through Sphere</b> 🎾"
    ),
    "networking": (
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "💼  <b>New match for Alex</b>\n\n"
        "<b>Sara T.</b> — Product Designer\n\n"
        "✦ Redesigned 3 SaaS products this year\n"
        "✦ Thinks in user flows, not pixels\n"
        "✦ Looking for a founder who values design\n\n"
        "💬 <i>\"Your landing page is bold.\n"
        "I have ideas — coffee this week?\"</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>She redesigned his product in 5 days.\n"
        "Two months later — co-founder</b> 🚀"
    ),
    "open": None,  # uses "friends"
}


def get_story(intent: str) -> dict:
    """Get story content for the given intent."""
    card_intent = intent if MATCH_CARDS.get(intent) else "friends"
    mechanism_intent = intent if MECHANISMS.get(intent) else "friends"

    return {
        "hook": HOOKS.get(intent, HOOKS["open"]),
        "character": CHARACTERS.get(intent, CHARACTERS["open"]),
        "how_it_works": HOW_IT_WORKS,
        "mechanism": MECHANISMS[mechanism_intent],
        "game_question": GAME_QUESTION,
        "game_options": GAME_OPTIONS,
        "game_after": GAME_AFTER,
        "match_card": MATCH_CARDS[card_intent],
        "cta": CTA,
    }
