"""
Test matching pipeline end-to-end.
Picks a user and runs vector matching to verify everything works.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import UUID
from infrastructure.database.supabase_client import supabase
from infrastructure.database.user_repository import SupabaseUserRepository
from infrastructure.database.match_repository import SupabaseMatchRepository
from infrastructure.database.event_repository import SupabaseEventRepository
from infrastructure.ai.openai_service import OpenAIService
from core.services.matching_service import MatchingService


async def test():
    # Init services
    user_repo = SupabaseUserRepository()
    match_repo = SupabaseMatchRepository()
    event_repo = SupabaseEventRepository()
    ai_service = OpenAIService()
    matching = MatchingService(match_repo, event_repo, ai_service)

    # Get TEST2024 event
    event = await event_repo.get_by_code("TEST2024")
    if not event:
        print("ERROR: TEST2024 event not found!")
        return

    print(f"Event: {event.name} (ID: {event.id})")

    # Get participants
    participants = await event_repo.get_participants(event.id)
    print(f"Participants: {len(participants)}")

    if len(participants) < 2:
        print("Not enough participants for matching")
        return

    # Pick first user for testing
    test_user = participants[0]
    print(f"\nTest user: {test_user.display_name}")
    print(f"  Bio: {(test_user.bio or '')[:100]}")
    print(f"  Has embeddings: {test_user.profile_embedding is not None}")

    # Test 1: Vector candidate search
    print("\n--- Test 1: Vector Candidate Search ---")
    try:
        candidates = await matching.find_vector_candidates(test_user, event.id, limit=5)
        print(f"Found {len(candidates)} vector candidates:")
        for user, score in candidates:
            print(f"  {user.display_name}: similarity={score:.3f}")
    except Exception as e:
        print(f"FAILED: {e}")

    # Test 2: Full matching pipeline (creates 1 match)
    print("\n--- Test 2: Full Matching Pipeline ---")
    try:
        matches = await matching.find_matches_vector(
            user=test_user,
            event_id=event.id,
            limit=2
        )
        print(f"Created {len(matches)} matches:")
        for matched_user, result in matches:
            print(f"  {matched_user.display_name}")
            print(f"    Score: {result.compatibility_score:.2f}")
            print(f"    Type: {result.match_type}")
            print(f"    Why: {result.explanation[:100]}")
            print(f"    Ice: {result.icebreaker[:80]}")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n--- Summary ---")
    total_matches = supabase.table("matches").select("id", count="exact").execute()
    print(f"Total matches in DB: {total_matches.count}")


if __name__ == "__main__":
    asyncio.run(test())
