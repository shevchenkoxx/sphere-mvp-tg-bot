"""
Supabase implementation of UserSource repository.
Tracks user attribution — how users discovered the bot.
"""

import logging
from typing import Optional, List
from uuid import UUID

from core.domain.models import UserSource
from infrastructure.database.supabase_client import supabase, run_sync

logger = logging.getLogger(__name__)


class SupabaseUserSourceRepository:
    """Append-only user attribution tracking"""

    def _to_model(self, data: dict) -> UserSource:
        return UserSource(
            id=data["id"],
            user_id=data["user_id"],
            source_type=data["source_type"],
            source_id=data.get("source_id"),
            referrer_tg_id=data.get("referrer_tg_id"),
            deep_link_raw=data.get("deep_link_raw"),
            created_at=data.get("created_at"),
        )

    @run_sync
    def _create_sync(self, user_id: UUID, source_type: str, source_id: Optional[str],
                     referrer_tg_id: Optional[str], deep_link_raw: Optional[str]) -> dict:
        data = {
            "user_id": str(user_id),
            "source_type": source_type,
            "source_id": source_id,
            "referrer_tg_id": referrer_tg_id,
            "deep_link_raw": deep_link_raw,
        }
        response = supabase.table("user_sources").insert(data).execute()
        return response.data[0]

    async def create(self, user_id: UUID, source_type: str, source_id: Optional[str] = None,
                     referrer_tg_id: Optional[str] = None, deep_link_raw: Optional[str] = None) -> UserSource:
        data = await self._create_sync(user_id, source_type, source_id, referrer_tg_id, deep_link_raw)
        return self._to_model(data)

    @run_sync
    def _get_user_sources_sync(self, user_id: UUID) -> List[dict]:
        response = supabase.table("user_sources").select("*")\
            .eq("user_id", str(user_id))\
            .order("created_at", desc=True)\
            .execute()
        return response.data or []

    async def get_user_sources(self, user_id: UUID) -> List[UserSource]:
        data = await self._get_user_sources_sync(user_id)
        return [self._to_model(d) for d in data]

    @run_sync
    def _get_by_source_sync(self, source_type: str, source_id: str) -> List[dict]:
        response = supabase.table("user_sources").select("*")\
            .eq("source_type", source_type)\
            .eq("source_id", source_id)\
            .execute()
        return response.data or []

    async def get_by_source(self, source_type: str, source_id: str) -> List[UserSource]:
        data = await self._get_by_source_sync(source_type, source_id)
        return [self._to_model(d) for d in data]

    @run_sync
    def _count_by_source_sync(self, source_type: str, source_id: str) -> int:
        response = supabase.table("user_sources").select("id", count="exact")\
            .eq("source_type", source_type)\
            .eq("source_id", source_id)\
            .execute()
        return response.count if response.count is not None else 0

    async def count_by_source(self, source_type: str, source_id: str) -> int:
        return await self._count_by_source_sync(source_type, source_id)
