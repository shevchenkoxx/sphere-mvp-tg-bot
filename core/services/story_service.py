"""
Story Onboarding Content — 4 intent tracks × 7 screens, bilingual EN/RU.

Intents: friends, dating, networking, open
Screens: hook, character, how_it_works, mechanism, match_card, game, cta

Design principles:
- Max 5 lines per message (Telegram isn't a blog)
- Bold the key number/fact
- One emoji per visual anchor
- Each screen = one clear point
- Characters feel REAL — specific details
- Match cards look like actual notifications
- CTA creates urgency without pressure
"""

from typing import Dict, List, Any, Optional

# Screen keys in order
SCREEN_ORDER = [
    "hook",
    "character",
    "how_it_works",
    "mechanism",
    "match_card",
    "game",
    "cta",
]

# Intent metadata
INTENT_META = {
    "friends": {
        "en": {"label": "Find your people", "emoji": "👥"},
        "ru": {"label": "Найди своих", "emoji": "👥"},
    },
    "dating": {
        "en": {"label": "Meet someone", "emoji": "💕"},
        "ru": {"label": "Познакомиться", "emoji": "💕"},
    },
    "networking": {
        "en": {"label": "Career connections", "emoji": "💼"},
        "ru": {"label": "Деловые связи", "emoji": "💼"},
    },
    "open": {
        "en": {"label": "Surprise me", "emoji": "✨"},
        "ru": {"label": "Удиви меня", "emoji": "✨"},
    },
}

# ─────────────────────────────────────────────
# FRIENDS — "Find your people"
# ─────────────────────────────────────────────

FRIENDS_SCREENS = {
    "hook": {
        "en": (
            "👥 <b>82% of people at events</b> leave without meeting\n"
            "the one person who could've become a real friend.\n\n"
            "Sphere fixes that."
        ),
        "ru": (
            "👥 <b>82% людей на мероприятиях</b> уходят,\n"
            "так и не встретив того, кто мог стать настоящим другом.\n\n"
            "Sphere это меняет."
        ),
    },
    "character": {
        "en": (
            "Meet <b>Dima</b>.\n\n"
            "Moved to Berlin 6 months ago. Knows everyone\n"
            "at work — but nobody to grab a beer with on Friday.\n\n"
            "Tried Sphere at a local meetup."
        ),
        "ru": (
            "Это <b>Дима</b>.\n\n"
            "Переехал в Берлин полгода назад. На работе\n"
            "знает всех — но в пятницу пить пиво не с кем.\n\n"
            "Попробовал Sphere на локальном митапе."
        ),
    },
    "how_it_works": {
        "en": (
            "📱 <b>How Sphere works</b>\n\n"
            "• Tell about yourself in 60 seconds\n"
            "• AI finds people on your wavelength\n"
            "• You get matches with <i>why</i> you'd click"
        ),
        "ru": (
            "📱 <b>Как работает Sphere</b>\n\n"
            "• Расскажи о себе за 60 секунд\n"
            "• AI найдёт людей на твоей волне\n"
            "• Получишь матчи с объяснением <i>почему</i> вы совпали"
        ),
    },
    "mechanism": {
        "en": (
            "🔍 Sphere noticed Dima mentioned\n"
            "climbing, sci-fi books, and cooking experiments.\n\n"
            "Not the \"tech in Berlin\" stuff.\n"
            "<b>The real stuff he actually cares about.</b>"
        ),
        "ru": (
            "🔍 Sphere заметил, что Дима упомянул\n"
            "скалолазание, фантастику и кулинарные эксперименты.\n\n"
            "Не «айтишник в Берлине».\n"
            "<b>А то, что ему реально интересно.</b>"
        ),
    },
    "match_card": {
        "en": (
            "━━━━━━━━━━━━━━━━━\n"
            "🔔 <b>New match!</b>\n\n"
            "👤 <b>Mika</b> — also climbs, reads Asimov,\n"
            "and makes her own hot sauce.\n\n"
            "💬 <i>\"Ask about her fermentation project\"</i>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "<b>They've been climbing together every week since.</b>"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━\n"
            "🔔 <b>Новый матч!</b>\n\n"
            "👤 <b>Мика</b> — тоже лазает, читает Азимова\n"
            "и делает свой острый соус.\n\n"
            "💬 <i>«Спроси про её проект с ферментацией»</i>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "<b>С тех пор лазают вместе каждую неделю.</b>"
        ),
    },
    "game": {
        "en": {
            "question": "🎲 Quick one — what sounds more like you?",
            "options": [
                {"text": "Deep 1-on-1 talks", "data": "game_friends_deep"},
                {"text": "Big group energy", "data": "game_friends_group"},
            ],
        },
        "ru": {
            "question": "🎲 Быстрый вопрос — что тебе ближе?",
            "options": [
                {"text": "Глубокие разговоры 1-на-1", "data": "game_friends_deep"},
                {"text": "Энергия большой компании", "data": "game_friends_group"},
            ],
        },
    },
    "cta": {
        "en": {
            "game_friends_deep": (
                "🎯 Same here — the best connections are the deep ones.\n\n"
                "Sphere finds people you'd <b>actually</b> want to hang out with.\n"
                "60 seconds to set up. Zero awkward small talk."
            ),
            "game_friends_group": (
                "🎯 Love that energy — and the best groups\n"
                "start with the right people.\n\n"
                "Sphere finds them for you.\n"
                "60 seconds to set up. Zero awkward small talk."
            ),
        },
        "ru": {
            "game_friends_deep": (
                "🎯 И мы тоже — лучшие связи именно такие.\n\n"
                "Sphere находит людей, с которыми <b>реально</b> хочется тусить.\n"
                "60 секунд на настройку. Ноль неловких бесед."
            ),
            "game_friends_group": (
                "🎯 Кайф — а лучшие компании начинаются\n"
                "с правильных людей.\n\n"
                "Sphere их найдёт.\n"
                "60 секунд на настройку. Ноль неловких бесед."
            ),
        },
    },
}

