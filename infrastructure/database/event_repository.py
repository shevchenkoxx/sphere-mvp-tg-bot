"""
Supabase implementation of Event repository.
"""

import logging
import random
import string
from typing import Optional, List

logger = logging.getLogger(__name__)
from uuid import UUID
from core.domain.models import Event, EventCreate, User, MessagePlatform
from core.domain.constants import EVENT_CODE_LENGTH
from core.interfaces.repositories import IEventRepository
from infrastructure.database.supabase_client import supabase, run_sync
from infrastructure.database.user_repository import SupabaseUserRepository


class SupabaseEventRepository(IEventRepository):
    """Supabase implementation of event repository"""

    def __init__(self):
        self._user_repo = SupabaseUserRepository()

    def _to_model(self, data: dict) -> Event:
        """Convert database row to Event model"""
        return Event(
            id=data["id"],
            code=data["code"],
            name=data["name"],
            description=data.get("description"),
            location=data.get("location"),
            event_date=data.get("event_date"),
            organizer_id=data.get("organizer_id"),
            image_url=data.get("image_url"),
            is_active=data.get("is_active", True),
            settings=data.get("settings") or {},
            created_at=data.get("created_at"),
        )

    def _generate_code(self) -> str:
        """Generate unique event code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=EVENT_CODE_LENGTH))

    @run_sync
    def _get_by_id_sync(self, event_id: UUID) -> Optional[dict]:
        response = supabase.table("events").select("*").eq("id", str(event_id)).execute()
        return response.data[0] if response.data else None

    async def get_by_id(self, event_id: UUID) -> Optional[Event]:
        data = await self._get_by_id_sync(event_id)
        return self._to_model(data) if data else None

    @run_sync
    def _get_by_code_sync(self, code: str) -> Optional[dict]:
        logger.info(f"[EVENT_REPO] Looking for event with code: '{code}'")
        response = supabase.table("events").select("*")\
            .eq("code", code)\
            .eq("is_active", True)\
            .execute()
        logger.info(f"[EVENT_REPO] Response data: {response.data}")
        return response.data[0] if response.data else None

    async def get_by_code(self, code: str) -> Optional[Event]:
        data = await self._get_by_code_sync(code)
        return self._to_model(data) if data else None

    @run_sync
    def _create_sync(self, event_data: EventCreate, organizer_id: Optional[UUID]) -> dict:
        code = self._generate_code()
        data = {
            "code": code,
            "name": event_data.name,
            "description": event_data.description,
            "location": event_data.location,
            "event_date": event_data.event_date.isoformat() if event_data.event_date else None,
            "organizer_id": str(organizer_id) if organizer_id else None,
            "settings": event_data.settings,
        }
        response = supabase.table("events").insert(data).execute()
        return response.data[0]

    async def create(self, event_data: EventCreate) -> Event:
        # Get organizer user ID
        organizer = await self._user_repo.get_by_platform_id(
            event_data.organizer_platform,
            event_data.organizer_platform_id
        )
        organizer_id = organizer.id if organizer else None

        data = await self._create_sync(event_data, organizer_id)
        return self._to_model(data)

    @run_sync
    def _get_participants_sync(self, event_id: UUID) -> List[dict]:
        response = supabase.table("event_participants")\
            .select("*, users(*)")\
            .eq("event_id", str(event_id))\
            .execute()
        return [p["users"] for p in response.data] if response.data else []

    async def get_participants(self, event_id: UUID) -> List[User]:
        data = await self._get_participants_sync(event_id)
        return [self._user_repo._to_model(d) for d in data if d]

    @run_sync
    def _add_participant_sync(self, event_id: UUID, user_id: UUID) -> bool:
        data = {
            "event_id": str(event_id),
            "user_id": str(user_id),
        }
        response = supabase.table("event_participants").upsert(data).execute()
        return bool(response.data)

    async def add_participant(self, event_id: UUID, user_id: UUID) -> bool:
        return await self._add_participant_sync(event_id, user_id)

    @run_sync
    def _get_user_events_sync(self, user_id: UUID) -> List[dict]:
        response = supabase.table("event_participants")\
            .select("*, events(*)")\
            .eq("user_id", str(user_id))\
            .execute()
        return [p["events"] for p in response.data] if response.data else []

    async def get_user_events(self, user_id: UUID) -> List[Event]:
        data = await self._get_user_events_sync(user_id)
        return [self._to_model(d) for d in data if d]

    @run_sync
    def _is_participant_sync(self, event_id: UUID, user_id: UUID) -> bool:
        response = supabase.table("event_participants")\
            .select("id")\
            .eq("event_id", str(event_id))\
            .eq("user_id", str(user_id))\
            .execute()
        return len(response.data) > 0 if response.data else False

    async def is_participant(self, event_id: UUID, user_id: UUID) -> bool:
        return await self._is_participant_sync(event_id, user_id)
