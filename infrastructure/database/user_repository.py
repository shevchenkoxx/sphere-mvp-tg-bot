"""
Supabase implementation of User repository.
"""

from typing import Optional
from uuid import UUID
from core.domain.models import User, UserCreate, UserUpdate, MessagePlatform
from core.interfaces.repositories import IUserRepository
from infrastructure.database.supabase_client import supabase, run_sync


class SupabaseUserRepository(IUserRepository):
    """Supabase implementation of user repository"""

    def _platform_field(self, platform: MessagePlatform) -> str:
        """Get the field name for platform-specific ID"""
        # For now, we use a single field. In future, might have separate tables.
        return "platform_user_id"

    def _to_model(self, data: dict) -> User:
        """Convert database row to User model"""
        return User(
            id=data["id"],
            platform=MessagePlatform(data.get("platform", "telegram")),
            platform_user_id=str(data.get("platform_user_id", data.get("telegram_id", ""))),
            username=data.get("username"),
            first_name=data.get("first_name"),
            display_name=data.get("display_name"),
            city_born=data.get("city_born"),
            city_current=data.get("city_current"),
            interests=data.get("interests") or [],
            goals=data.get("goals") or [],
            bio=data.get("bio"),
            photo_url=data.get("photo_url"),
            voice_intro_url=data.get("voice_intro_url"),
            social_links=data.get("social_links") or {},
            ai_summary=data.get("ai_summary"),
            onboarding_completed=data.get("onboarding_completed", False),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    @run_sync
    def _get_by_id_sync(self, user_id: UUID) -> Optional[dict]:
        response = supabase.table("users").select("*").eq("id", str(user_id)).execute()
        return response.data[0] if response.data else None

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        data = await self._get_by_id_sync(user_id)
        return self._to_model(data) if data else None

    @run_sync
    def _get_by_platform_id_sync(self, platform: MessagePlatform, platform_user_id: str) -> Optional[dict]:
        response = supabase.table("users").select("*")\
            .eq("platform", platform.value)\
            .eq("platform_user_id", platform_user_id)\
            .execute()
        return response.data[0] if response.data else None

    async def get_by_platform_id(self, platform: MessagePlatform, platform_user_id: str) -> Optional[User]:
        data = await self._get_by_platform_id_sync(platform, platform_user_id)
        return self._to_model(data) if data else None

    @run_sync
    def _create_sync(self, user_data: UserCreate) -> dict:
        data = {
            "platform": user_data.platform.value,
            "platform_user_id": user_data.platform_user_id,
            "username": user_data.username,
            "first_name": user_data.first_name,
            "display_name": user_data.display_name,
            "city_born": user_data.city_born,
            "city_current": user_data.city_current,
            "interests": user_data.interests,
            "goals": user_data.goals,
            "bio": user_data.bio,
        }
        response = supabase.table("users").insert(data).execute()
        return response.data[0]

    async def create(self, user_data: UserCreate) -> User:
        data = await self._create_sync(user_data)
        return self._to_model(data)

    @run_sync
    def _update_sync(self, user_id: UUID, user_data: UserUpdate) -> Optional[dict]:
        update_dict = user_data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_dict:
            return None
        response = supabase.table("users").update(update_dict).eq("id", str(user_id)).execute()
        return response.data[0] if response.data else None

    async def update(self, user_id: UUID, user_data: UserUpdate) -> Optional[User]:
        data = await self._update_sync(user_id, user_data)
        return self._to_model(data) if data else None

    @run_sync
    def _update_by_platform_id_sync(self, platform: MessagePlatform, platform_user_id: str,
                                     user_data: UserUpdate) -> Optional[dict]:
        update_dict = user_data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_dict:
            return None
        response = supabase.table("users").update(update_dict)\
            .eq("platform", platform.value)\
            .eq("platform_user_id", platform_user_id)\
            .execute()
        return response.data[0] if response.data else None

    async def update_by_platform_id(self, platform: MessagePlatform, platform_user_id: str,
                                     user_data: UserUpdate) -> Optional[User]:
        data = await self._update_by_platform_id_sync(platform, platform_user_id, user_data)
        return self._to_model(data) if data else None

    async def get_or_create(self, user_data: UserCreate) -> User:
        # Try to get existing user
        existing = await self.get_by_platform_id(user_data.platform, user_data.platform_user_id)
        if existing:
            return existing
        # Create new user
        return await self.create(user_data)