# ─────────────────────────────────────────────
# DATING — "Meet someone"
# ─────────────────────────────────────────────

DATING_SCREENS = {
    "hook": {
        "en": (
            "💕 The person you'd vibe with\n"
            "is <b>probably in the same room right now.</b>\n\n"
            "You just haven't met yet."
        ),
        "ru": (
            "💕 Человек, с которым у тебя будет искра,\n"
            "<b>скорее всего уже в этой комнате.</b>\n\n"
            "Вы просто ещё не познакомились."
        ),
    },
    "character": {
        "en": (
            "Meet <b>Lena</b>.\n\n"
            "Tired of apps where people lead with their gym pics.\n"
            "Wanted to meet someone who gets her humor\n"
            "and actually reads books.\n\n"
            "Tried Sphere at a friend's birthday party."
        ),
        "ru": (
            "Это <b>Лена</b>.\n\n"
            "Устала от приложений, где все начинают с фото из зала.\n"
            "Хотела встретить того, кто понимает её юмор\n"
            "и правда читает книги.\n\n"
            "Попробовала Sphere на дне рождения подруги."
        ),
    },
    "how_it_works": {
        "en": (
            "📱 <b>How Sphere works</b>\n\n"
            "• Tell about yourself — voice or text\n"
            "• AI reads between the lines (not just keywords)\n"
            "• Matches based on <i>who you are</i>, not how you look"
        ),
        "ru": (
            "📱 <b>Как работает Sphere</b>\n\n"
            "• Расскажи о себе — голосом или текстом\n"
            "• AI читает между строк (не только ключевые слова)\n"
            "• Матчи по тому, <i>кто ты</i>, а не как выглядишь"
        ),
    },
    "mechanism": {
        "en": (
            "🔍 Sphere picked up that Lena values\n"
            "wit, spontaneity, and intellectual curiosity.\n\n"
            "Not \"likes travel and coffee.\"\n"
            "<b>The things that actually matter on a first date.</b>"
        ),
        "ru": (
            "🔍 Sphere уловил, что для Лены важны\n"
            "остроумие, спонтанность и любопытство.\n\n"
            "Не «люблю путешествия и кофе».\n"
            "<b>То, что реально важно на первом свидании.</b>"
        ),
    },
    "match_card": {
        "en": (
            "━━━━━━━━━━━━━━━━━\n"
            "🔔 <b>New match!</b>\n\n"
            "👤 <b>Artem</b> — quotes Vonnegut casually,\n"
            "runs a podcast about weird history.\n\n"
            "💬 <i>\"Ask him about the episode on Soviet arcade games\"</i>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "<b>First date was 4 hours long. Neither noticed.</b>"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━\n"
            "🔔 <b>Новый матч!</b>\n\n"
            "👤 <b>Артём</b> — цитирует Воннегута между делом,\n"
            "ведёт подкаст про странную историю.\n\n"
            "💬 <i>«Спроси про выпуск о советских игровых автоматах»</i>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "<b>Первое свидание длилось 4 часа. Оба не заметили.</b>"
        ),
    },
    "game": {
        "en": {
            "question": "🎲 What's more your style?",
            "options": [
                {"text": "Slow burn connection", "data": "game_dating_slow"},
                {"text": "Instant chemistry", "data": "game_dating_instant"},
            ],
        },
        "ru": {
            "question": "🎲 Что тебе ближе?",
            "options": [
                {"text": "Когда чувства растут постепенно", "data": "game_dating_slow"},
                {"text": "Мгновенная химия", "data": "game_dating_instant"},
            ],
        },
    },
    "cta": {
        "en": {
            "game_dating_slow": (
                "🎯 The best stories start slowly.\n\n"
                "Sphere finds people worth getting to know.\n"
                "Not swipes — <b>real introductions.</b>"
            ),
            "game_dating_instant": (
                "🎯 That spark is real — and it starts\n"
                "when you meet the right person.\n\n"
                "Sphere makes sure you don't miss them.\n"
                "<b>60 seconds to set up.</b>"
            ),
        },
        "ru": {
            "game_dating_slow": (
                "🎯 Лучшие истории начинаются не спеша.\n\n"
                "Sphere находит тех, кого стоит узнать.\n"
                "Не свайпы — <b>настоящие знакомства.</b>"
            ),
            "game_dating_instant": (
                "🎯 Эта искра настоящая — и она вспыхивает,\n"
                "когда встречаешь нужного человека.\n\n"
                "Sphere поможет его не пропустить.\n"
                "<b>60 секунд на настройку.</b>"
            ),
        },
    },
}

