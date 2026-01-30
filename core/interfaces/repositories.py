"""
Repository interfaces - abstractions for data access.
This allows swapping implementations (Supabase -> PostgreSQL -> MongoDB, etc.)
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from core.domain.models import (
    User, UserCreate, UserUpdate,
    Event, EventCreate,
    Match, MatchCreate, MatchStatus,
    Message, MessageCreate,
    MessagePlatform,
)


class IUserRepository(ABC):
    """Interface for user data access"""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by internal ID"""
        pass

    @abstractmethod
    async def get_by_platform_id(self, platform: MessagePlatform, platform_user_id: str) -> Optional[User]:
        """Get user by platform-specific ID (telegram_id, whatsapp_id, etc.)"""
        pass

    @abstractmethod
    async def create(self, user_data: UserCreate) -> User:
        """Create a new user"""
        pass

    @abstractmethod
    async def update(self, user_id: UUID, user_data: UserUpdate) -> Optional[User]:
        """Update user data"""
        pass

    @abstractmethod
    async def update_by_platform_id(self, platform: MessagePlatform, platform_user_id: str,
                                     user_data: UserUpdate) -> Optional[User]:
        """Update user data by platform ID"""
        pass

    @abstractmethod
    async def get_or_create(self, user_data: UserCreate) -> User:
        """Get existing user or create new one"""
        pass


class IEventRepository(ABC):
    """Interface for event data access"""

    @abstractmethod
    async def get_by_id(self, event_id: UUID) -> Optional[Event]:
        """Get event by ID"""
        pass

    @abstractmethod
    async def get_by_code(self, code: str) -> Optional[Event]:
        """Get event by unique code"""
        pass

    @abstractmethod
    async def create(self, event_data: EventCreate) -> Event:
        """Create a new event"""
        pass

    @abstractmethod
    async def get_participants(self, event_id: UUID) -> List[User]:
        """Get all participants of an event"""
        pass

    @abstractmethod
    async def add_participant(self, event_id: UUID, user_id: UUID) -> bool:
        """Add user to event"""
        pass

    @abstractmethod
    async def get_user_events(self, user_id: UUID) -> List[Event]:
        """Get all events a user participates in"""
        pass

    @abstractmethod
    async def is_participant(self, event_id: UUID, user_id: UUID) -> bool:
        """Check if user is already a participant"""
        pass


class IMatchRepository(ABC):
    """Interface for match data access"""

    @abstractmethod
    async def get_by_id(self, match_id: UUID) -> Optional[Match]:
        """Get match by ID"""
        pass

    @abstractmethod
    async def create(self, match_data: MatchCreate) -> Match:
        """Create a new match"""
        pass

    @abstractmethod
    async def get_user_matches(self, user_id: UUID, status: Optional[MatchStatus] = None) -> List[Match]:
        """Get all matches for a user"""
        pass

    @abstractmethod
    async def update_status(self, match_id: UUID, status: MatchStatus) -> Optional[Match]:
        """Update match status"""
        pass

    @abstractmethod
    async def mark_notified(self, match_id: UUID, user_position: str) -> None:
        """Mark user as notified about match (user_position: 'a' or 'b')"""
        pass

    @abstractmethod
    async def exists(self, event_id: UUID, user_a_id: UUID, user_b_id: UUID) -> bool:
        """Check if match already exists between two users for an event"""
        pass

    @abstractmethod
    async def get_unnotified_matches(self, user_id: UUID) -> List[Match]:
        """Get matches where user hasn't been notified yet"""
        pass


class IMessageRepository(ABC):
    """Interface for message data access"""

    @abstractmethod
    async def create(self, message_data: MessageCreate) -> Message:
        """Create a new message"""
        pass

    @abstractmethod
    async def get_by_match(self, match_id: UUID, limit: int = 50, offset: int = 0) -> List[Message]:
        """Get messages for a match"""
        pass

    @abstractmethod
    async def mark_as_read(self, message_id: UUID) -> None:
        """Mark message as read"""
        pass

    @abstractmethod
    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread messages for a user"""
        pass
