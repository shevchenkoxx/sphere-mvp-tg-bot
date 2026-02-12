"""
Supabase implementation of Match repository.
"""

from typing import Optional, List
from uuid import UUID
from core.domain.models import Match, MatchCreate, MatchStatus, MatchType
from core.interfaces.repositories import IMatchRepository
from infrastructure.database.supabase_client import supabase, run_sync


class SupabaseMatchRepository(IMatchRepository):
    """Supabase implementation of match repository"""

    def _to_model(self, data: dict) -> Match:
        """Convert database row to Match model"""
        return Match(
            id=data["id"],
            event_id=data.get("event_id"),
            user_a_id=data["user_a_id"],
            user_b_id=data["user_b_id"],
            compatibility_score=data["compatibility_score"],
            match_type=MatchType(data["match_type"]),
            ai_explanation=data["ai_explanation"],
            icebreaker=data["icebreaker"],
            status=MatchStatus(data.get("status", "pending")),
            user_a_notified=data.get("user_a_notified", False),
            user_b_notified=data.get("user_b_notified", False),
            city=data.get("city"),
            created_at=data.get("created_at"),
        )

    @run_sync
    def _get_by_id_sync(self, match_id: UUID) -> Optional[dict]:
        response = supabase.table("matches").select("*").eq("id", str(match_id)).execute()
        return response.data[0] if response.data else None

    async def get_by_id(self, match_id: UUID) -> Optional[Match]:
        data = await self._get_by_id_sync(match_id)
        return self._to_model(data) if data else None

    @run_sync
    def _create_sync(self, match_data: MatchCreate) -> dict:
        data = {
            "event_id": str(match_data.event_id) if match_data.event_id else None,
            "user_a_id": str(match_data.user_a_id),
            "user_b_id": str(match_data.user_b_id),
            "compatibility_score": match_data.compatibility_score,
            "match_type": match_data.match_type.value,
            "ai_explanation": match_data.ai_explanation,
            "icebreaker": match_data.icebreaker,
            "city": match_data.city,  # For Sphere City matches
        }
        response = supabase.table("matches").upsert(data).execute()
        return response.data[0]

    async def create(self, match_data: MatchCreate) -> Match:
        data = await self._create_sync(match_data)
        return self._to_model(data)

    @run_sync
    def _get_user_matches_sync(self, user_id: UUID, status: Optional[MatchStatus]) -> List[dict]:
        query = supabase.table("matches").select("*")\
            .or_(f"user_a_id.eq.{user_id},user_b_id.eq.{user_id}")

        if status:
            query = query.eq("status", status.value)

        response = query.order("compatibility_score", desc=True).execute()
        return response.data if response.data else []

    async def get_user_matches(self, user_id: UUID, status: Optional[MatchStatus] = None) -> List[Match]:
        data = await self._get_user_matches_sync(user_id, status)
        return [self._to_model(d) for d in data]

    @run_sync
    def _update_status_sync(self, match_id: UUID, status: MatchStatus) -> Optional[dict]:
        response = supabase.table("matches")\
            .update({"status": status.value})\
            .eq("id", str(match_id))\
            .execute()
        return response.data[0] if response.data else None

    async def update_status(self, match_id: UUID, status: MatchStatus) -> Optional[Match]:
        data = await self._update_status_sync(match_id, status)
        return self._to_model(data) if data else None

    @run_sync
    def _mark_notified_sync(self, match_id: UUID, user_position: str) -> None:
        field = "user_a_notified" if user_position == "a" else "user_b_notified"
        supabase.table("matches").update({field: True}).eq("id", str(match_id)).execute()

    async def mark_notified(self, match_id: UUID, user_position: str) -> None:
        await self._mark_notified_sync(match_id, user_position)

    @run_sync
    def _exists_sync(self, event_id: UUID, user_a_id: UUID, user_b_id: UUID) -> bool:
        # Check both directions (A-B and B-A)
        query = supabase.table("matches").select("id")

        # Handle NULL event_id properly
        if event_id:
            query = query.eq("event_id", str(event_id))
        else:
            query = query.is_("event_id", "null")

        response = query.or_(
            f"and(user_a_id.eq.{user_a_id},user_b_id.eq.{user_b_id}),"
            f"and(user_a_id.eq.{user_b_id},user_b_id.eq.{user_a_id})"
        ).execute()
        return len(response.data) > 0 if response.data else False

    async def exists(self, event_id: UUID, user_a_id: UUID, user_b_id: UUID) -> bool:
        return await self._exists_sync(event_id, user_a_id, user_b_id)

    @run_sync
    def _get_unnotified_matches_sync(self, user_id: UUID) -> List[dict]:
        # Get matches where user is A and not notified
        response_a = supabase.table("matches").select("*")\
            .eq("user_a_id", str(user_id))\
            .eq("user_a_notified", False)\
            .execute()

        # Get matches where user is B and not notified
        response_b = supabase.table("matches").select("*")\
            .eq("user_b_id", str(user_id))\
            .eq("user_b_notified", False)\
            .execute()

        results = (response_a.data or []) + (response_b.data or [])
        return results

    async def get_unnotified_matches(self, user_id: UUID) -> List[Match]:
        data = await self._get_unnotified_matches_sync(user_id)
        return [self._to_model(d) for d in data]

    # === SPHERE CITY - City-based Matching ===

    @run_sync
    def _get_city_matches_sync(self, user_id: UUID, city: str) -> List[dict]:
        """Get city matches for a user (event_id is NULL)"""
        response = supabase.table("matches").select("*")\
            .is_("event_id", "null")\
            .eq("city", city)\
            .or_(f"user_a_id.eq.{user_id},user_b_id.eq.{user_id}")\
            .order("compatibility_score", desc=True)\
            .execute()
        return response.data if response.data else []

    async def get_city_matches(self, user_id: UUID, city: str) -> List[Match]:
        """Get city-based matches for a user"""
        data = await self._get_city_matches_sync(user_id, city)
        return [self._to_model(d) for d in data]

    @run_sync
    def _exists_any_sync(self, user_a_id: UUID, user_b_id: UUID) -> bool:
        """Check if any match exists between two users (regardless of event)"""
        response = supabase.table("matches").select("id")\
            .or_(
                f"and(user_a_id.eq.{user_a_id},user_b_id.eq.{user_b_id}),"
                f"and(user_a_id.eq.{user_b_id},user_b_id.eq.{user_a_id})"
            ).execute()
        return len(response.data) > 0 if response.data else False

    async def exists_any(self, user_a_id: UUID, user_b_id: UUID) -> bool:
        """Check if any match exists between two users"""
        return await self._exists_any_sync(user_a_id, user_b_id)
