"""
Supabase implementation of Community repository.
"""

import logging
from typing import Optional, List
from uuid import UUID

from core.domain.models import Community, CommunityMember
from infrastructure.database.supabase_client import supabase, run_sync

logger = logging.getLogger(__name__)


class SupabaseCommunityRepository:
    """Supabase implementation of community repository"""

    def _to_community(self, data: dict) -> Community:
        return Community(
            id=data["id"],
            telegram_group_id=data["telegram_group_id"],
            name=data.get("name"),
            description=data.get("description"),
            invite_link=data.get("invite_link"),
            settings=data.get("settings") or {},
            owner_user_id=data.get("owner_user_id"),
            is_active=data.get("is_active", True),
            member_count=data.get("member_count", 0),
            created_at=data.get("created_at"),
        )

    def _to_member(self, data: dict) -> CommunityMember:
        return CommunityMember(
            id=data["id"],
            community_id=data["community_id"],
            user_id=data["user_id"],
            role=data.get("role", "member"),
            joined_via=data.get("joined_via"),
            is_onboarded=data.get("is_onboarded", False),
            joined_at=data.get("joined_at"),
        )

    # --- Community CRUD ---

    @run_sync
    def _create_sync(self, telegram_group_id: int, name: Optional[str], owner_user_id: Optional[UUID]) -> dict:
        data = {
            "telegram_group_id": telegram_group_id,
            "name": name,
            "owner_user_id": str(owner_user_id) if owner_user_id else None,
        }
        response = supabase.table("communities").insert(data).execute()
        return response.data[0]

    async def create(self, telegram_group_id: int, name: Optional[str] = None, owner_user_id: Optional[UUID] = None) -> Community:
        data = await self._create_sync(telegram_group_id, name, owner_user_id)
        return self._to_community(data)

    @run_sync
    def _get_by_id_sync(self, community_id: UUID) -> Optional[dict]:
        response = supabase.table("communities").select("*").eq("id", str(community_id)).execute()
        return response.data[0] if response.data else None

    async def get_by_id(self, community_id: UUID) -> Optional[Community]:
        data = await self._get_by_id_sync(community_id)
        return self._to_community(data) if data else None

    @run_sync
    def _get_by_telegram_group_id_sync(self, group_id: int) -> Optional[dict]:
        response = supabase.table("communities").select("*").eq("telegram_group_id", group_id).execute()
        return response.data[0] if response.data else None

    async def get_by_telegram_group_id(self, group_id: int) -> Optional[Community]:
        data = await self._get_by_telegram_group_id_sync(group_id)
        return self._to_community(data) if data else None

    @run_sync
    def _update_settings_sync(self, community_id: UUID, settings: dict) -> dict:
        response = supabase.table("communities").update({"settings": settings}).eq("id", str(community_id)).execute()
        return response.data[0]

    async def update_settings(self, community_id: UUID, settings: dict) -> Community:
        data = await self._update_settings_sync(community_id, settings)
        return self._to_community(data)

    @run_sync
    def _deactivate_sync(self, community_id: UUID) -> None:
        supabase.table("communities").update({"is_active": False}).eq("id", str(community_id)).execute()

    async def deactivate(self, community_id: UUID) -> None:
        await self._deactivate_sync(community_id)

    @run_sync
    def _update_member_count_sync(self, community_id: UUID) -> None:
        # Count members and update
        response = supabase.table("community_members").select("id", count="exact").eq("community_id", str(community_id)).execute()
        count = response.count if response.count is not None else 0
        supabase.table("communities").update({"member_count": count}).eq("id", str(community_id)).execute()

    async def update_member_count(self, community_id: UUID) -> None:
        await self._update_member_count_sync(community_id)

    @run_sync
    def _get_all_active_sync(self) -> List[dict]:
        response = supabase.table("communities").select("*").eq("is_active", True).execute()
        return response.data or []

    async def get_all_active(self) -> List[Community]:
        data = await self._get_all_active_sync()
        return [self._to_community(d) for d in data]

    # --- Members ---

    @run_sync
    def _add_member_sync(self, community_id: UUID, user_id: UUID, role: str, joined_via: Optional[str]) -> dict:
        data = {
            "community_id": str(community_id),
            "user_id": str(user_id),
            "role": role,
            "joined_via": joined_via,
        }
        response = supabase.table("community_members").upsert(data).execute()
        return response.data[0]

    async def add_member(self, community_id: UUID, user_id: UUID, role: str = "member", joined_via: Optional[str] = None) -> CommunityMember:
        data = await self._add_member_sync(community_id, user_id, role, joined_via)
        return self._to_member(data)

    @run_sync
    def _get_member_sync(self, community_id: UUID, user_id: UUID) -> Optional[dict]:
        response = supabase.table("community_members").select("*")\
            .eq("community_id", str(community_id))\
            .eq("user_id", str(user_id))\
            .execute()
        return response.data[0] if response.data else None

    async def get_member(self, community_id: UUID, user_id: UUID) -> Optional[CommunityMember]:
        data = await self._get_member_sync(community_id, user_id)
        return self._to_member(data) if data else None

    @run_sync
    def _get_members_sync(self, community_id: UUID) -> List[dict]:
        response = supabase.table("community_members").select("*")\
            .eq("community_id", str(community_id))\
            .execute()
        return response.data or []

    async def get_members(self, community_id: UUID) -> List[CommunityMember]:
        data = await self._get_members_sync(community_id)
        return [self._to_member(d) for d in data]

    @run_sync
    def _get_admins_sync(self, community_id: UUID) -> List[dict]:
        response = supabase.table("community_members").select("*")\
            .eq("community_id", str(community_id))\
            .eq("role", "admin")\
            .execute()
        return response.data or []

    async def get_admins(self, community_id: UUID) -> List[CommunityMember]:
        data = await self._get_admins_sync(community_id)
        return [self._to_member(d) for d in data]

    @run_sync
    def _set_member_onboarded_sync(self, community_id: UUID, user_id: UUID) -> None:
        supabase.table("community_members").update({"is_onboarded": True})\
            .eq("community_id", str(community_id))\
            .eq("user_id", str(user_id))\
            .execute()

    async def set_member_onboarded(self, community_id: UUID, user_id: UUID) -> None:
        await self._set_member_onboarded_sync(community_id, user_id)

    @run_sync
    def _get_user_communities_sync(self, user_id: UUID) -> List[dict]:
        response = supabase.table("community_members")\
            .select("*, communities(*)")\
            .eq("user_id", str(user_id))\
            .execute()
        return [m["communities"] for m in response.data if m.get("communities")] if response.data else []

    async def get_user_communities(self, user_id: UUID) -> List[Community]:
        data = await self._get_user_communities_sync(user_id)
        return [self._to_community(d) for d in data]

    @run_sync
    def _get_member_user_ids_sync(self, community_id: UUID) -> List[str]:
        response = supabase.table("community_members").select("user_id")\
            .eq("community_id", str(community_id))\
            .execute()
        return [m["user_id"] for m in response.data] if response.data else []

    async def get_member_user_ids(self, community_id: UUID) -> List[str]:
        return await self._get_member_user_ids_sync(community_id)
