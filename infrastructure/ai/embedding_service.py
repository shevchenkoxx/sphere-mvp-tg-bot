"""
Embedding service for generating user profile vectors.
Uses OpenAI text-embedding-3-small (1536 dimensions).
"""

import asyncio
from typing import List, Tuple, Optional
from openai import AsyncOpenAI
from core.domain.models import User
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Timeout for embedding API calls (seconds)
EMBEDDING_TIMEOUT = 15


class EmbeddingService:
    """Generate embeddings for vector-based matching"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=20.0)
        self.model = "text-embedding-3-small"  # 1536 dims, cheap, fast

    def _build_profile_text(self, user: User) -> str:
        """Build rich profile text for embedding"""
        parts = []

        if user.bio:
            parts.append(f"About: {user.bio}")
        if user.looking_for:
            parts.append(f"Looking for: {user.looking_for}")
        if user.can_help_with:
            parts.append(f"Can help with: {user.can_help_with}")
        if user.interests:
            parts.append(f"Interests: {', '.join(user.interests)}")
        if user.goals:
            parts.append(f"Goals: {', '.join(user.goals)}")

        return " | ".join(parts) if parts else "New user"

    def _build_interests_text(self, user: User) -> str:
        """Build interests-focused text"""
        parts = []
        if user.interests:
            parts.append(f"Interests: {', '.join(user.interests)}")
        if user.goals:
            parts.append(f"Goals: {', '.join(user.goals)}")
        if user.looking_for:
            parts.append(f"Looking for: {user.looking_for}")
        return " | ".join(parts) if parts else "General networking"

    def _build_expertise_text(self, user: User) -> str:
        """Build expertise-focused text"""
        parts = []
        if user.can_help_with:
            parts.append(f"Can help with: {user.can_help_with}")
        if user.bio:
            # Extract professional info from bio
            parts.append(f"Background: {user.bio[:200]}")
        return " | ".join(parts) if parts else "Open to connecting"

    async def generate_embeddings(
        self, user: User
    ) -> Optional[Tuple[List[float], List[float], List[float]]]:
        """
        Generate all three embeddings in a single API call.

        Returns:
            Tuple of (profile_embedding, interests_embedding, expertise_embedding)
            or None if generation fails (non-blocking - matching will use fallback)
        """
        texts = [
            self._build_profile_text(user),
            self._build_interests_text(user),
            self._build_expertise_text(user),
        ]

        try:
            # Add timeout to prevent hanging
            response = await asyncio.wait_for(
                self.client.embeddings.create(
                    model=self.model,
                    input=texts
                ),
                timeout=EMBEDDING_TIMEOUT
            )

            return (
                response.data[0].embedding,  # profile
                response.data[1].embedding,  # interests
                response.data[2].embedding,  # expertise
            )
        except asyncio.TimeoutError:
            logger.warning(f"Embedding generation timed out for user {user.id}")
            return None
        except Exception as e:
            logger.error(f"Embedding generation failed for user {user.id}: {e}")
            return None  # Don't raise - let matching use fallback

    async def generate_single_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=[text]
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Single embedding generation failed: {e}")
            raise
