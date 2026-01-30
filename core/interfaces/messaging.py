"""
Messaging interfaces - abstractions for multi-platform messaging.
This allows supporting Telegram, WhatsApp, and other platforms with the same business logic.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Any
from core.domain.models import MessagePlatform


class IMessenger(ABC):
    """Interface for messenger adapters (Telegram, WhatsApp, etc.)"""

    @property
    @abstractmethod
    def platform(self) -> MessagePlatform:
        """Return the platform this messenger represents"""
        pass

    @abstractmethod
    async def send_message(
        self,
        user_platform_id: str,
        text: str,
        reply_markup: Optional[Any] = None
    ) -> bool:
        """Send a text message to user"""
        pass

    @abstractmethod
    async def send_match_notification(
        self,
        user_platform_id: str,
        partner_name: str,
        explanation: str,
        icebreaker: str,
        match_id: str
    ) -> bool:
        """Send notification about new match"""
        pass

    @abstractmethod
    async def get_file_url(self, file_id: str) -> Optional[str]:
        """Get downloadable URL for a file (voice message, photo, etc.)"""
        pass


class INotificationService(ABC):
    """Interface for sending notifications across platforms"""

    @abstractmethod
    async def notify_match(
        self,
        user_id: str,
        platform: MessagePlatform,
        platform_user_id: str,
        partner_name: str,
        explanation: str,
        icebreaker: str,
        match_id: str
    ) -> bool:
        """Send match notification to user on their platform"""
        pass

    @abstractmethod
    async def notify_event_update(
        self,
        event_id: str,
        message: str
    ) -> int:
        """Notify all event participants, return count of notified users"""
        pass
