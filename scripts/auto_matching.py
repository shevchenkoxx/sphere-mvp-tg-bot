#!/usr/bin/env python3
"""
Auto-matching script - runs matching for POSTSW24 event every 20 minutes.
Run with: python3 scripts/auto_matching.py
Stop with: Ctrl+C or: pkill -f auto_matching
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Log file
LOG_FILE = project_root / "auto_matching.log"

def log(msg):
    """Write to both stdout and log file"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# Load environment variables from .env or require them to be set
# Run with: export $(cat .env | xargs) && python3 scripts/auto_matching.py
required_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY']
missing = [v for v in required_vars if not os.environ.get(v)]
if missing:
    print(f"ERROR: Missing environment variables: {', '.join(missing)}")
    print("Set them or run: export $(cat .env | xargs) && python3 scripts/auto_matching.py")
    sys.exit(1)

os.environ.setdefault('DEFAULT_MATCH_THRESHOLD', '0.5')

from uuid import UUID
from core.services.matching_service import MatchingService
from infrastructure.database.match_repository import SupabaseMatchRepository
from infrastructure.database.event_repository import SupabaseEventRepository
from infrastructure.database.user_repository import SupabaseUserRepository
from infrastructure.ai.openai_service import OpenAIService
from infrastructure.ai.embedding_service import EmbeddingService

# POSTSW24 event ID
EVENT_ID = UUID("bd4817db-aac2-41a2-836c-2e4fd2fed944")
INTERVAL_MINUTES = 20
END_TIME = datetime.now().replace(hour=23, minute=59, second=59)


async def generate_missing_embeddings():
    """Generate embeddings for users who don't have them"""
    user_repo = SupabaseUserRepository()
    event_repo = SupabaseEventRepository()
    embedding_service = EmbeddingService()

    participants = await event_repo.get_participants(EVENT_ID)

    for user in participants:
        if user.profile_embedding is None:
            log(f"  📊 Generating embeddings for {user.display_name}...")
            try:
                result = await embedding_service.generate_embeddings(user)
                if result:
                    profile_emb, interests_emb, expertise_emb = result
                    await user_repo.update_embeddings(
                        user.id,
                        profile_embedding=profile_emb,
                        interests_embedding=interests_emb,
                        expertise_embedding=expertise_emb
                    )
                    log(f"  ✅ Embeddings saved for {user.display_name}")
            except Exception as e:
                log(f"  ❌ Failed to generate embeddings for {user.display_name}: {e}")


async def run_matching():
    """Run matching for POSTSW24 event"""
    match_repo = SupabaseMatchRepository()
    event_repo = SupabaseEventRepository()
    ai_service = OpenAIService()
    matching_service = MatchingService(match_repo, event_repo, ai_service)

    # Get participant count
    participants = await event_repo.get_participants(EVENT_ID)
    log(f"  👥 Participants: {len(participants)}")

    if len(participants) < 2:
        log("  ⏭️ Not enough participants, skipping")
        return 0

    # Generate missing embeddings first
    await generate_missing_embeddings()

    # Run matching
    count = await matching_service.create_matches_for_event(EVENT_ID)
    return count


async def main():
    log("🚀 Auto-matching started for POSTSW24")
    log(f"⏰ Running every {INTERVAL_MINUTES} minutes until {END_TIME.strftime('%H:%M')}")
    log("-" * 50)

    iteration = 0
    while datetime.now() < END_TIME:
        iteration += 1
        log(f"🔄 Iteration #{iteration}")

        try:
            count = await run_matching()
            log(f"  ✅ Created {count} new matches")
        except Exception as e:
            log(f"  ❌ Error: {e}")

        # Calculate next run time
        next_run = datetime.now() + timedelta(minutes=INTERVAL_MINUTES)
        if next_run > END_TIME:
            log("🏁 End time reached. Stopping.")
            break

        log(f"  ⏳ Next run at {next_run.strftime('%H:%M:%S')}")

        # Sleep until next run
        await asyncio.sleep(INTERVAL_MINUTES * 60)

    log("✅ Auto-matching completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("⛔ Stopped by user")
