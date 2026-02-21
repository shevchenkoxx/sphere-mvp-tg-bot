"""
Conversation Log Repository — fire-and-forget message logging.
"""

from __future__ import annotations

import logging
from typing import Optional
from infrastructure.database.supabase_client import supabase, run_sync

logger = logging.getLogger(__name__)


class ConversationLogRepository:
    """Logs all incoming/outgoing messages for admin dashboard."""

    @run_sync
    def _log_sync(self, data: dict):
        supabase.table("conversation_logs").insert(data).execute()

    async def log_message(
        self,
        telegram_user_id: int,
        direction: str,
        message_type: str = "text",
        content: Optional[str] = None,
        callback_data: Optional[str] = None,
        api_method: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        has_media: bool = False,
        fsm_state: Optional[str] = None,
    ):
        """Fire-and-forget log. Never raises."""
        try:
            data = {
                "telegram_user_id": telegram_user_id,
                "direction": direction,
                "message_type": message_type,
            }
            if content is not None:
                data["content"] = content[:4000]  # safety cap
            if callback_data is not None:
                data["callback_data"] = callback_data
            if api_method is not None:
                data["api_method"] = api_method
            if telegram_message_id is not None:
                data["telegram_message_id"] = telegram_message_id
            if has_media:
                data["has_media"] = True
            if fsm_state is not None:
                data["fsm_state"] = fsm_state

            await self._log_sync(data)
        except Exception as e:
            logger.debug(f"Conv log failed: {e}")

    @run_sync
    def _get_conversation_sync(self, telegram_user_id: int, limit: int, offset: int):
        resp = (
            supabase.table("conversation_logs")
            .select("*")
            .eq("telegram_user_id", telegram_user_id)
            .order("created_at", desc=False)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return resp.data or []

    async def get_user_conversation(
        self, telegram_user_id: int, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """Get chronological messages for a user."""
        return await self._get_conversation_sync(telegram_user_id, limit, offset)

    @run_sync
    def _get_active_users_sync(self, limit: int, hours: int):
        from datetime import datetime, timedelta, timezone

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        # Get distinct users with their latest message time
        resp = (
            supabase.rpc(
                "get_active_conversation_users",
                {"cutoff_time": cutoff, "max_results": limit},
            ).execute()
        )
        return resp.data or []

    @run_sync
    def _get_active_users_fallback_sync(self, limit: int, hours: int):
        """Fallback: get recent logs and aggregate in Python."""
        from datetime import datetime, timedelta, timezone

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        resp = (
            supabase.table("conversation_logs")
            .select("telegram_user_id, created_at, direction")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(5000)
            .execute()
        )
        return resp.data or []

    async def get_active_users(self, limit: int = 50, hours: int = 72) -> list[dict]:
        """Recent active users sorted by last activity."""
        try:
            return await self._get_active_users_sync(limit, hours)
        except Exception:
            # RPC may not exist yet — fallback to client-side aggregation
            rows = await self._get_active_users_fallback_sync(limit, hours)
            seen: dict[int, dict] = {}
            for r in rows:
                uid = r["telegram_user_id"]
                if uid not in seen:
                    seen[uid] = {
                        "telegram_user_id": uid,
                        "last_active": r["created_at"],
                        "message_count": 0,
                    }
                seen[uid]["message_count"] += 1
            result = sorted(seen.values(), key=lambda x: x["last_active"], reverse=True)
            return result[:limit]

    @run_sync
    def _get_count_sync(self, telegram_user_id: int):
        resp = (
            supabase.table("conversation_logs")
            .select("id", count="exact")
            .eq("telegram_user_id", telegram_user_id)
            .execute()
        )
        return resp.count or 0

    async def get_message_count(self, telegram_user_id: int) -> int:
        """Total message count for a user."""
        return await self._get_count_sync(telegram_user_id)

    @run_sync
    def _search_conversations_sync(self, query: str, limit: int):
        resp = (
            supabase.table("conversation_logs")
            .select("telegram_user_id, content, created_at")
            .ilike("content", f"%{query}%")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []

    async def search_conversations(self, query: str, limit: int = 50) -> list[dict]:
        """Search message content across all users."""
        return await self._search_conversations_sync(query, limit)

    @run_sync
    def _get_fsm_state_logs_sync(self, limit: int):
        resp = (
            supabase.table("conversation_logs")
            .select("telegram_user_id, fsm_state, created_at")
            .not_.is_("fsm_state", "null")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []

    async def get_fsm_state_logs(self, limit: int = 10000) -> list[dict]:
        """Get logs with FSM state for onboarding funnel analysis."""
        return await self._get_fsm_state_logs_sync(limit)

    @run_sync
    def _get_message_stats_sync(self, cutoff_iso: str | None, limit: int):
        q = (
            supabase.table("conversation_logs")
            .select("telegram_user_id, direction, message_type, created_at")
        )
        if cutoff_iso:
            q = q.gte("created_at", cutoff_iso)
        resp = q.order("created_at", desc=True).limit(limit).execute()
        return resp.data or []

    async def get_message_stats(self, cutoff=None, limit: int = 10000) -> list[dict]:
        """Get message metadata for analytics (direction, type, timestamps)."""
        cutoff_iso = cutoff.isoformat() if cutoff else None
        return await self._get_message_stats_sync(cutoff_iso, limit)
