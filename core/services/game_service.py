"""
Game engine — manages community games: Mystery Profile, This or That,
Vibe Check, Hot Take Roulette, Common Ground.

Each game type follows the same lifecycle:
  create → post to group → collect responses → end → reveal results

The scheduler triggers games periodically; the handler processes user interactions.
"""

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from openai import AsyncOpenAI
from config.settings import settings

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------
# Question banks
# -----------------------------------------------------------------

THIS_OR_THAT_QUESTIONS = [
    {"q": "Work from home or work from office?", "a": "Home", "b": "Office"},
    {"q": "Early bird or night owl?", "a": "Early bird", "b": "Night owl"},
    {"q": "Cats or dogs?", "a": "Cats", "b": "Dogs"},
    {"q": "Coffee or tea?", "a": "Coffee", "b": "Tea"},
    {"q": "Books or podcasts?", "a": "Books", "b": "Podcasts"},
    {"q": "City or nature?", "a": "City", "b": "Nature"},
    {"q": "Plan everything or go with the flow?", "a": "Plan", "b": "Flow"},
    {"q": "Call or text?", "a": "Call", "b": "Text"},
    {"q": "Startup or big company?", "a": "Startup", "b": "Big company"},
    {"q": "Deep talk or small talk?", "a": "Deep talk", "b": "Small talk"},
    {"q": "Solo travel or group travel?", "a": "Solo", "b": "Group"},
    {"q": "Mac or Windows?", "a": "Mac", "b": "Windows"},
    {"q": "Build from scratch or use a framework?", "a": "Scratch", "b": "Framework"},
    {"q": "Move fast and break things or move slow and get it right?", "a": "Move fast", "b": "Get it right"},
    {"q": "Mentor others or be mentored?", "a": "Mentor", "b": "Be mentored"},
    {"q": "Twitter (X) or LinkedIn?", "a": "X", "b": "LinkedIn"},
    {"q": "Online events or in-person events?", "a": "Online", "b": "In-person"},
    {"q": "AI will help humanity or AI is dangerous?", "a": "Will help", "b": "Dangerous"},
    {"q": "Crypto believer or crypto skeptic?", "a": "Believer", "b": "Skeptic"},
    {"q": "Introvert or extrovert?", "a": "Introvert", "b": "Extrovert"},
]

VIBE_CHECK_QUESTIONS = [
    {"q": "What's your ideal weekend?", "options": ["Beach & chill", "Side project", "Party", "Hiking", "Sleep"]},
    {"q": "Your superpower would be?", "options": ["Read minds", "Time travel", "Fly", "Teleport", "Invisibility"]},
    {"q": "What describes you best at a party?", "options": ["DJ", "Deep convo corner", "Dancing", "Left early", "Organizing"]},
    {"q": "Your work motto?", "options": ["Ship it", "Perfect it", "Delegate it", "Automate it", "Pivot"]},
    {"q": "If you weren't doing your current job?", "options": ["Chef", "Artist", "Astronaut", "Writer", "Farmer"]},
    {"q": "How do you recharge?", "options": ["Alone time", "Friends", "Exercise", "Gaming", "Cooking"]},
    {"q": "Your approach to a new city?", "options": ["Plan everything", "Ask locals", "Wander randomly", "Food tour", "Stay in hotel"]},
    {"q": "Most important in a cofounder?", "options": ["Vision", "Execution", "Network", "Humor", "Resilience"]},
    {"q": "Pick your era:", "options": ["90s internet", "2010s social", "AI revolution", "Space age", "Renaissance"]},
    {"q": "What matters most in work?", "options": ["Impact", "Money", "Freedom", "Team", "Learning"]},
]

HOT_TAKE_STATEMENTS = [
    "Remote work is better than office work — period.",
    "University degrees are becoming irrelevant.",
    "AI will replace most knowledge workers within 10 years.",
    "Networking events are mostly a waste of time.",
    "You should never work for free, even for experience.",
    "Side projects are more valuable than a second degree.",
    "Imposter syndrome is actually a sign you're growing.",
    "The best ideas come from solo thinking, not brainstorming.",
    "Hustle culture is toxic.",
    "LinkedIn is the cringiest social network.",
    "Everyone should learn to code.",
    "Work-life balance is a myth — it's about work-life integration.",
    "Crypto will fundamentally change finance.",
    "Most startups fail because of bad founders, not bad ideas.",
    "Cold outreach actually works if you do it right.",
]


