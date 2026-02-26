"""
Supabase implementation of Game repository.
Manages game sessions and responses for community games.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from core.domain.models import GameSession, GameResponse
from infrastructure.database.supabase_client import supabase, run_sync

logger = logging.getLogger(__name__)


class SupabaseGameRepository:
    """Supabase implementation of game repository"""

    def _to_session(self, data: dict) -> GameSession:
        return GameSession(
            id=data["id"],
            community_id=data["community_id"],
            game_type=data["game_type"],
            status=data.get("status", "active"),
            game_data=data.get("game_data") or {},
            telegram_message_id=data.get("telegram_message_id"),
            created_at=data.get("created_at"),
            ends_at=data.get("ends_at"),
        )

    def _to_response(self, data: dict) -> GameResponse:
        return GameResponse(
            id=data["id"],
            game_session_id=data["game_session_id"],
            user_id=data["user_id"],
            response=data.get("response") or {},
            is_correct=data.get("is_correct"),
            created_at=data.get("created_at"),
        )

    # --- Game Sessions ---

    @run_sync
    def _create_session_sync(self, community_id: UUID, game_type: str, game_data: dict,
                              telegram_message_id: Optional[int], ends_at: Optional[str]) -> dict:
        data = {
            "community_id": str(community_id),
            "game_type": game_type,
            "game_data": game_data,
            "status": "active",
        }
        if telegram_message_id:
            data["telegram_message_id"] = telegram_message_id
        if ends_at:
            data["ends_at"] = ends_at
        response = supabase.table("game_sessions").insert(data).execute()
        return response.data[0]

    async def create_session(self, community_id: UUID, game_type: str, game_data: dict = None,
                              telegram_message_id: Optional[int] = None,
                              ends_at: Optional[str] = None) -> GameSession:
        data = await self._create_session_sync(community_id, game_type, game_data or {}, telegram_message_id, ends_at)
        return self._to_session(data)

    @run_sync
    def _get_session_sync(self, session_id: UUID) -> Optional[dict]:
        response = supabase.table("game_sessions").select("*").eq("id", str(session_id)).execute()
        return response.data[0] if response.data else None

    async def get_session(self, session_id: UUID) -> Optional[GameSession]:
        data = await self._get_session_sync(session_id)
        return self._to_session(data) if data else None

    @run_sync
    def _get_active_sessions_sync(self, community_id: UUID) -> List[dict]:
        response = supabase.table("game_sessions").select("*")\
            .eq("community_id", str(community_id))\
            .eq("status", "active")\
            .order("created_at", desc=True)\
            .execute()
        return response.data or []

    async def get_active_sessions(self, community_id: UUID) -> List[GameSession]:
        data = await self._get_active_sessions_sync(community_id)
        return [self._to_session(d) for d in data]

    @run_sync
    def _update_session_sync(self, session_id: UUID, updates: dict) -> Optional[dict]:
        response = supabase.table("game_sessions").update(updates).eq("id", str(session_id)).execute()
        return response.data[0] if response.data else None

    async def update_session(self, session_id: UUID, **kwargs) -> Optional[GameSession]:
        data = await self._update_session_sync(session_id, kwargs)
        return self._to_session(data) if data else None

    @run_sync
    def _end_session_sync(self, session_id: UUID) -> Optional[dict]:
        response = supabase.table("game_sessions").update({"status": "ended"}).eq("id", str(session_id)).execute()
        return response.data[0] if response.data else None

    async def end_session(self, session_id: UUID) -> Optional[GameSession]:
        data = await self._end_session_sync(session_id)
        return self._to_session(data) if data else None

    @run_sync
    def _get_recent_sessions_sync(self, community_id: UUID, game_type: str, limit: int) -> List[dict]:
        response = supabase.table("game_sessions").select("*")\
            .eq("community_id", str(community_id))\
            .eq("game_type", game_type)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        return response.data or []

    async def get_recent_sessions(self, community_id: UUID, game_type: str, limit: int = 5) -> List[GameSession]:
        data = await self._get_recent_sessions_sync(community_id, game_type, limit)
        return [self._to_session(d) for d in data]

    @run_sync
    def _get_expired_active_sessions_sync(self, community_id: str) -> List[dict]:
        now_iso = datetime.now(timezone.utc).isoformat()
        response = supabase.table("game_sessions").select("*")\
            .eq("community_id", community_id)\
            .eq("status", "active")\
            .lt("ends_at", now_iso)\
            .execute()
        return response.data or []

    async def get_expired_active_sessions(self, community_id: str) -> List[dict]:
        """Return all active sessions whose ends_at is in the past."""
        return await self._get_expired_active_sessions_sync(community_id)

    # --- Game Responses ---

    @run_sync
    def _submit_response_sync(self, game_session_id: UUID, user_id: UUID, response: dict,
                               is_correct: Optional[bool]) -> dict:
        data = {
            "game_session_id": str(game_session_id),
            "user_id": str(user_id),
            "response": response,
        }
        if is_correct is not None:
            data["is_correct"] = is_correct
        result = supabase.table("game_responses").upsert(data, on_conflict="game_session_id,user_id").execute()
        return result.data[0]

    async def submit_response(self, game_session_id: UUID, user_id: UUID, response: dict,
                               is_correct: Optional[bool] = None) -> GameResponse:
        data = await self._submit_response_sync(game_session_id, user_id, response, is_correct)
        return self._to_response(data)

    @run_sync
    def _get_responses_sync(self, game_session_id: UUID) -> List[dict]:
        response = supabase.table("game_responses").select("*")\
            .eq("game_session_id", str(game_session_id))\
            .execute()
        return response.data or []

    async def get_responses(self, game_session_id: UUID) -> List[GameResponse]:
        data = await self._get_responses_sync(game_session_id)
        return [self._to_response(d) for d in data]

    @run_sync
    def _get_response_count_sync(self, game_session_id: UUID) -> int:
        response = supabase.table("game_responses").select("id", count="exact")\
            .eq("game_session_id", str(game_session_id))\
            .execute()
        return response.count if response.count is not None else 0

    async def get_response_count(self, game_session_id: UUID) -> int:
        return await self._get_response_count_sync(game_session_id)

    @run_sync
    def _get_user_response_sync(self, game_session_id: UUID, user_id: UUID) -> Optional[dict]:
        response = supabase.table("game_responses").select("*")\
            .eq("game_session_id", str(game_session_id))\
            .eq("user_id", str(user_id))\
            .execute()
        return response.data[0] if response.data else None

    async def get_user_response(self, game_session_id: UUID, user_id: UUID) -> Optional[GameResponse]:
        data = await self._get_user_response_sync(game_session_id, user_id)
        return self._to_response(data) if data else None