# ─────────────────────────────────────────────
# NETWORKING — "Career connections"
# ─────────────────────────────────────────────

NETWORKING_SCREENS = {
    "hook": {
        "en": (
            "💼 <b>1 right conversation</b> can change your career.\n\n"
            "But at events, you usually find it by accident.\n"
            "Sphere makes it on purpose."
        ),
        "ru": (
            "💼 <b>1 правильный разговор</b> может изменить карьеру.\n\n"
            "Но на мероприятиях нужный человек находится случайно.\n"
            "Sphere делает это целенаправленно."
        ),
    },
    "character": {
        "en": (
            "Meet <b>Sasha</b>.\n\n"
            "Product designer, 5 years in fintech.\n"
            "Went to every conference — collected business cards,\n"
            "never followed up.\n\n"
            "Tried Sphere at a product meetup."
        ),
        "ru": (
            "Это <b>Саша</b>.\n\n"
            "Продуктовый дизайнер, 5 лет в финтехе.\n"
            "Ходила на все конференции — собирала визитки,\n"
            "никогда не писала потом.\n\n"
            "Попробовала Sphere на продуктовом митапе."
        ),
    },
    "how_it_works": {
        "en": (
            "📱 <b>How Sphere works</b>\n\n"
            "• Share what you do and what you need\n"
            "• AI maps your skills and goals\n"
            "• Matches you with people who <i>complement</i> you"
        ),
        "ru": (
            "📱 <b>Как работает Sphere</b>\n\n"
            "• Расскажи, чем занимаешься и что ищешь\n"
            "• AI проанализирует твои навыки и цели\n"
            "• Подберёт людей, которые тебя <i>дополняют</i>"
        ),
    },
    "mechanism": {
        "en": (
            "🔍 Sphere understood that Sasha doesn't need\n"
            "\"more designers to talk to.\"\n\n"
            "She needs a PM who gets design,\n"
            "<b>or a founder looking for a design co-pilot.</b>"
        ),
        "ru": (
            "🔍 Sphere понял, что Саше не нужны\n"
            "«ещё дизайнеры для общения».\n\n"
            "Ей нужен PM, который понимает дизайн,\n"
            "<b>или фаундер, ищущий дизайн-партнёра.</b>"
        ),
    },
    "match_card": {
        "en": (
            "━━━━━━━━━━━━━━━━━\n"
            "🔔 <b>New match!</b>\n\n"
            "👤 <b>Viktor</b> — CTO at a fintech startup,\n"
            "desperately needs a design lead.\n\n"
            "💬 <i>\"Ask about their Series A and product roadmap\"</i>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "<b>Sasha joined his team 2 months later.</b>"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━\n"
            "🔔 <b>Новый матч!</b>\n\n"
            "👤 <b>Виктор</b> — CTO финтех-стартапа,\n"
            "отчаянно ищет дизайн-лида.\n\n"
            "💬 <i>«Спроси про их Series A и продуктовый роадмап»</i>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "<b>Саша присоединилась к его команде через 2 месяца.</b>"
        ),
    },
    "game": {
        "en": {
            "question": "🎲 At events, you usually:",
            "options": [
                {"text": "Talk to 2-3 people deeply", "data": "game_net_deep"},
                {"text": "Work the room", "data": "game_net_room"},
            ],
        },
        "ru": {
            "question": "🎲 На мероприятиях ты обычно:",
            "options": [
                {"text": "Общаюсь с 2-3 людьми глубоко", "data": "game_net_deep"},
                {"text": "Обхожу всех по кругу", "data": "game_net_room"},
            ],
        },
    },
    "cta": {
        "en": {
            "game_net_deep": (
                "🎯 Quality over quantity — we get it.\n\n"
                "Sphere picks the <b>2-3 people worth your time.</b>\n"
                "No more random business card exchanges."
            ),
            "game_net_room": (
                "🎯 Great at networking — but even better\n"
                "when you know <b>who</b> to talk to first.\n\n"
                "Sphere gives you that intel.\n"
                "60 seconds to set up."
            ),
        },
        "ru": {
            "game_net_deep": (
                "🎯 Качество важнее количества — мы понимаем.\n\n"
                "Sphere выберет <b>2-3 человека, стоящих твоего времени.</b>\n"
                "Никаких случайных визиток."
            ),
            "game_net_room": (
                "🎯 Круто нетворкаешь — но ещё круче,\n"
                "когда знаешь, <b>к кому</b> подойти первым.\n\n"
                "Sphere даст тебе эту информацию.\n"
                "60 секунд на настройку."
            ),
        },
    },
}

