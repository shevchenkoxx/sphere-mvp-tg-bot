"""
Meetup Repository - CRUD for meetup_proposals table.
"""

import string
import random
import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta, timezone

from core.domain.models import MeetupProposal, MeetupStatus
from infrastructure.database.supabase_client import supabase, run_sync

logger = logging.getLogger(__name__)

# Characters for short_id generation (base62)
_BASE62 = string.ascii_letters + string.digits


def _generate_short_id(length: int = 6) -> str:
    return "".join(random.choices(_BASE62, k=length))


class MeetupRepository:

    def _to_model(self, data: dict) -> MeetupProposal:
        return MeetupProposal(
            id=data["id"],
            short_id=data["short_id"],
            match_id=data["match_id"],
            proposer_id=data["proposer_id"],
            receiver_id=data["receiver_id"],
            event_id=data.get("event_id"),
            time_slots=data["time_slots"],
            location=data["location"],
            ai_why_meet=data.get("ai_why_meet"),
            ai_topics=data.get("ai_topics"),
            status=data.get("status", "pending"),
            accepted_time_slot=data.get("accepted_time_slot"),
            created_at=data.get("created_at"),
            responded_at=data.get("responded_at"),
            expires_at=data.get("expires_at"),
        )

    # --- CREATE ---

    @run_sync
    def _create_sync(self, data: dict) -> dict:
        response = supabase.table("meetup_proposals").insert(data).execute()
        return response.data[0]

    async def create_proposal(
        self,
        match_id: UUID,
        proposer_id: UUID,
        receiver_id: UUID,
        time_slots: List[int],
        location: str,
        ai_why_meet: Optional[str] = None,
        ai_topics: Optional[List[str]] = None,
        event_id: Optional[UUID] = None,
        expires_hours: int = 2,
    ) -> MeetupProposal:
        now = datetime.now(timezone.utc)
        data = {
            "short_id": _generate_short_id(),
            "match_id": str(match_id),
            "proposer_id": str(proposer_id),
            "receiver_id": str(receiver_id),
            "time_slots": time_slots,
            "location": location[:200],
            "ai_why_meet": ai_why_meet,
            "ai_topics": ai_topics,
            "status": "pending",
            "expires_at": (now + timedelta(hours=expires_hours)).isoformat(),
        }
        if event_id:
            data["event_id"] = str(event_id)

        row = await self._create_sync(data)
        return self._to_model(row)

    # --- READ ---

    @run_sync
    def _get_by_short_id_sync(self, short_id: str) -> Optional[dict]:
        response = (
            supabase.table("meetup_proposals")
            .select("*")
            .eq("short_id", short_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_by_short_id(self, short_id: str) -> Optional[MeetupProposal]:
        data = await self._get_by_short_id_sync(short_id)
        return self._to_model(data) if data else None

    @run_sync
    def _get_by_id_sync(self, proposal_id: UUID) -> Optional[dict]:
        response = (
            supabase.table("meetup_proposals")
            .select("*")
            .eq("id", str(proposal_id))
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_by_id(self, proposal_id: UUID) -> Optional[MeetupProposal]:
        data = await self._get_by_id_sync(proposal_id)
        return self._to_model(data) if data else None

    @run_sync
    def _get_pending_for_match_sync(self, match_id: UUID, proposer_id: UUID) -> Optional[dict]:
        response = (
            supabase.table("meetup_proposals")
            .select("*")
            .eq("match_id", str(match_id))
            .eq("proposer_id", str(proposer_id))
            .eq("status", "pending")
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_pending_for_match(
        self, match_id: UUID, proposer_id: UUID
    ) -> Optional[MeetupProposal]:
        data = await self._get_pending_for_match_sync(match_id, proposer_id)
        return self._to_model(data) if data else None

    # --- UPDATE ---

    @run_sync
    def _update_status_sync(self, proposal_id: UUID, status: str, extra: dict) -> Optional[dict]:
        update_data = {"status": status, **extra}
        response = (
            supabase.table("meetup_proposals")
            .update(update_data)
            .eq("id", str(proposal_id))
            .execute()
        )
        return response.data[0] if response.data else None

    async def accept_proposal(
        self, proposal_id: UUID, accepted_time_slot: int
    ) -> Optional[MeetupProposal]:
        data = await self._update_status_sync(
            proposal_id,
            "accepted",
            {
                "accepted_time_slot": accepted_time_slot,
                "responded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return self._to_model(data) if data else None

    async def decline_proposal(self, proposal_id: UUID) -> Optional[MeetupProposal]:
        data = await self._update_status_sync(
            proposal_id,
            "declined",
            {"responded_at": datetime.now(timezone.utc).isoformat()},
        )
        return self._to_model(data) if data else None

    async def cancel_proposal(self, proposal_id: UUID) -> Optional[MeetupProposal]:
        data = await self._update_status_sync(proposal_id, "cancelled", {})
        return self._to_model(data) if data else None

    async def update_ai_content(
        self,
        proposal_id: UUID,
        ai_why_meet: str,
        ai_topics: List[str],
    ) -> Optional[MeetupProposal]:
        data = await self._update_status_sync(
            proposal_id,
            "pending",  # keep status
            {"ai_why_meet": ai_why_meet, "ai_topics": ai_topics},
        )
        return self._to_model(data) if data else None

    def is_expired(self, proposal: MeetupProposal) -> bool:
        if not proposal.expires_at:
            return False
        now = datetime.now(timezone.utc)
        expires = proposal.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires
