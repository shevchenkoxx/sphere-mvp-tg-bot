"""
Supabase implementation of User repository.
"""

import json
from typing import Optional, List
from uuid import UUID
from core.domain.models import User, UserCreate, UserUpdate, MessagePlatform
from core.interfaces.repositories import IUserRepository
from infrastructure.database.supabase_client import supabase, run_sync


def _parse_embedding(value) -> Optional[List[float]]:
    """Parse embedding from database - handles string or list format"""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # PostgreSQL vector comes as string like '[0.1,0.2,...]'
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


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
            looking_for=data.get("looking_for"),
            can_help_with=data.get("can_help_with"),
            photo_url=data.get("photo_url"),
            voice_intro_url=data.get("voice_intro_url"),
            social_links=data.get("social_links") or {},
            ai_summary=data.get("ai_summary"),
            onboarding_completed=data.get("onboarding_completed", False),
            is_active=data.get("is_active", True),
            current_event_id=data.get("current_event_id"),
            matching_mode=data.get("matching_mode", "event"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            profile_embedding=_parse_embedding(data.get("profile_embedding")),
            interests_embedding=_parse_embedding(data.get("interests_embedding")),
            expertise_embedding=_parse_embedding(data.get("expertise_embedding")),
            # Professional info (from extraction)
            profession=data.get("profession"),
            company=data.get("company"),
            skills=data.get("skills") or [],
            experience_level=data.get("experience_level"),
            # Personalization fields
            passion_text=data.get("passion_text"),
            passion_themes=data.get("passion_themes") or [],
            connection_mode=data.get("connection_mode"),
            personalization_preference=data.get("personalization_preference"),
            ideal_connection=data.get("ideal_connection"),
            # Referral tracking
            referral_count=data.get("referral_count", 0),
            referred_by=data.get("referred_by"),
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
    def _update_sync(self, user_id: UUID, user_data) -> Optional[dict]:
        if isinstance(user_data, dict):
            update_dict = {k: v for k, v in user_data.items() if v is not None}
        else:
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

    @run_sync
    def _reset_profile_sync(self, platform: MessagePlatform, platform_user_id: str,
                            reset_data: dict) -> Optional[dict]:
        """Reset profile with explicit NULL values (bypasses exclude_none)"""
        response = supabase.table("users").update(reset_data)\
            .eq("platform", platform.value)\
            .eq("platform_user_id", platform_user_id)\
            .execute()
        return response.data[0] if response.data else None

    async def reset_profile(self, platform: MessagePlatform, platform_user_id: str,
                            reset_data: dict) -> Optional[User]:
        """Reset user profile with explicit NULL values"""
        data = await self._reset_profile_sync(platform, platform_user_id, reset_data)
        return self._to_model(data) if data else None

    async def get_or_create(self, user_data: UserCreate) -> User:
        # Try to get existing user
        existing = await self.get_by_platform_id(user_data.platform, user_data.platform_user_id)
        if existing:
            return existing
        # Create new user
        return await self.create(user_data)

    @run_sync
    def _update_embeddings_sync(self, user_id: UUID, embeddings: dict) -> Optional[dict]:
        """Update user embeddings in database"""
        response = supabase.table("users").update(embeddings).eq("id", str(user_id)).execute()
        return response.data[0] if response.data else None

    async def update_embeddings(
        self,
        user_id: UUID,
        profile_embedding: List[float],
        interests_embedding: List[float],
        expertise_embedding: List[float]
    ) -> Optional[User]:
        """Update user's vector embeddings"""
        data = await self._update_embeddings_sync(user_id, {
            "profile_embedding": profile_embedding,
            "interests_embedding": interests_embedding,
            "expertise_embedding": expertise_embedding
        })
        return self._to_model(data) if data else None

    # === SPHERE CITY - City-based User Queries ===

    @run_sync
    def _get_users_by_city_sync(self, city: str, exclude_user_id: UUID, limit: int) -> List[dict]:
        """Get users in a specific city (case-insensitive)"""
        response = supabase.table("users").select("*")\
            .ilike("city_current", city)\
            .neq("id", str(exclude_user_id))\
            .eq("onboarding_completed", True)\
            .eq("is_active", True)\
            .limit(limit)\
            .execute()
        return response.data if response.data else []

    async def get_users_by_city(
        self,
        city: str,
        exclude_user_id: UUID,
        limit: int = 20
    ) -> List[User]:
        """Get users in a specific city for Sphere City matching"""
        data = await self._get_users_by_city_sync(city, exclude_user_id, limit)
        return [self._to_model(d) for d in data]