# ─────────────────────────────────────────────
# OPEN — "Surprise me"
# ─────────────────────────────────────────────

OPEN_SCREENS = {
    "hook": {
        "en": (
            "✨ The most interesting people in your life\n"
            "were <b>never part of the plan.</b>\n\n"
            "Sphere finds the ones you'd never search for."
        ),
        "ru": (
            "✨ Самые интересные люди в твоей жизни\n"
            "<b>никогда не были частью плана.</b>\n\n"
            "Sphere находит тех, кого ты бы сам не искал."
        ),
    },
    "character": {
        "en": (
            "Meet <b>Kai</b>.\n\n"
            "Data scientist by day. Ceramic artist by night.\n"
            "Didn't know what they were looking for —\n"
            "just \"someone interesting.\"\n\n"
            "Tried Sphere at a weekend pop-up."
        ),
        "ru": (
            "Это <b>Кай</b>.\n\n"
            "Днём — дата-саентист. Вечером — керамист.\n"
            "Не знал, кого ищет —\n"
            "просто «кого-то интересного».\n\n"
            "Попробовал Sphere на выходном поп-апе."
        ),
    },
    "how_it_works": {
        "en": (
            "📱 <b>How Sphere works</b>\n\n"
            "• Share your story — AI gets the full picture\n"
            "• It sees connections you wouldn't expect\n"
            "• You meet people who surprise you"
        ),
        "ru": (
            "📱 <b>Как работает Sphere</b>\n\n"
            "• Расскажи свою историю — AI увидит полную картину\n"
            "• Он найдёт связи, которых ты не ожидал\n"
            "• Ты встретишь людей, которые удивят"
        ),
    },
    "mechanism": {
        "en": (
            "🔍 Sphere didn't just see \"data + ceramics.\"\n\n"
            "It understood: Kai loves turning chaos into patterns.\n"
            "In code. In clay. In life.\n"
            "<b>That's a rare and matchable thing.</b>"
        ),
        "ru": (
            "🔍 Sphere увидел не просто «данные + керамика».\n\n"
            "Он понял: Кай любит превращать хаос в паттерны.\n"
            "В коде. В глине. В жизни.\n"
            "<b>Это редкость — и это можно сматчить.</b>"
        ),
    },
    "match_card": {
        "en": (
            "━━━━━━━━━━━━━━━━━\n"
            "🔔 <b>New match!</b>\n\n"
            "👤 <b>Noor</b> — architect who codes generative art.\n"
            "Same brain, different medium.\n\n"
            "💬 <i>\"You both think in structures — start there\"</i>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "<b>They started a creative studio together.</b>"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━\n"
            "🔔 <b>Новый матч!</b>\n\n"
            "👤 <b>Нур</b> — архитектор, который кодит генеративное искусство.\n"
            "Тот же мозг, другой материал.\n\n"
            "💬 <i>«Вы оба мыслите структурами — начните с этого»</i>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "<b>Вместе открыли креативную студию.</b>"
        ),
    },
    "game": {
        "en": {
            "question": "🎲 What excites you more?",
            "options": [
                {"text": "Meeting someone totally different", "data": "game_open_diff"},
                {"text": "Finding a hidden twin", "data": "game_open_twin"},
            ],
        },
        "ru": {
            "question": "🎲 Что тебя больше заводит?",
            "options": [
                {"text": "Встретить кого-то совсем другого", "data": "game_open_diff"},
                {"text": "Найти скрытого двойника", "data": "game_open_twin"},
            ],
        },
    },
    "cta": {
        "en": {
            "game_open_diff": (
                "🎯 The best surprises come from unexpected people.\n\n"
                "Sphere sees connections <b>you'd never think to search for.</b>\n"
                "Ready to be surprised?"
            ),
            "game_open_twin": (
                "🎯 Finding someone who just <i>gets it</i> —\n"
                "that's the magic.\n\n"
                "Sphere is <b>really good</b> at finding your people.\n"
                "60 seconds. Let's go."
            ),
        },
        "ru": {
            "game_open_diff": (
                "🎯 Лучшие сюрпризы — от неожиданных людей.\n\n"
                "Sphere видит связи, <b>которые ты бы сам не нашёл.</b>\n"
                "Готов удивиться?"
            ),
            "game_open_twin": (
                "🎯 Найти того, кто просто <i>понимает</i> —\n"
                "вот это магия.\n\n"
                "Sphere <b>отлично</b> находит своих.\n"
                "60 секунд. Погнали."
            ),
        },
    },
}

