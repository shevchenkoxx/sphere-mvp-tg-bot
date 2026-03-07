"""
Activity intent constants for UserEvents feature.
Categories and subcategories for the activity picker.
"""

from typing import Dict, List, Any


# Level 1: Main activity categories
ACTIVITY_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "coffee": {"emoji": "☕", "label_en": "Tea or coffee", "label_ru": "Чай или кофе", "has_sub": False},
    "walk": {"emoji": "🌳", "label_en": "Walk in the park", "label_ru": "Прогулка в парке", "has_sub": False},
    "sport": {"emoji": "⚽", "label_en": "Play sports", "label_ru": "Спорт", "has_sub": True},
    "dining": {"emoji": "🍽", "label_en": "Dinner or drinks", "label_ru": "Ужин или напитки", "has_sub": True},
    "event": {"emoji": "🎤", "label_en": "Go to an event", "label_ru": "Пойти на ивент", "has_sub": True},
    "chat": {"emoji": "💬", "label_en": "Just chat & connect", "label_ru": "Просто пообщаться", "has_sub": False},
}

# Level 2: Subcategories for categories with has_sub=True
ACTIVITY_SUBCATEGORIES: Dict[str, List[Dict[str, str]]] = {
    "sport": [
        {"key": "tennis", "emoji": "🎾", "label_en": "Tennis", "label_ru": "Теннис"},
        {"key": "padel", "emoji": "🏓", "label_en": "Padel", "label_ru": "Падел"},
        {"key": "billiards", "emoji": "🎱", "label_en": "Billiards", "label_ru": "Бильярд"},
        {"key": "bowling", "emoji": "🎳", "label_en": "Bowling", "label_ru": "Боулинг"},
        {"key": "running", "emoji": "🏃", "label_en": "Running", "label_ru": "Бег"},
    ],
    "dining": [
        {"key": "italian", "emoji": "🍕", "label_en": "Italian", "label_ru": "Итальянская"},
        {"key": "japanese", "emoji": "🍣", "label_en": "Japanese & Sushi", "label_ru": "Японская и суши"},
        {"key": "burgers", "emoji": "🍔", "label_en": "Burgers & Grill", "label_ru": "Бургеры и гриль"},
        {"key": "polish", "emoji": "🥘", "label_en": "Polish traditional", "label_ru": "Польская кухня"},
        {"key": "mexican_asian", "emoji": "🌮", "label_en": "Mexican & Asian", "label_ru": "Мексиканская и азиатская"},
    ],
    "event": [
        {"key": "tech", "emoji": "💻", "label_en": "Tech & Startups", "label_ru": "Tech & Startups"},
        {"key": "art", "emoji": "🎨", "label_en": "Art & Exhibitions", "label_ru": "Искусство и выставки"},
        {"key": "workshops", "emoji": "📚", "label_en": "Workshops & Education", "label_ru": "Воркшопы и обучение"},
        {"key": "music", "emoji": "🎵", "label_en": "Music & Concerts", "label_ru": "Музыка и концерты"},
        {"key": "theater", "emoji": "🎭", "label_en": "Theater & Shows", "label_ru": "Театр и шоу"},
    ],
}

# Order for display
ACTIVITY_CATEGORY_ORDER = ["coffee", "walk", "sport", "dining", "event", "chat"]

MAX_ACTIVITY_SELECTIONS = 3


def get_category_label(key: str, lang: str = "en") -> str:
    """Get display label for a category."""
    cat = ACTIVITY_CATEGORIES.get(key, {})
    label_key = f"label_{lang}" if f"label_{lang}" in cat else "label_en"
    return f"{cat.get('emoji', '')} {cat.get(label_key, key)}"


def get_subcategory_label(category: str, sub_key: str, lang: str = "en") -> str:
    """Get display label for a subcategory."""
    subs = ACTIVITY_SUBCATEGORIES.get(category, [])
    for sub in subs:
        if sub["key"] == sub_key:
            label_key = f"label_{lang}" if f"label_{lang}" in sub else "label_en"
            return f"{sub.get('emoji', '')} {sub.get(label_key, sub_key)}"
    return sub_key


def format_user_activities(categories: list, details: dict, lang: str = "en") -> str:
    """Format user's selected activities for display."""
    if not categories:
        return "No activities selected" if lang == "en" else "Нет выбранных активностей"

    lines = []
    for cat_key in categories:
        cat = ACTIVITY_CATEGORIES.get(cat_key, {})
        label_key = f"label_{lang}" if f"label_{lang}" in cat else "label_en"
        emoji = cat.get("emoji", "")
        label = cat.get(label_key, cat_key)

        cat_details = details.get(cat_key, {})
        selected_subs = cat_details.get("selected", [])
        custom = cat_details.get("custom")
        refinement = cat_details.get("refinement")

        if selected_subs:
            sub_labels = []
            for sub_key in selected_subs:
                sub_label = get_subcategory_label(cat_key, sub_key, lang)
                sub_labels.append(sub_label.split(" ", 1)[-1] if " " in sub_label else sub_label)
            lines.append(f"{emoji} {label}: {', '.join(sub_labels)}")
        elif custom:
            lines.append(f"{emoji} {label}: {custom}")
        else:
            lines.append(f"{emoji} {label}")

        if refinement:
            lines.append(f"   └ {refinement}")

    return "\n".join(lines)
