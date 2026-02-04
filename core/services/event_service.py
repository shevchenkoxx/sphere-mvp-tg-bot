"""
Event service - business logic for event operations.
"""

import logging
import random
import string
from typing import Optional, List
from uuid import UUID
from core.domain.models import Event, EventCreate, User, MessagePlatform
from core.domain.constants import EVENT_CODE_LENGTH
from core.interfaces.repositories import IEventRepository, IUserRepository

logger = logging.getLogger(__name__)


class EventService:
    """Service for event-related operations"""

    def __init__(self, event_repo: IEventRepository, user_repo: IUserRepository):
        self.event_repo = event_repo
        self.user_repo = user_repo

    def generate_event_code(self) -> str:
        """Generate unique event code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=EVENT_CODE_LENGTH))

    async def create_event(
        self,
        name: str,
        organizer_platform: MessagePlatform,
        organizer_platform_id: str,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> Event:
        """Create a new event"""
        event_data = EventCreate(
            name=name,
            description=description,
            location=location,
            organizer_platform=organizer_platform,
            organizer_platform_id=organizer_platform_id
        )
        return await self.event_repo.create(event_data)

    async def get_event_by_code(self, code: str) -> Optional[Event]:
        """Get event by code"""
        return await self.event_repo.get_by_code(code)

    async def get_event_by_id(self, event_id: UUID) -> Optional[Event]:
        """Get event by ID"""
        return await self.event_repo.get_by_id(event_id)

    async def join_event(
        self,
        event_code: str,
        platform: MessagePlatform,
        platform_user_id: str
    ) -> tuple[bool, str, Optional[Event]]:
        """
        Join user to event.
        Returns: (success, message, event)
        """
        logger.info(f"[EVENT_SERVICE] join_event called with code='{event_code}', platform={platform}, user={platform_user_id}")

        # Get event
        event = await self.event_repo.get_by_code(event_code)
        logger.info(f"[EVENT_SERVICE] get_by_code result: {event}")
        if not event:
            logger.warning(f"[EVENT_SERVICE] Event not found for code '{event_code}'")
            return False, "Event not found or ended", None

        # Get user
        user = await self.user_repo.get_by_platform_id(platform, platform_user_id)
        if not user:
            return False, "User not found", None

        if not user.onboarding_completed:
            return False, "Complete your profile first", None

        # Check if already participant
        if await self.event_repo.is_participant(event.id, user.id):
            return True, "Already a participant", event

        # Add to event
        await self.event_repo.add_participant(event.id, user.id)

        # Update user's current event
        await self.user_repo.update(user.id, {"current_event_id": str(event.id)})

        return True, "Successfully joined!", event

    async def get_event_participants(self, event_id: UUID) -> List[User]:
        """Get all participants of an event"""
        return await self.event_repo.get_participants(event_id)

    async def get_user_events(
        self,
        platform: MessagePlatform,
        platform_user_id: str
    ) -> List[Event]:
        """Get all events user participates in"""
        user = await self.user_repo.get_by_platform_id(platform, platform_user_id)
        if not user:
            return []
        return await self.event_repo.get_user_events(user.id)

    def generate_deep_link(self, event_code: str, bot_username: str) -> str:
        """Generate deep link for event"""
        return f"https://t.me/{bot_username}?start=event_{event_code}"

    def generate_qr_data(self, event_code: str, bot_username: str) -> str:
        """Generate data for QR code"""
        return self.generate_deep_link(event_code, bot_username)
