"""
Message Observation Pipeline — batched topic/sentiment extraction.

Drains the in-memory queue from community_group.py every scheduler tick,
batches messages per community, extracts topics + sentiment via gpt-4o-mini,
and stores in the message_observations table. After enough observations
per user, generates a community_profile_summary.
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone

from openai import AsyncOpenAI
from config.settings import settings
from core.domain.models import MessagePlatform, UserUpdate
from infrastructure.database.supabase_client import supabase, run_sync

logger = logging.getLogger(__name__)

# Limits
MAX_OBSERVATIONS_PER_USER_PER_DAY = 20
MIN_WORDS_FOR_ANALYSIS = 10
BATCH_SIZE = 20  # Max messages per LLM call
SUMMARY_THRESHOLD = 5  # Observations before generating profile summary


class ObservationService:
    """Batch-processes group messages into structured observations."""

    def __init__(self, user_repo):
        self.user_repo = user_repo
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)

    async def process_queue(self, queue_items: List[dict]) -> int:
        """Process a batch of queued messages. Returns count of observations stored."""
        if not queue_items:
            return 0

        # Group by community
        by_community: Dict[str, List[dict]] = {}
        for item in queue_items:
            cid = item["community_id"]
            by_community.setdefault(cid, []).append(item)

        total_stored = 0
        for community_id, messages in by_community.items():
            try:
                stored = await self._process_community_batch(community_id, messages)
                total_stored += stored
            except Exception as e:
                logger.error(f"[OBSERVE] Failed to process community {community_id}: {e}", exc_info=True)

        return total_stored

    async def _process_community_batch(self, community_id: str, messages: List[dict]) -> int:
        """Process messages for one community."""
        # Filter: skip too-short messages, cap per user
        filtered = []
        user_counts: Dict[str, int] = {}

        for msg in messages:
            text = msg.get("text", "")
            if len(text.split()) < MIN_WORDS_FOR_ANALYSIS:
                continue
            user_tg_id = msg["user_tg_id"]
            user_counts[user_tg_id] = user_counts.get(user_tg_id, 0) + 1
            if user_counts[user_tg_id] > MAX_OBSERVATIONS_PER_USER_PER_DAY:
                continue
            filtered.append(msg)

        if not filtered:
            return 0

        # Process in batches
        stored = 0
        for i in range(0, len(filtered), BATCH_SIZE):
            batch = filtered[i:i + BATCH_SIZE]
            try:
                results = await self._extract_topics_batch(batch)
                for msg, result in zip(batch, results):
                    if await self._store_observation(community_id, msg, result):
                        stored += 1
            except Exception as e:
                logger.error(f"[OBSERVE] Batch extraction failed: {e}")

        # Check if any user crossed the summary threshold
        for user_tg_id in user_counts:
            try:
                await self._maybe_generate_summary(community_id, user_tg_id)
            except Exception as e:
                logger.warning(f"[OBSERVE] Summary generation failed for {user_tg_id}: {e}")

        return stored

    async def _extract_topics_batch(self, messages: List[dict]) -> List[dict]:
        """Extract topics + sentiment from a batch of messages via LLM."""
        numbered = "\n".join(
            f"{i+1}. {msg['text'][:200]}"
            for i, msg in enumerate(messages)
        )

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "You analyze group chat messages and extract topics and sentiment. "
                        "For each numbered message, output one line in this exact format:\n"
                        "N|topic1,topic2|sentiment\n"
                        "Topics: 1-3 lowercase keywords (e.g., ai, startups, hiring, travel).\n"
                        "Sentiment: positive, negative, or neutral.\n"
                        "Example: 1|ai,machine-learning|positive"
                    )},
                    {"role": "user", "content": numbered},
                ],
                max_tokens=500,
                temperature=0.1,
            )

            raw = response.choices[0].message.content or ""
            return self._parse_batch_results(raw, len(messages))
        except Exception as e:
            logger.error(f"[OBSERVE] LLM extraction failed: {e}")
            return [{"topics": [], "sentiment": "neutral"} for _ in messages]

    def _parse_batch_results(self, raw: str, expected_count: int) -> List[dict]:
        """Parse LLM batch results into list of dicts."""
        results = []
        lines = [line.strip() for line in raw.strip().split("\n") if line.strip()]

        for line in lines:
            parts = line.split("|")
            if len(parts) >= 3:
                topics = [t.strip() for t in parts[1].split(",") if t.strip()]
                sentiment = parts[2].strip().lower()
                if sentiment not in ("positive", "negative", "neutral"):
                    sentiment = "neutral"
                results.append({"topics": topics[:3], "sentiment": sentiment})
            else:
                results.append({"topics": [], "sentiment": "neutral"})

        # Pad if LLM returned fewer lines
        while len(results) < expected_count:
            results.append({"topics": [], "sentiment": "neutral"})

        return results[:expected_count]

    @run_sync
    def _store_observation_sync(self, data: dict):
        supabase.table("message_observations").insert(data).execute()

    async def _store_observation(self, community_id: str, msg: dict, result: dict):
        """Store a single observation in the DB."""
        user = await self.user_repo.get_by_platform_id(MessagePlatform.TELEGRAM, str(msg["user_tg_id"]))
        if not user:
            return False

        data = {
            "community_id": community_id,
            "user_id": str(user.id),
            "topics": result.get("topics", []),
            "sentiment": result.get("sentiment", "neutral"),
            "snippet": msg["text"][:200],
            "message_type": "text",
        }
        try:
            await self._store_observation_sync(data)
            return True
        except Exception as e:
            logger.error(f"[OBSERVE] Failed to store observation: {e}")
            return False

    @run_sync
    def _count_user_observations_sync(self, community_id: str, user_id: str) -> int:
        response = supabase.table("message_observations").select("id", count="exact")\
            .eq("community_id", community_id)\
            .eq("user_id", user_id)\
            .execute()
        return response.count if response.count is not None else 0

    @run_sync
    def _get_user_topics_sync(self, community_id: str, user_id: str) -> List[dict]:
        response = supabase.table("message_observations").select("topics, sentiment")\
            .eq("community_id", community_id)\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()
        return response.data or []

    async def _maybe_generate_summary(self, community_id: str, user_tg_id: str):
        """Generate community_profile_summary if user has enough observations."""
        user = await self.user_repo.get_by_platform_id(MessagePlatform.TELEGRAM, str(user_tg_id))
        if not user:
            return

        count = await self._count_user_observations_sync(community_id, str(user.id))

        has_summary = getattr(user, 'community_profile_summary', None)
        if has_summary and count % 20 != 0:
            return  # Refresh summary every 20 observations (at 20, 40, 60, ...)
        if not has_summary and count < SUMMARY_THRESHOLD:
            return

        observations = await self._get_user_topics_sync(community_id, str(user.id))
        if not observations:
            return

        # Collect all topics
        all_topics = []
        sentiments = []
        for obs in observations:
            all_topics.extend(obs.get("topics") or [])
            sentiments.append(obs.get("sentiment", "neutral"))

        # Count topic frequency
        topic_counts: Dict[str, int] = {}
        for t in all_topics:
            topic_counts[t] = topic_counts.get(t, 0) + 1

        top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:8]
        positive_pct = round(sentiments.count("positive") / len(sentiments) * 100) if sentiments else 0

        summary = (
            f"Active in: {', '.join(t for t, _ in top_topics[:5])}. "
            f"Vibe: {'positive' if positive_pct > 60 else 'balanced' if positive_pct > 30 else 'thoughtful'}. "
            f"Based on {count} messages."
        )

        # Save to user profile
        try:
            await self.user_repo.update_by_platform_id(
                MessagePlatform.TELEGRAM,
                str(user_tg_id),
                UserUpdate(community_profile_summary=summary),
            )
            logger.info(f"[OBSERVE] Generated community summary for user {user.id}: {summary[:80]}...")
        except Exception as e:
            logger.error(f"[OBSERVE] Failed to save summary for user {user.id}: {e}")

    # -----------------------------------------------------------------
    # Community-wide analytics (used by Pulse)
    # -----------------------------------------------------------------

    @run_sync
    def _get_community_topics_sync(self, community_id: str, days: int = 7) -> List[dict]:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        response = supabase.table("message_observations").select("topics, sentiment, user_id")\
            .eq("community_id", community_id)\
            .gte("created_at", cutoff)\
            .execute()
        return response.data or []

    async def get_community_analytics(self, community_id: str, days: int = 7) -> dict:
        """Get aggregated analytics for a community over N days."""
        observations = await self._get_community_topics_sync(community_id, days)

        if not observations:
            return {"total": 0, "topics": [], "active_users": 0, "sentiment": "neutral"}

        all_topics = []
        sentiments = []
        user_ids = set()

        for obs in observations:
            all_topics.extend(obs.get("topics") or [])
            sentiments.append(obs.get("sentiment", "neutral"))
            user_ids.add(obs["user_id"])

        topic_counts: Dict[str, int] = {}
        for t in all_topics:
            topic_counts[t] = topic_counts.get(t, 0) + 1

        top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:10]
        positive = sentiments.count("positive")
        negative = sentiments.count("negative")
        total = len(sentiments)

        return {
            "total": len(observations),
            "topics": [{"topic": t, "count": c} for t, c in top_topics],
            "active_users": len(user_ids),
            "sentiment": "positive" if positive > negative else "negative" if negative > positive else "neutral",
            "sentiment_breakdown": {
                "positive": positive,
                "negative": negative,
                "neutral": total - positive - negative,
            },
        }
