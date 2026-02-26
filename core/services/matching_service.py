"""
Matching service - AI-powered matching algorithm.
Core business logic for finding compatible people.
"""

from typing import List, Tuple, Optional
from uuid import UUID
import asyncio
import logging
from core.domain.models import (
    User, Match, MatchCreate, MatchResult, MatchResultWithId, MatchType, MatchStatus
)
from core.interfaces.repositories import IMatchRepository, IEventRepository
from core.interfaces.ai import IAIService
from config.settings import settings

logger = logging.getLogger(__name__)


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
        # Cap threshold at 0.4 — higher values reject too many valid matches
        self.threshold = min(settings.default_match_threshold, 0.4)

    def _check_gender_compatibility(self, user_a: User, user_b: User) -> bool:
        """Check if gender preferences are compatible (V1.1).
        Returns True if compatible or if no gender data available.
        """
        # If no gender data, skip filter (backward compatible)
        if not user_a.gender and not user_b.gender:
            return True

        # Check if A's preference matches B's gender
        if user_a.looking_for_gender and user_b.gender:
            if "everyone" not in user_a.looking_for_gender:
                # Map gender to preference format
                gender_map = {"male": "men", "female": "women", "non-binary": "everyone"}
                b_as_pref = gender_map.get(user_b.gender, user_b.gender)
                if b_as_pref not in user_a.looking_for_gender:
                    return False

        # Check if B's preference matches A's gender
        if user_b.looking_for_gender and user_a.gender:
            if "everyone" not in user_b.looking_for_gender:
                gender_map = {"male": "men", "female": "women", "non-binary": "everyone"}
                a_as_pref = gender_map.get(user_a.gender, user_a.gender)
                if a_as_pref not in user_b.looking_for_gender:
                    return False

        return True

    def calculate_base_score(self, user_a: User, user_b: User) -> float:
        """
        Calculate quick base score for pre-filtering.
        Considers: looking_for/can_help_with match, interests, goals, city, intent overlap, gender.
        """
        # V1.1: Gender filter — incompatible genders = no match for romance/hookup
        romantic_intents = {"romance", "hookup"}
        a_intents = set(user_a.connection_intents or [])
        b_intents = set(user_b.connection_intents or [])
        if (a_intents & romantic_intents) or (b_intents & romantic_intents):
            if not self._check_gender_compatibility(user_a, user_b):
                return 0.0  # Hard filter

        score = 0.0

        # V1.1: Intent overlap bonus
        if a_intents and b_intents:
            common_intents = a_intents & b_intents
            if common_intents:
                score += min(len(common_intents) * 0.15, 0.3)
            elif not common_intents and a_intents and b_intents:
                # No intent overlap = penalty
                score -= 0.1

        # PRIMARY: looking_for <-> can_help_with match (most important!)
        looking_a = (user_a.looking_for or "").lower()
        looking_b = (user_b.looking_for or "").lower()
        help_a = (user_a.can_help_with or "").lower()
        help_b = (user_b.can_help_with or "").lower()

        # Simple keyword matching for pre-filter
        value_exchange = False
        keywords_a_looking = set(looking_a.split()) if looking_a else set()
        keywords_b_help = set(help_b.split()) if help_b else set()
        keywords_b_looking = set(looking_b.split()) if looking_b else set()
        keywords_a_help = set(help_a.split()) if help_a else set()

        # Check for common meaningful words (excluding stopwords)
        stopwords = {'a', 'an', 'the', 'and', 'or', 'for', 'to', 'with', 'in', 'on', 'at', 'i', 'am', 'is', 'are', 'can', 'help', 'looking'}
        keywords_a_looking -= stopwords
        keywords_b_help -= stopwords
        keywords_b_looking -= stopwords
        keywords_a_help -= stopwords

        if keywords_a_looking & keywords_b_help or keywords_b_looking & keywords_a_help:
            value_exchange = True
            score += 0.4  # Strong signal

        # If both have looking_for and can_help_with filled, that's good
        if (looking_a and help_a) or (looking_b and help_b):
            score += 0.1

        # SECONDARY: interests overlap
        interests_a = set(user_a.interests or [])
        interests_b = set(user_b.interests or [])
        common_interests = interests_a & interests_b
        score += min(len(common_interests) * 0.1, 0.3)

        # TERTIARY: goals overlap
        goals_a = set(user_a.goals or [])
        goals_b = set(user_b.goals or [])
        common_goals = goals_a & goals_b
        score += min(len(common_goals) * 0.1, 0.2)

        # City bonus
        if user_a.city_current and user_b.city_current and user_a.city_current == user_b.city_current:
            score += 0.1

        return max(min(score, 1.0), 0.0)

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
        min_base = self.threshold * 0.5  # relaxed pre-filter

        # Skip if base score is too low
        if base_score < min_base:
            logger.info(
                f"Pre-filter skip: {user_a.display_name} ↔ {user_b.display_name} "
                f"base_score={base_score:.2f} < {min_base:.2f}"
            )
            return None

        # Deep AI analysis
        user_a_dict = user_a.model_dump()
        user_b_dict = user_b.model_dump()

        result = await self.ai_service.analyze_match(
            user_a_dict,
            user_b_dict,
            event_context=event_context
        )

        return result

    async def find_vector_candidates(
        self,
        user: User,
        event_id: UUID,
        limit: int = 10,
        similarity_threshold: float = 0.45
    ) -> List[Tuple[User, float]]:
        """
        Find candidate matches using vector similarity search.
        Uses pgvector function match_candidates for fast similarity lookup.
        """
        from infrastructure.database.supabase_client import supabase
        from infrastructure.database.user_repository import SupabaseUserRepository

        user_repo = SupabaseUserRepository()

        try:
            # Call pgvector function via RPC
            response = supabase.rpc('match_candidates', {
                'query_user_id': str(user.id),
                'query_event_id': str(event_id),
                'similarity_threshold': similarity_threshold,
                'limit_count': limit
            }).execute()

            if not response.data:
                logger.info(f"Vector search found 0 candidates for user {user.id}")
                return []

            # Fetch full user objects for candidates
            candidates = []
            for row in response.data:
                try:
                    candidate = await user_repo.get_by_id(UUID(row['user_id']))
                    if candidate:
                        candidates.append((candidate, row.get('similarity_score', 0.5)))
                except (KeyError, ValueError) as e:
                    logger.warning(f"Invalid RPC row: {e}")
                    continue

            logger.info(f"Vector search found {len(candidates)} candidates for {user.display_name or user.id}")
            return candidates

        except Exception as e:
            logger.warning(f"Vector search failed, using base score fallback: {e}")
            return await self._fallback_base_score_candidates(user, event_id, limit)

    async def _fallback_base_score_candidates(
        self,
        user: User,
        event_id: UUID,
        limit: int = 10
    ) -> List[Tuple[User, float]]:
        """
        Fallback candidate selection using base score (interests/goals overlap).
        Used when vector search is not available.
        """
        participants = await self.event_repo.get_participants(event_id)
        others = [p for p in participants if p.id != user.id]

        if not others:
            return []

        # Calculate base scores and sort
        scored = []
        for other in others:
            score = self.calculate_base_score(user, other)
            if score >= self.threshold * 0.7:
                scored.append((other, score))

        # Sort by score and return top candidates
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    async def find_matches_vector(
        self,
        user: User,
        event_id: UUID,
        limit: int = 3
    ) -> List[Tuple[User, MatchResultWithId]]:
        """
        Two-stage matching: vector similarity search + LLM re-ranking.

        Stage 1: Fast vector similarity to get top N candidates
        Stage 2: Deep LLM analysis of top candidates

        Returns list of (User, MatchResultWithId) tuples.
        """
        event = await self.event_repo.get_by_id(event_id)
        event_name = event.name if event else "Event"

        # Stage 1: Vector similarity search (fast)
        # Check if user has embeddings
        if user.profile_embedding is not None:
            candidates = await self.find_vector_candidates(user, event_id, limit=10)
        else:
            # Fallback to base score if no embeddings
            logger.info(f"User {user.id} has no embeddings, using base score fallback")
            candidates = await self._fallback_base_score_candidates(user, event_id, limit=10)

        if not candidates:
            logger.info(f"No candidates found for {user.display_name or user.id}")
            return []

        # Filter out already-matched candidates
        new_candidates = []
        for candidate, vector_score in candidates:
            if await self.match_repo.exists(event_id, user.id, candidate.id):
                logger.info(f"Skipping {candidate.display_name or candidate.id} — already matched")
                continue
            new_candidates.append((candidate, vector_score))

        if not new_candidates:
            logger.info(f"All {len(candidates)} candidates already matched")
            return []

        logger.info(f"Running parallel LLM re-ranking for {len(new_candidates)} candidates")

        # Stage 2: PARALLEL LLM deep analysis
        async def _analyze_one(candidate, vector_score):
            result = await self.analyze_pair(user, candidate, event_name)
            if result:
                logger.info(
                    f"LLM score: {user.display_name} ↔ {candidate.display_name}: "
                    f"{result.compatibility_score:.2f} (threshold={self.threshold}, vec={vector_score:.2f})"
                )
            return candidate, vector_score, result

        results = await asyncio.gather(
            *[_analyze_one(c, vs) for c, vs in new_candidates],
            return_exceptions=True
        )

        # Process results and create match records
        matches = []
        for item in results:
            if isinstance(item, Exception):
                logger.error(f"LLM analysis failed for a candidate: {item}")
                continue
            candidate, vector_score, result = item
            if result and result.compatibility_score >= self.threshold:
                match_create = MatchCreate(
                    event_id=event_id,
                    user_a_id=user.id,
                    user_b_id=candidate.id,
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    ai_explanation=result.explanation,
                    icebreaker=result.icebreaker
                )
                created_match = await self.match_repo.create(match_create)
                result_with_id = MatchResultWithId(
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    explanation=result.explanation,
                    icebreaker=result.icebreaker,
                    match_id=created_match.id
                )
                matches.append((candidate, result_with_id))

        # Sort by LLM score and return top N
        matches.sort(key=lambda x: x[1].compatibility_score, reverse=True)
        return matches[:limit]

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
        limit: int = 3,
        user_repo=None
    ) -> List[Tuple[User, Match]]:
        """
        Get top N matches for a user, optionally filtered by event.
        Returns list of (matched_user, match) tuples sorted by score.
        """
        if user_repo is None:
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
    ) -> List[Tuple[User, "MatchResultWithId"]]:
        """
        Find matches for a specific user within an event.
        Creates match records and returns top matches with match IDs.
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
                created_match = await self.match_repo.create(match_create)

                # Create result with match_id for notifications
                result_with_id = MatchResultWithId(
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    explanation=result.explanation,
                    icebreaker=result.icebreaker,
                    match_id=created_match.id
                )
                matches.append((other, result_with_id))

        # Sort by score and return top N
        matches.sort(key=lambda x: x[1].compatibility_score, reverse=True)
        return matches[:limit]

    # === SPHERE CITY - City-based Matching ===

    async def get_city_matches(
        self,
        user_id: UUID,
        city: str
    ) -> List[Match]:
        """Get existing city matches for a user"""
        return await self.match_repo.get_city_matches(user_id, city)

    async def find_city_candidates(
        self,
        user: User,
        limit: int = 20
    ) -> List[User]:
        """Find users in the same city as potential matches"""
        from infrastructure.database.user_repository import SupabaseUserRepository

        if not user.city_current:
            return []

        user_repo = SupabaseUserRepository()

        try:
            # Get users in the same city
            candidates = await user_repo.get_users_by_city(
                city=user.city_current,
                exclude_user_id=user.id,
                limit=limit
            )
            return candidates
        except Exception as e:
            logger.warning(f"Failed to get city candidates: {e}")
            return []

    async def find_city_matches(
        self,
        user: User,
        limit: int = 5
    ) -> List[Tuple[User, MatchResultWithId]]:
        """
        Find matches for a user based on city (Sphere City feature).
        Creates match records with city set, event_id is NULL.
        """
        if not user.city_current:
            logger.warning(f"User {user.id} has no city_current set")
            return []

        # First check for existing matches
        existing = await self.match_repo.get_city_matches(user.id, user.city_current)
        if existing:
            # Return existing matches with user objects
            from infrastructure.database.user_repository import SupabaseUserRepository
            user_repo = SupabaseUserRepository()

            results = []
            for match in existing[:limit]:
                other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
                other_user = await user_repo.get_by_id(other_id)
                if other_user:
                    result_with_id = MatchResultWithId(
                        compatibility_score=match.compatibility_score,
                        match_type=match.match_type,
                        explanation=match.ai_explanation,
                        icebreaker=match.icebreaker,
                        match_id=match.id
                    )
                    results.append((other_user, result_with_id))
            return results

        # Find new candidates
        candidates = await self.find_city_candidates(user, limit=20)

        if not candidates:
            logger.info(f"No city candidates found for {user.display_name or user.id} in {user.city_current}")
            return []

        logger.info(f"Found {len(candidates)} city candidates for {user.display_name or user.id}")

        # Analyze pairs and create matches
        matches = []
        for candidate in candidates:
            # Skip if already matched (city or event)
            if await self.match_repo.exists_any(user.id, candidate.id):
                continue

            # Deep AI analysis
            result = await self.analyze_pair(user, candidate, f"Sphere City - {user.city_current}")

            if result and result.compatibility_score >= self.threshold:
                # Create city match (event_id is None)
                match_create = MatchCreate(
                    event_id=None,  # City match, no event
                    user_a_id=user.id,
                    user_b_id=candidate.id,
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    ai_explanation=result.explanation,
                    icebreaker=result.icebreaker,
                    city=user.city_current  # Store city for filtering
                )
                created_match = await self.match_repo.create(match_create)

                result_with_id = MatchResultWithId(
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    explanation=result.explanation,
                    icebreaker=result.icebreaker,
                    match_id=created_match.id
                )
                matches.append((candidate, result_with_id))

                if len(matches) >= limit:
                    break

        # Sort by score
        matches.sort(key=lambda x: x[1].compatibility_score, reverse=True)
        return matches[:limit]

    # === COMMUNITY MATCHING ===

    async def get_community_matches(
        self,
        user_id: UUID,
        community_id: UUID,
    ) -> List[Match]:
        """Get existing community-scoped matches for a user."""
        return await self.match_repo.get_community_matches(user_id, community_id)

    async def find_community_matches(
        self,
        user: User,
        community_id: UUID,
        limit: int = 5,
    ) -> List[Tuple[User, MatchResultWithId]]:
        """
        Find matches for a user within a specific community.
        Filters candidates to community members only, then runs
        vector similarity + LLM re-ranking.

        Also provides 1 free cross-community match if available.
        """
        from infrastructure.database.community_repository import SupabaseCommunityRepository
        from infrastructure.database.user_repository import SupabaseUserRepository

        community_repo = SupabaseCommunityRepository()
        user_repo = SupabaseUserRepository()

        # Check for existing community matches first
        existing = await self.match_repo.get_community_matches(user.id, community_id)
        if existing:
            results = []
            for match in existing[:limit]:
                other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
                other_user = await user_repo.get_by_id(other_id)
                if other_user:
                    result_with_id = MatchResultWithId(
                        compatibility_score=match.compatibility_score,
                        match_type=match.match_type,
                        explanation=match.ai_explanation,
                        icebreaker=match.icebreaker,
                        match_id=match.id,
                    )
                    results.append((other_user, result_with_id))
            return results

        # Get community member user IDs
        member_ids = await community_repo.get_member_user_ids(community_id)
        if not member_ids:
            logger.info(f"No community members found for community {community_id}")
            return []

        # Filter to onboarded members with profiles (exclude self)
        candidates = []
        for mid in member_ids:
            if str(mid) == str(user.id):
                continue
            candidate = await user_repo.get_by_id(UUID(mid))
            if candidate and candidate.onboarding_completed:
                candidates.append(candidate)

        if not candidates:
            logger.info(f"No onboarded candidates in community {community_id}")
            return []

        logger.info(f"Found {len(candidates)} community candidates for {user.display_name or user.id}")

        # Analyze pairs and create matches
        community = await community_repo.get_by_id(community_id)
        context = f"Community: {community.name}" if community else "Community matching"

        matches = []
        for candidate in candidates:
            if await self.match_repo.exists_any(user.id, candidate.id):
                continue

            result = await self.analyze_pair(user, candidate, context)

            if result and result.compatibility_score >= self.threshold:
                match_create = MatchCreate(
                    event_id=None,
                    user_a_id=user.id,
                    user_b_id=candidate.id,
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    ai_explanation=result.explanation,
                    icebreaker=result.icebreaker,
                    community_id=community_id,
                )
                created_match = await self.match_repo.create(match_create)

                result_with_id = MatchResultWithId(
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    explanation=result.explanation,
                    icebreaker=result.icebreaker,
                    match_id=created_match.id,
                )
                matches.append((candidate, result_with_id))

                if len(matches) >= limit:
                    break

        matches.sort(key=lambda x: x[1].compatibility_score, reverse=True)
        return matches[:limit]

    FREE_TIER_CROSS_COMMUNITY_LIMIT = 1

    async def find_cross_community_match(
        self,
        user: User,
        exclude_community_id: UUID,
    ) -> Optional[Tuple[User, MatchResultWithId]]:
        """
        Find 1 free cross-community match (from global pool excluding current community).
        Returns None if user already used their free match and is on free tier.
        """
        cross_count = await self.match_repo.count_cross_community_matches(user.id)
        user_tier = getattr(user, "tier", "free") or "free"

        if user_tier == "free" and cross_count >= self.FREE_TIER_CROSS_COMMUNITY_LIMIT:
            logger.info(f"User {user.id} hit free tier cross-community limit ({cross_count})")
            return None

        global_matches = await self.find_global_matches(user, limit=1)
        if global_matches:
            return global_matches[0]
        return None

    async def check_cross_community_paywall(self, user: User) -> dict:
        """Check if user has hit the cross-community matching paywall."""
        cross_count = await self.match_repo.count_cross_community_matches(user.id)
        user_tier = getattr(user, "tier", "free") or "free"

        if user_tier != "free":
            return {"hit_paywall": False, "used": cross_count, "limit": 999, "remaining_locked": 0}

        hit = cross_count >= self.FREE_TIER_CROSS_COMMUNITY_LIMIT
        return {
            "hit_paywall": hit,
            "used": cross_count,
            "limit": self.FREE_TIER_CROSS_COMMUNITY_LIMIT,
            "remaining_locked": 3 if hit else 0,
        }

    # === GLOBAL MATCHING ===

    async def get_global_matches(
        self,
        user_id: UUID,
    ) -> List[Match]:
        """Get existing global matches for a user"""
        return await self.match_repo.get_global_matches(user_id)

    async def find_global_candidates(
        self,
        user: User,
        limit: int = 20
    ) -> List[User]:
        """Find users with global matching scope"""
        from infrastructure.database.user_repository import SupabaseUserRepository

        user_repo = SupabaseUserRepository()

        try:
            candidates = await user_repo.get_global_candidates(
                exclude_user_id=user.id,
                limit=limit
            )
            return candidates
        except Exception as e:
            logger.warning(f"Failed to get global candidates: {e}")
            return []

    async def find_global_matches(
        self,
        user: User,
        limit: int = 5
    ) -> List[Tuple[User, MatchResultWithId]]:
        """
        Find matches for a user globally (no city filter).
        Creates match records with event_id=NULL, city=NULL.
        """
        # First check for existing global matches
        existing = await self.match_repo.get_global_matches(user.id)
        if existing:
            from infrastructure.database.user_repository import SupabaseUserRepository
            user_repo = SupabaseUserRepository()

            results = []
            for match in existing[:limit]:
                other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
                other_user = await user_repo.get_by_id(other_id)
                if other_user:
                    result_with_id = MatchResultWithId(
                        compatibility_score=match.compatibility_score,
                        match_type=match.match_type,
                        explanation=match.ai_explanation,
                        icebreaker=match.icebreaker,
                        match_id=match.id
                    )
                    results.append((other_user, result_with_id))
            return results

        # Find new global candidates
        candidates = await self.find_global_candidates(user, limit=20)

        if not candidates:
            logger.info(f"No global candidates found for {user.display_name or user.id}")
            return []

        logger.info(f"Found {len(candidates)} global candidates for {user.display_name or user.id}")

        # Build context based on meeting preferences
        def _build_global_context(user_a: User, user_b: User) -> str:
            same_city = (
                user_a.city_current and user_b.city_current
                and user_a.city_current.lower() == user_b.city_current.lower()
            )
            if same_city:
                return f"Global Online Matching — both in {user_a.city_current}, can meet IRL"
            else:
                cities = []
                if user_a.city_current:
                    cities.append(user_a.city_current)
                if user_b.city_current:
                    cities.append(user_b.city_current)
                city_info = f" ({' & '.join(cities)})" if cities else ""
                return f"Global Online Matching{city_info}"

        # Analyze pairs and create matches
        matches = []
        for candidate in candidates:
            if await self.match_repo.exists_any(user.id, candidate.id):
                continue

            context = _build_global_context(user, candidate)
            result = await self.analyze_pair(user, candidate, context)

            if result and result.compatibility_score >= self.threshold:
                match_create = MatchCreate(
                    event_id=None,
                    user_a_id=user.id,
                    user_b_id=candidate.id,
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    ai_explanation=result.explanation,
                    icebreaker=result.icebreaker,
                    city=None,  # Global match — no city filter
                )
                created_match = await self.match_repo.create(match_create)

                result_with_id = MatchResultWithId(
                    compatibility_score=result.compatibility_score,
                    match_type=result.match_type,
                    explanation=result.explanation,
                    icebreaker=result.icebreaker,
                    match_id=created_match.id
                )
                matches.append((candidate, result_with_id))

                if len(matches) >= limit:
                    break

        matches.sort(key=lambda x: x[1].compatibility_score, reverse=True)
        return matches[:limit]
