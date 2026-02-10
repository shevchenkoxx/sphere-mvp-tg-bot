"""
Backfill embeddings for all users who are missing them.
Run once before release to ensure vector matching works for everyone.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.database.supabase_client import supabase
from infrastructure.database.user_repository import SupabaseUserRepository
from infrastructure.ai.embedding_service import EmbeddingService


async def backfill():
    user_repo = SupabaseUserRepository()
    embedding_service = EmbeddingService()

    # Get all users without embeddings
    response = supabase.table("users").select("id, display_name, bio, looking_for").is_("profile_embedding", "null").eq("onboarding_completed", True).execute()

    users_without = response.data or []
    print(f"Found {len(users_without)} users without embeddings")

    success = 0
    failed = 0

    for row in users_without:
        user_id = row["id"]
        name = row.get("display_name") or row.get("id")

        # Fetch full user object
        from uuid import UUID
        user = await user_repo.get_by_id(UUID(user_id))
        if not user:
            print(f"  SKIP {name} - user not found")
            failed += 1
            continue

        # Generate embeddings
        result = await embedding_service.generate_embeddings(user)
        if result:
            profile_emb, interests_emb, expertise_emb = result
            await user_repo.update_embeddings(user.id, profile_emb, interests_emb, expertise_emb)
            print(f"  OK {name}")
            success += 1
        else:
            print(f"  FAIL {name} - embedding generation returned None")
            failed += 1

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)

    print(f"\nDone: {success} success, {failed} failed, {len(users_without)} total")


if __name__ == "__main__":
    asyncio.run(backfill())