# ─────────────────────────────────────────────
# Registry — all intents
# ─────────────────────────────────────────────

STORY_CONTENT: Dict[str, Dict] = {
    "friends": FRIENDS_SCREENS,
    "dating": DATING_SCREENS,
    "networking": NETWORKING_SCREENS,
    "open": OPEN_SCREENS,
}


def get_screen(intent: str, screen: str, lang: str = "en") -> Any:
    """Get screen content for given intent and screen key.

    For text screens, returns a string.
    For game screens, returns a dict with question + options.
    For CTA screens, returns a dict keyed by game answer.
    """
    content = STORY_CONTENT.get(intent, {}).get(screen, {})
    if not content:
        return None
    return content.get(lang, content.get("en"))


def get_intent_label(intent: str, lang: str = "en") -> str:
    """Get display label for intent."""
    meta = INTENT_META.get(intent, {}).get(lang, {})
    return meta.get("label", intent)


def get_intent_emoji(intent: str) -> str:
    """Get emoji for intent."""
    meta = INTENT_META.get(intent, {}).get("en", {})
    return meta.get("emoji", "")


def get_all_intents() -> List[str]:
    """Get list of all intent keys in order."""
    return list(INTENT_META.keys())


def get_next_screen(current: str) -> Optional[str]:
    """Get next screen key, or None if at the end."""
    try:
        idx = SCREEN_ORDER.index(current)
        if idx + 1 < len(SCREEN_ORDER):
            return SCREEN_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def get_screen_index(screen: str) -> int:
    """Get 0-based index of screen in sequence."""
    try:
        return SCREEN_ORDER.index(screen)
    except ValueError:
        return -1
