"""
Domain constants - interests, goals, and other static data.
Centralized here for easy modification and future localization.
"""

# Available interests for user selection
INTERESTS = {
    "art": {"emoji": "art", "label_ru": "Искусство", "label_en": "Art"},
    "tech": {"emoji": "computer", "label_ru": "Технологии", "label_en": "Technology"},
    "sport": {"emoji": "running", "label_ru": "Спорт", "label_en": "Sports"},
    "books": {"emoji": "books", "label_ru": "Книги", "label_en": "Books"},
    "music": {"emoji": "musical_note", "label_ru": "Музыка", "label_en": "Music"},
    "cinema": {"emoji": "clapper", "label_ru": "Кино", "label_en": "Cinema"},
    "travel": {"emoji": "airplane", "label_ru": "Путешествия", "label_en": "Travel"},
    "cooking": {"emoji": "cooking", "label_ru": "Кулинария", "label_en": "Cooking"},
    "gaming": {"emoji": "video_game", "label_ru": "Игры", "label_en": "Gaming"},
    "business": {"emoji": "chart_increasing", "label_ru": "Бизнес", "label_en": "Business"},
    "wellness": {"emoji": "person_in_lotus_position", "label_ru": "Wellness", "label_en": "Wellness"},
    "ecology": {"emoji": "seedling", "label_ru": "Экология", "label_en": "Ecology"},
    "crypto": {"emoji": "coin", "label_ru": "Крипто/Web3", "label_en": "Crypto/Web3"},
    "startups": {"emoji": "rocket", "label_ru": "Стартапы", "label_en": "Startups"},
    "psychology": {"emoji": "brain", "label_ru": "Психология", "label_en": "Psychology"},
    "design": {"emoji": "palette", "label_ru": "Дизайн", "label_en": "Design"},
}

# Available goals for user selection
GOALS = {
    "friends": {"emoji": "people_holding_hands", "label_ru": "Новые друзья", "label_en": "New Friends"},
    "networking": {"emoji": "briefcase", "label_ru": "Нетворкинг", "label_en": "Networking"},
    "dating": {"emoji": "two_hearts", "label_ru": "Отношения", "label_en": "Dating"},
    "business": {"emoji": "handshake", "label_ru": "Бизнес-партнёры", "label_en": "Business Partners"},
    "mentorship": {"emoji": "direct_hit", "label_ru": "Менторство", "label_en": "Mentorship"},
    "creative": {"emoji": "art", "label_ru": "Творческие коллабы", "label_en": "Creative Collabs"},
    "cofounders": {"emoji": "busts_in_silhouette", "label_ru": "Кофаундеры", "label_en": "Co-founders"},
    "learning": {"emoji": "graduation_cap", "label_ru": "Обучение", "label_en": "Learning"},
}

# === Community Mode ===
GAME_TYPES = ["mystery_profile", "this_or_that", "vibe_check", "hot_take", "common_ground", "bingo"]
SOURCE_TYPES = ["community", "event", "referral", "game", "organic"]
COMMUNITY_ROLES = ["admin", "member"]

# Limits
MAX_INTERESTS = 5
MAX_GOALS = 3
MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 50
MAX_BIO_LENGTH = 500

# Event code settings
EVENT_CODE_LENGTH = 8

# === Matching Constants ===
EMBEDDING_DIMENSION = 1536
VECTOR_SIMILARITY_THRESHOLD = 0.45
EMBEDDING_WEIGHTS = {
    "profile": 0.40,
    "interests": 0.35,
    "expertise": 0.25,
}
DEFAULT_MATCH_THRESHOLD = 0.4
DEFAULT_MATCH_LIMIT = 10
VECTOR_CANDIDATE_LIMIT = 10

# === Rate Limiting (requests per interval) ===
RATE_LIMIT_COMMANDS = 15         # general commands per minute
RATE_LIMIT_MATCHING = 5          # /find_matches per minute
RATE_LIMIT_VOICE = 5             # voice messages per minute
RATE_LIMIT_INTERVAL_SECONDS = 60


def get_interest_display(interest_key: str, lang: str = "ru") -> str:
    """Get display text for an interest"""
    interest = INTERESTS.get(interest_key)
    if not interest:
        return interest_key
    label_key = f"label_{lang}"
    return interest.get(label_key, interest.get("label_en", interest_key))


def get_goal_display(goal_key: str, lang: str = "ru") -> str:
    """Get display text for a goal"""
    goal = GOALS.get(goal_key)
    if not goal:
        return goal_key
    label_key = f"label_{lang}"
    return goal.get(label_key, goal.get("label_en", goal_key))
