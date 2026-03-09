#!/usr/bin/env python3
"""
Script to manually create matches for a user via OpenAI.
Run: python scripts/create_matches.py <telegram_user_id>
"""

import asyncio
import os
import sys

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env
from dotenv import load_dotenv

load_dotenv()

from adapters.telegram.loader import event_service, matching_service, user_service
from core.domain.models import MessagePlatform


async def create_matches_for_user(telegram_user_id: str):
    """Create matches for a user"""
    print(f"🔍 Looking up user {telegram_user_id}...")

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        telegram_user_id
    )

    if not user:
        print("❌ User not found")
        return

    print(f"✅ Found user: {user.display_name}")
    print(f"   Interests: {user.interests}")
    print(f"   Goals: {user.goals}")
    print(f"   Current event: {user.current_event_id}")

    if not user.current_event_id:
        print("❌ User has no current_event_id")
        return

    # Get event
    event = await event_service.get_event_by_id(user.current_event_id)
    if not event:
        print("❌ Event not found")
        return

    print(f"✅ Event: {event.name} ({event.code})")

    # Create matches
    print("\n🤖 Creating matches via OpenAI...")

    try:
        matches = await matching_service.find_and_create_matches_for_user(
            user=user,
            event_id=event.id,
            limit=5
        )

        if not matches:
            print("❌ No matches created (maybe threshold too high or no compatible users)")
            return

        print(f"\n✅ Created {len(matches)} matches:\n")

        for i, (matched_user, match_result) in enumerate(matches, 1):
            print(f"{i}. {matched_user.display_name}")
            print(f"   Score: {match_result.compatibility_score:.2f}")
            print(f"   Type: {match_result.match_type}")
            print(f"   Why: {match_result.explanation[:100]}...")
            print(f"   Icebreaker: {match_result.icebreaker}")
            print()

    except Exception as e:
        print(f"❌ Error creating matches: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_matches.py <telegram_user_id>")
        print("Example: python scripts/create_matches.py 44420077")
        sys.exit(1)

    telegram_user_id = sys.argv[1]
    asyncio.run(create_matches_for_user(telegram_user_id))