class GameService:
    """Manages community game lifecycle: create, respond, end, reveal."""

    def __init__(self, game_repo, community_repo, user_repo):
        self.game_repo = game_repo
        self.community_repo = community_repo
        self.user_repo = user_repo
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)

    # -----------------------------------------------------------------
    # Generic lifecycle
    # -----------------------------------------------------------------

    async def create_game(self, community_id: UUID, game_type: str,
                          game_data: dict = None, duration_minutes: int = 60) -> "GameSession":
        """Create a new game session for a community."""
        ends_at = (datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)).isoformat()
        session = await self.game_repo.create_session(
            community_id=community_id,
            game_type=game_type,
            game_data=game_data or {},
            ends_at=ends_at,
        )
        logger.info(f"[GAME] Created {game_type} session {session.id} for community {community_id}")
        return session

    async def submit_response(self, session_id: UUID, user_id: UUID,
                               response: dict, is_correct: Optional[bool] = None) -> "GameResponse":
        """Submit a user's response to a game."""
        return await self.game_repo.submit_response(session_id, user_id, response, is_correct)

    async def end_game(self, session_id: UUID) -> "GameSession":
        """End a game session and return final state."""
        return await self.game_repo.end_session(session_id)

    async def get_active_games(self, community_id: UUID) -> list:
        """Get all active games for a community."""
        return await self.game_repo.get_active_sessions(community_id)

    async def get_results(self, session_id: UUID) -> Dict[str, Any]:
        """Get aggregated results for a game session."""
        session = await self.game_repo.get_session(session_id)
        responses = await self.game_repo.get_responses(session_id)
        if not session:
            return {"error": "Session not found"}
        return {
            "session": session,
            "responses": responses,
            "count": len(responses),
        }

    # -----------------------------------------------------------------
    # Mystery Profile
    # -----------------------------------------------------------------

    async def create_mystery_profile(self, community_id: UUID) -> Optional[Dict[str, Any]]:
        """Create a Mystery Profile game — pick a member, generate clues."""
        # Get onboarded members with rich profiles
        members = await self.community_repo.get_members(community_id)
        if len(members) < 3:
            return None

        # Get full user profiles for onboarded members
        candidates = []
        for member in members:
            if not member.is_onboarded:
                continue
            user = await self.user_repo.get_by_id(member.user_id)
            if user and user.bio and len(user.bio) > 20:
                candidates.append(user)

        if len(candidates) < 3:
            return None

        # Pick the mystery person
        mystery_person = random.choice(candidates)

        # Pick 3 decoy names (other members)
        decoys = [c for c in candidates if c.id != mystery_person.id]
        random.shuffle(decoys)
        decoy_names = [d.display_name or d.first_name or "Someone" for d in decoys[:3]]

        # Generate clues via LLM
        clues = await self._generate_mystery_clues(mystery_person)

        # Build answer options (shuffled)
        correct_name = mystery_person.display_name or mystery_person.first_name or "Mystery Person"
        options = decoy_names + [correct_name]
        random.shuffle(options)
        correct_index = options.index(correct_name)

        game_data = {
            "mystery_user_id": str(mystery_person.id),
            "mystery_name": correct_name,
            "clues": clues,
            "options": options,
            "correct_index": correct_index,
        }

        session = await self.create_game(community_id, "mystery_profile", game_data, duration_minutes=120)
        return {"session": session, "game_data": game_data}

    async def _generate_mystery_clues(self, user) -> List[str]:
        """Generate 3 fun, ambiguous clues about a user via LLM."""
        profile_text = f"""
Name: {user.display_name or user.first_name}
Bio: {user.bio or 'N/A'}
Interests: {', '.join(user.interests or [])}
Goals: {', '.join(user.goals or [])}
Looking for: {user.looking_for or 'N/A'}
Can help with: {user.can_help_with or 'N/A'}
Profession: {getattr(user, 'profession', None) or 'N/A'}
Skills: {', '.join(getattr(user, 'skills', None) or [])}
""".strip()

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "You generate fun, mysterious clues about a person for a guessing game. "
                        "Each clue should be intriguing but not give away the answer immediately. "
                        "Be creative and playful. Output exactly 3 clues, one per line, no numbering."
                    )},
                    {"role": "user", "content": f"Generate 3 mystery clues for this person:\n\n{profile_text}"},
                ],
                max_tokens=200,
                temperature=0.9,
            )
            text = response.choices[0].message.content or ""
            clues = [line.strip() for line in text.strip().split("\n") if line.strip()]
            return clues[:3] if len(clues) >= 3 else clues + ["This person is full of surprises..."]
        except Exception as e:
            logger.error(f"[GAME] Failed to generate mystery clues: {e}")
            return [
                "This person has a unique perspective on life...",
                "They're known for connecting ideas others miss...",
                "Ask them about their passion — you won't be disappointed.",
            ]

    # -----------------------------------------------------------------
    # This or That
    # -----------------------------------------------------------------

    async def create_this_or_that(self, community_id: UUID,
                                   question: Optional[dict] = None) -> Dict[str, Any]:
        """Create a This or That game — binary choice."""
        if not question:
            question = random.choice(THIS_OR_THAT_QUESTIONS)

        game_data = {
            "question": question["q"],
            "option_a": question["a"],
            "option_b": question["b"],
            "votes_a": [],  # list of user_ids
            "votes_b": [],
        }

        session = await self.create_game(community_id, "this_or_that", game_data, duration_minutes=60)
        return {"session": session, "game_data": game_data}

    # -----------------------------------------------------------------
    # Vibe Check
    # -----------------------------------------------------------------

    async def create_vibe_check(self, community_id: UUID,
                                 question: Optional[dict] = None) -> Dict[str, Any]:
        """Create a Vibe Check game — multiple choice."""
        if not question:
            question = random.choice(VIBE_CHECK_QUESTIONS)

        game_data = {
            "question": question["q"],
            "options": question["options"],
            "votes": {opt: [] for opt in question["options"]},  # option -> [user_ids]
        }

        session = await self.create_game(community_id, "vibe_check", game_data, duration_minutes=60)
        return {"session": session, "game_data": game_data}

    # -----------------------------------------------------------------
    # Hot Take Roulette
    # -----------------------------------------------------------------

    async def create_hot_take(self, community_id: UUID,
                               statement: Optional[str] = None) -> Dict[str, Any]:
        """Create a Hot Take game — agree/disagree on a spicy statement."""
        if not statement:
            statement = random.choice(HOT_TAKE_STATEMENTS)

        game_data = {
            "statement": statement,
            "agree": [],    # list of user_ids
            "disagree": [],
        }

        session = await self.create_game(community_id, "hot_take", game_data, duration_minutes=60)
        return {"session": session, "game_data": game_data}

    # -----------------------------------------------------------------
    # Common Ground Detection
    # -----------------------------------------------------------------

    async def detect_common_ground(self, community_id: UUID) -> Optional[Dict[str, Any]]:
        """Scan community for surprising overlaps between members."""
        members = await self.community_repo.get_members(community_id)
        onboarded = [m for m in members if m.is_onboarded]

        if len(onboarded) < 2:
            return None

        # Get profiles
        profiles = []
        for member in onboarded:
            user = await self.user_repo.get_by_id(member.user_id)
            if user:
                profiles.append(user)

        if len(profiles) < 2:
            return None

        # Find pairs with overlapping interests/skills
        best_pair = None
        best_overlap = []

        for i, u1 in enumerate(profiles):
            for u2 in profiles[i + 1:]:
                overlap = self._find_overlap(u1, u2)
                if len(overlap) > len(best_overlap):
                    best_overlap = overlap
                    best_pair = (u1, u2)

        if not best_pair or not best_overlap:
            return None

        u1, u2 = best_pair
        game_data = {
            "user_a_id": str(u1.id),
            "user_b_id": str(u2.id),
            "user_a_name": u1.display_name or u1.first_name or "Someone",
            "user_b_name": u2.display_name or u2.first_name or "Someone",
            "overlaps": best_overlap,
        }

        session = await self.create_game(community_id, "common_ground", game_data, duration_minutes=0)
        return {"session": session, "game_data": game_data}

    def _find_overlap(self, u1, u2) -> List[str]:
        """Find shared interests, skills, or goals between two users."""
        overlaps = []

        # Shared interests
        i1 = set(u1.interests or [])
        i2 = set(u2.interests or [])
        for shared in i1 & i2:
            overlaps.append(f"Both interested in {shared}")

        # Shared goals
        g1 = set(u1.goals or [])
        g2 = set(u2.goals or [])
        for shared in g1 & g2:
            overlaps.append(f"Both looking for {shared}")

        # Shared skills
        s1 = set(getattr(u1, 'skills', None) or [])
        s2 = set(getattr(u2, 'skills', None) or [])
        for shared in s1 & s2:
            overlaps.append(f"Both skilled in {shared}")

        return overlaps

    # -----------------------------------------------------------------
    # Scheduler integration — pick a random game for a community
    # -----------------------------------------------------------------

    async def schedule_next_game(self, community_id: UUID, bot, group_chat_id: int) -> Optional[str]:
        """Pick and launch a random game for a community. Returns game type or None."""
        from adapters.telegram.handlers.community_games import post_game_to_group

        # Check no active game already running
        active = await self.get_active_games(community_id)
        if active:
            logger.debug(f"[GAME] Community {community_id} already has active game, skipping")
            return None

        # Pick a random game type (weighted — simpler games more often)
        weights = {
            "this_or_that": 3,
            "vibe_check": 3,
            "hot_take": 2,
            "mystery_profile": 1,
            "common_ground": 1,
        }
        game_types = list(weights.keys())
        game_weights = [weights[t] for t in game_types]
        game_type = random.choices(game_types, weights=game_weights, k=1)[0]

        # Create the game
        result = None
        if game_type == "mystery_profile":
            result = await self.create_mystery_profile(community_id)
        elif game_type == "this_or_that":
            result = await self.create_this_or_that(community_id)
        elif game_type == "vibe_check":
            result = await self.create_vibe_check(community_id)
        elif game_type == "hot_take":
            result = await self.create_hot_take(community_id)
        elif game_type == "common_ground":
            result = await self.detect_common_ground(community_id)

        if not result:
            logger.debug(f"[GAME] Failed to create {game_type} for community {community_id}")
            return None

        # Post to group
        session = result["session"]
        game_data = result["game_data"]

        try:
            message_id = await post_game_to_group(bot, group_chat_id, session, game_data)
            if message_id:
                await self.game_repo.update_session(session.id, telegram_message_id=message_id)
            return game_type
        except Exception as e:
            logger.error(f"[GAME] Failed to post {game_type} to group {group_chat_id}: {e}")
            return None
