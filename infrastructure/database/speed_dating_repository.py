"""
Speed Dating Repository - handles caching of AI-generated conversations.
"""

from typing import Optional
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
from infrastructure.database.supabase_client import supabase, run_sync


@dataclass
class SpeedDatingConversation:
    """Speed dating conversation model"""
    id: UUID
    match_id: UUID
    viewer_user_id: UUID
    conversation_text: str
    language: str
    created_at: datetime


class SpeedDatingRepository:
    """Repository for speed dating conversation cache"""

    def _to_model(self, data: dict) -> SpeedDatingConversation:
        """Convert database row to model"""
        return SpeedDatingConversation(
            id=data["id"],
            match_id=data["match_id"],
            viewer_user_id=data["viewer_user_id"],
            conversation_text=data["conversation_text"],
            language=data.get("language", "en"),
            created_at=data.get("created_at")
        )

    @run_sync
    def _get_conversation_sync(self, match_id: UUID, viewer_user_id: UUID) -> Optional[dict]:
        """Get cached conversation from database"""
        response = supabase.table("speed_dating_conversations").select("*")\
            .eq("match_id", str(match_id))\
            .eq("viewer_user_id", str(viewer_user_id))\
            .execute()
        return response.data[0] if response.data else None

    async def get_conversation(
        self,
        match_id: UUID,
        viewer_user_id: UUID
    ) -> Optional[SpeedDatingConversation]:
        """
        Get cached speed dating conversation.

        Args:
            match_id: The match ID
            viewer_user_id: The user viewing the conversation

        Returns:
            Cached conversation or None if not found
        """
        data = await self._get_conversation_sync(match_id, viewer_user_id)
        return self._to_model(data) if data else None

    @run_sync
    def _save_conversation_sync(
        self,
        match_id: UUID,
        viewer_user_id: UUID,
        conversation_text: str,
        language: str
    ) -> dict:
        """Save or update conversation in database"""
        data = {
            "match_id": str(match_id),
            "viewer_user_id": str(viewer_user_id),
            "conversation_text": conversation_text,
            "language": language
        }
        # Use upsert to handle regeneration (updates existing row if constraint matches)
        response = supabase.table("speed_dating_conversations")\
            .upsert(data, on_conflict="match_id,viewer_user_id")\
            .execute()
        return response.data[0]

    async def save_conversation(
        self,
        match_id: UUID,
        viewer_user_id: UUID,
        conversation_text: str,
        language: str = "en"
    ) -> SpeedDatingConversation:
        """
        Save or update a speed dating conversation.

        Args:
            match_id: The match ID
            viewer_user_id: The user who requested the conversation
            conversation_text: The generated conversation
            language: Language code ('en' or 'ru')

        Returns:
            Saved conversation model
        """
        data = await self._save_conversation_sync(
            match_id, viewer_user_id, conversation_text, language
        )
        return self._to_model(data)

    @run_sync
    def _delete_conversation_sync(self, match_id: UUID, viewer_user_id: UUID) -> bool:
        """Delete conversation from database"""
        response = supabase.table("speed_dating_conversations")\
            .delete()\
            .eq("match_id", str(match_id))\
            .eq("viewer_user_id", str(viewer_user_id))\
            .execute()
        return len(response.data) > 0 if response.data else False

    async def delete_conversation(
        self,
        match_id: UUID,
        viewer_user_id: UUID
    ) -> bool:
        """
        Delete a cached conversation (for regeneration).

        Args:
            match_id: The match ID
            viewer_user_id: The user who owns the conversation

        Returns:
            True if deleted, False if not found
        """
        return await self._delete_conversation_sync(match_id, viewer_user_id)
