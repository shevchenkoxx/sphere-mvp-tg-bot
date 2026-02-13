"""
Question bank utilities for daily questions and profile enrichment.
Provides question selection logic with user intent filtering,
depth rotation, and gap-based prioritization.
"""

import random
import logging
from typing import List, Optional, Dict, Any

from questions.bank import QUESTION_BANK

logger = logging.getLogger(__name__)


def load_questions(
    intents: Optional[List[str]] = None,
    category: Optional[str] = None,
    depth: Optional[str] = None,
    exclude_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Load questions filtered by criteria.

    Args:
        intents: User's connection intents (networking/friends/romance/hookup)
        category: Filter by category (networking/friends/romance/hookup/self_discovery/icebreaker)
        depth: Filter by depth (light/medium/deep)
        exclude_ids: Question IDs to exclude (already asked)

    Returns:
        List of matching question dicts, sorted by priority.
    """
    exclude_ids = exclude_ids or []
    results = []

    for q in QUESTION_BANK:
        # Skip already-asked questions
        if q["id"] in exclude_ids:
            continue

        # Filter by category
        if category and q["category"] != category:
            continue

        # Filter by depth
        if depth and q["depth"] != depth:
            continue

        # Filter by intents: question must be relevant to at least one user intent
        if intents:
            q_intents = q.get("intents", [])
            # Icebreakers and self_discovery are always relevant
            if q["category"] in ("icebreaker", "self_discovery"):
                pass  # Always include
            elif not any(i in q_intents for i in intents):
                continue

        results.append(q)

    # Sort by priority (lower = asked sooner)
    results.sort(key=lambda x: x.get("priority", 99))
    return results


def get_daily_question(
    user_intents: List[str],
    asked_question_ids: List[str],
    user_profile: Optional[Dict[str, Any]] = None,
    question_count: int = 0,
) -> Optional[Dict[str, Any]]:
    """Select the best daily question for a user.

    Selection logic:
    1. Filter by user's connection_intents (only relevant questions)
    2. Exclude already-asked questions
    3. Prioritize questions that fill profile gaps (missing fields)
    4. Mix: 70% intent-relevant, 30% icebreakers/self-discovery
    5. Rotate depth: light → medium → deep (don't scare users early)

    Args:
        user_intents: User's selected connection intents
        asked_question_ids: IDs of questions already asked to this user
        user_profile: Dict with current profile data (for gap detection)
        question_count: How many questions user has answered total (for depth rotation)

    Returns:
        Question dict or None if no questions available.
    """
    if not user_intents:
        user_intents = ["friends"]  # Fallback

    # Determine target depth based on question count
    if question_count < 5:
        preferred_depth = "light"
    elif question_count < 15:
        preferred_depth = "medium"
    else:
        preferred_depth = "deep"

    # Decide: 70% intent-relevant, 30% icebreaker/self-discovery
    use_icebreaker = random.random() < 0.3

    if use_icebreaker:
        # Pick from icebreakers or self_discovery
        candidates = []
        for cat in ("icebreaker", "self_discovery"):
            candidates.extend(
                load_questions(
                    intents=user_intents,
                    category=cat,
                    exclude_ids=asked_question_ids,
                )
            )
    else:
        # Pick from intent-relevant questions
        candidates = load_questions(
            intents=user_intents,
            exclude_ids=asked_question_ids,
        )
        # Exclude icebreakers and self_discovery from intent pool
        candidates = [
            q for q in candidates
            if q["category"] not in ("icebreaker", "self_discovery")
        ]

    if not candidates:
        # Fallback: try any remaining question
        candidates = load_questions(exclude_ids=asked_question_ids)

    if not candidates:
        return None

    # Prioritize by profile gaps if profile data available
    if user_profile:
        gap_candidates = _prioritize_by_gaps(candidates, user_profile)
        if gap_candidates:
            candidates = gap_candidates

    # Filter by preferred depth, but fallback if no matches
    depth_filtered = [q for q in candidates if q["depth"] == preferred_depth]
    if depth_filtered:
        candidates = depth_filtered

    # Pick from top 3 by priority (add some randomness)
    top = candidates[:3]
    return random.choice(top)


def _prioritize_by_gaps(
    candidates: List[Dict[str, Any]],
    profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Re-order candidates to prioritize questions that fill profile gaps."""
    # Detect missing fields
    missing_fields = set()
    field_checks = {
        "bio": profile.get("bio"),
        "looking_for": profile.get("looking_for"),
        "can_help_with": profile.get("can_help_with"),
        "interests": profile.get("interests"),
        "goals": profile.get("goals"),
        "ideal_connection": profile.get("ideal_connection"),
        "skills": profile.get("skills"),
        "personality_vibe": profile.get("personality_vibe"),
        "partner_values": profile.get("partner_values"),
    }

    for field, value in field_checks.items():
        if not value or (isinstance(value, list) and len(value) == 0):
            missing_fields.add(field)

    if not missing_fields:
        return []  # Profile complete, no gap-based prioritization

    # Score candidates by how many missing fields they can fill
    scored = []
    for q in candidates:
        extracts = set(q.get("extracts", []))
        overlap = extracts & missing_fields
        if overlap:
            scored.append((len(overlap), q))

    if not scored:
        return []

    # Sort by overlap count (descending), then by priority (ascending)
    scored.sort(key=lambda x: (-x[0], x[1].get("priority", 99)))
    return [q for _, q in scored]


def get_question_text(question: Dict[str, Any], lang: str = "en") -> str:
    """Get localized question text."""
    if lang == "ru":
        return question.get("text_ru", question.get("text_en", ""))
    return question.get("text_en", "")
