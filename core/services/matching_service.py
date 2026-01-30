"""
Matching service - AI-powered matching algorithm.
Core business logic for finding compatible people.
"""

from typing import List, Tuple, Optional
from uuid import UUID
from core.domain.models import (
    User, Match, MatchCreate, MatchResult, MatchType, MatchStatus
)
from core.interfaces.repositories import IMatchRepository, IEventRepository
from core.interfaces.ai import IAIService
from config.settings import settings


class MatchingService:
    """Service for matching operations"""

    def __init__(
        self,
        match_repo: IMatchRepository,
        event_repo: IEventRepository,
        ai_service: IAIService
    ):
        self.match_repo = match_repo
        self.event_repo = event_repo
        self.ai_service = ai_service
        self.threshold = settings.default_match_threshold

    def calculate_base_score(self, user_a: User, user_b: User) -> float:
        """
        Calculate quick base score based on interests/goals overlap.
        This is a fast pre-filter before expensive AI analysis.
        """
        interests_a = set(user_a.interests or [])
        interests_b = set(user_b.interests or [])
        goals_a = set(user_a.goals or [])
        goals_b = set(user_b.goals or [])

        common_interests = interests_a & interests_b
        common_goals = goals_a & goals_b

        # Weights: interests = 0.15 each (max 0.5), goals = 0.2 each (max 0.5)
        interest_score = min(len(common_interests) * 0.15, 0.5)
        goal_score = min(len(common_goals) * 0.2, 0.5)

        # City bonus
        city_bonus = 0.1 if user_a.city_current == user_b.city_current else 0

        return min(interest_score + goal_score + city_bonus, 1.0)

    async def analyze_pair(
        self,
        user_a: User,
        user_b: User,
        event_context: Optional[str] = None
    ) -> Optional[MatchResult]:
        """
        Analyze compatibility between two users using AI.
        Returns MatchResult if compatible, None otherwise.
        """
        # Quick pre-filter
        base_score = self.calculate_base_score(user_a, user_b)

        # Skip if base score is too low
        if base_score < self.threshold * 0.7:
            return None

        # Deep AI analysis
        user_a_dict = user_a.model_dump()
        user_b_dict = user_b.model_dump()

        result = await self.ai_service.analyze_match(
            user_a_dict,
            user_b_dict,
            event_context=event_context
        )

        # Check if above threshold
        if result.compatibility_score >= self.threshold:
            return result

        return None

    async def find_matches_for_event(
        self,
        event_id: UUID
    ) -> List[Tuple[User, User, MatchResult]]:
        """
        Find all potential matches for an event.
        Returns list of (user_a, user_b, match_result) tuples.
        """
        participants = await self.event_repo.get_participants(event_id)

        if len(participants) < 2:
            return []

        # Get event for context
        event = await self.event_repo.get_by_id(event_id)
        event_context = event.name if event else None

        matches = []

        # Compare each pair
        for i, user_a in enumerate(participants):
            for user_b in participants[i + 1:]:
                # Check if match already exists
                if await self.match_repo.exists(event_id, user_a.id, user_b.id):
                    continue

                # Analyze pair
                result = await self.analyze_pair(user_a, user_b, event_context)

                if result:
                    matches.append((user_a, user_b, result))

        return matches

    async def create_matches_for_event(self, event_id: UUID) -> int:
        """
        Create all matches for an event.
        Returns count of created matches.
        """
        matches_data = await self.find_matches_for_event(event_id)
        created_count = 0

        for user_a, user_b, result in matches_data:
            match_create = MatchCreate(
                event_id=event_id,
                user_a_id=user_a.id,
                user_b_id=user_b.id,
                compatibility_score=result.compatibility_score,
                match_type=result.match_type,
                ai_explanation=result.explanation,
                icebreaker=result.icebreaker
            )

            await self.match_repo.create(match_create)
            created_count += 1

        return created_count

    async def get_user_matches(
        self,
        user_id: UUID,
        status: Optional[MatchStatus] = None
    ) -> List[Match]:
        """Get all matches for a user"""
        return await self.match_repo.get_user_matches(user_id, status)

    async def get_match(self, match_id: UUID) -> Optional[Match]:
        """Get match by ID"""
        return await self.match_repo.get_by_id(match_id)

    async def accept_match(self, match_id: UUID) -> Optional[Match]:
        """Accept a match"""
        return await self.match_repo.update_status(match_id, MatchStatus.ACCEPTED)

    async def decline_match(self, match_id: UUID) -> Optional[Match]:
        """Decline a match"""
        return await self.match_repo.update_status(match_id, MatchStatus.DECLINED)

    async def get_unnotified_matches(self, user_id: UUID) -> List[Match]:
        """Get matches where user hasn't been notified"""
        return await self.match_repo.get_unnotified_matches(user_id)

    async def mark_match_notified(self, match_id: UUID, user_position: str) -> None:
        """Mark that user was notified about match"""
        await self.match_repo.mark_notified(match_id, user_position)

    async def get_top_matches_for_user(
        self,
        user_id: UUID,
        event_id: Optional[UUID] = None,
        limit: int = 3
    ) -> List[Tuple[User, Match]]:
        """
        Get top N matches for a user, optionally filtered by event.
        Returns list of (matched_user, match) tuples sorted by score.
        """
        from infrastructure.database.user_repository import SupabaseUserRepository
        user_repo = SupabaseUserRepository()

        # Get all matches for user
        matches = await self.match_repo.get_user_matches(user_id)

        # Filter by event if specified
        if event_id:
            matches = [m for m in matches if m.event_id == event_id]

        # Sort by compatibility score (highest first)
        matches.sort(key=lambda m: m.compatibility_score, reverse=True)

        # Get top N with user details
        results = []
        for match in matches[:limit]:
            # Determine which user is the "other" one
            other_user_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
            other_user = await user_repo.get_by_id(other_user_id)
            if other_user:
                results.append((other_user, match))

        return results

    async def find_and_create_matches_for_user(
        self,
        user: User,
        event_id: UUID,
        limit: int = 3
    ) -> List[Tuple[User, MatchResult]]:
        """
        Find matches for a specific user within an event.
        Creates match records and returns top matches.
        """
        participants = await self.event_repo.get_participants(event_id)
        event = await self.event_repo.get_by_id(event_id)
        event_context = event.name if event else None

        # Filter out self
        others = [p for p in participants if p.id != user.id]

        if not others:
            return []

        matches = []
        for other in others:
            # Skip if match already exists
            if await self.match_repo.exists(event_id, user.id, other.id):
                continue

            # Analyze pair
            result = await self.analyze_pair(user, other, event_context)
            if result:
                # Create match record
                match_create = MatchCreate(
                    event_id=event_id,
                    user_a_id=user.id,
                    user_b_id=other.id,
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    ai_explanation=result.explanation,
                    icebreaker=result.icebreaker
                )
                await self.match_repo.create(match_create)
                matches.append((other, result))

        # Sort by score and return top N
        matches.sort(key=lambda x: x[1].compatibility_score, reverse=True)
        return matches[:limit]
