"""
User service - business logic for user operations.
Platform-agnostic, works through interfaces.
"""

from typing import Optional
from uuid import UUID
from core.domain.models import (
    User, UserCreate, UserUpdate,
    MessagePlatform, OnboardingData
)
from core.domain.constants import (
    MIN_NAME_LENGTH, MAX_NAME_LENGTH, MAX_INTERESTS, MAX_GOALS
)
from core.interfaces.repositories import IUserRepository
from core.interfaces.ai import IAIService


class UserService:
    """Service for user-related operations"""

    def __init__(self, user_repo: IUserRepository, ai_service: IAIService):
        self.user_repo = user_repo
        self.ai_service = ai_service

    async def get_user(self, user_id: UUID) -> Optional[User]:
        """Get user by internal ID"""
        return await self.user_repo.get_by_id(user_id)

    async def get_user_by_platform(
        self,
        platform: MessagePlatform,
        platform_user_id: str
    ) -> Optional[User]:
        """Get user by platform-specific ID"""
        return await self.user_repo.get_by_platform_id(platform, platform_user_id)

    async def get_or_create_user(
        self,
        platform: MessagePlatform,
        platform_user_id: str,
        username: Optional[str] = None,
        first_name: Optional[str] = None
    ) -> User:
        """Get existing user or create a new one"""
        user_data = UserCreate(
            platform=platform,
            platform_user_id=platform_user_id,
            username=username,
            first_name=first_name
        )
        return await self.user_repo.get_or_create(user_data)

    async def update_user(
        self,
        platform: MessagePlatform,
        platform_user_id: str,
        **kwargs
    ) -> Optional[User]:
        """Update user data by platform ID"""
        update_data = UserUpdate(**{k: v for k, v in kwargs.items() if v is not None})
        return await self.user_repo.update_by_platform_id(platform, platform_user_id, update_data)

    async def reset_user(
        self,
        platform: MessagePlatform,
        platform_user_id: str
    ) -> Optional[User]:
        """Full reset of user profile - clears all fields to defaults"""
        # Use raw update to set fields including NULL for current_event_id
        reset_data = {
            "display_name": None,
            "first_name": None,
            "bio": None,
            "interests": [],
            "goals": [],
            "looking_for": None,
            "can_help_with": None,
            "ai_summary": None,
            "photo_url": None,
            "current_event_id": None,
            "onboarding_completed": False
        }
        return await self.user_repo.reset_profile(platform, platform_user_id, reset_data)

    async def complete_onboarding(
        self,
        platform: MessagePlatform,
        platform_user_id: str,
        onboarding_data: OnboardingData
    ) -> User:
        """Complete onboarding process and generate AI summary"""
        # Update user with onboarding data
        update_data = UserUpdate(
            display_name=onboarding_data.display_name,
            city_born=onboarding_data.city_born,
            city_current=onboarding_data.city_current,
            interests=onboarding_data.selected_interests,
            goals=onboarding_data.selected_goals,
            bio=onboarding_data.bio,
            onboarding_completed=True
        )

        user = await self.user_repo.update_by_platform_id(platform, platform_user_id, update_data)

        if user:
            # Generate AI summary
            user_dict = user.model_dump()
            summary = await self.ai_service.generate_user_summary(user_dict)

            # Update with summary
            await self.user_repo.update_by_platform_id(
                platform, platform_user_id,
                UserUpdate(ai_summary=summary)
            )

        return await self.user_repo.get_by_platform_id(platform, platform_user_id)

    def validate_name(self, name: str) -> tuple[bool, str]:
        """Validate display name"""
        name = name.strip()
        if len(name) < MIN_NAME_LENGTH:
            return False, f"Name must be at least {MIN_NAME_LENGTH} characters"
        if len(name) > MAX_NAME_LENGTH:
            return False, f"Name must be at most {MAX_NAME_LENGTH} characters"
        return True, ""

    def validate_interests(self, interests: list) -> tuple[bool, str]:
        """Validate interests selection"""
        if not interests:
            return False, "Select at least one interest"
        if len(interests) > MAX_INTERESTS:
            return False, f"Maximum {MAX_INTERESTS} interests"
        return True, ""

    def validate_goals(self, goals: list) -> tuple[bool, str]:
        """Validate goals selection"""
        if not goals:
            return False, "Select at least one goal"
        if len(goals) > MAX_GOALS:
            return False, f"Maximum {MAX_GOALS} goals"
        return True, ""

    async def is_onboarding_completed(
        self,
        platform: MessagePlatform,
        platform_user_id: str
    ) -> bool:
        """Check if user completed onboarding"""
        user = await self.user_repo.get_by_platform_id(platform, platform_user_id)
        return user is not None and user.onboarding_completed
