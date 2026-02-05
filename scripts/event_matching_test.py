#!/usr/bin/env python3
"""
Event Matching Test - Simplified matching for events.
Runs every 20 minutes, sends notifications to admin.

Run: python3 scripts/event_matching_test.py
Stop: pkill -f event_matching_test
"""

import asyncio
import os
import sys
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables - require them to be set
# Run with: export $(cat .env | xargs) && python3 scripts/event_matching_test.py
required_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'OPENAI_API_KEY', 'TELEGRAM_BOT_TOKEN']
missing = [v for v in required_vars if not os.environ.get(v)]
if missing:
    print(f"ERROR: Missing environment variables: {', '.join(missing)}")
    print("Set them or run: export $(cat .env | xargs) && python3 scripts/event_matching_test.py")
    sys.exit(1)

os.environ.setdefault('DEFAULT_MATCH_THRESHOLD', '0.3')  # Low threshold for testing

BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
ADMIN_CHAT_ID = int(os.environ.get('ADMIN_CHAT_ID', '44420077'))
EVENT_ID = UUID("bd4817db-aac2-41a2-836c-2e4fd2fed944")  # POSTSW24
INTERVAL_MINUTES = 20
END_TIME = datetime.now().replace(hour=23, minute=59, second=59)

LOG_FILE = project_root / "event_matching.log"


def log(msg):
    """Log to file and stdout"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


async def send_admin_notification(text: str):
    """Send notification to admin via Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json={
                "chat_id": ADMIN_CHAT_ID,
                "text": text,
                "parse_mode": "HTML"
            })
        log(f"  📤 Admin notified")
    except Exception as e:
        log(f"  ⚠️ Failed to notify admin: {e}")


async def simple_match_users(user_a, user_b, event_name: str) -> dict:
    """
    Simple matching using OpenAI - no complex pre-filtering.
    Returns match result or None.
    """
    from openai import AsyncOpenAI
    import json
    import re

    client = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'])

    # Build simple profiles
    profile_a = f"""
Name: {user_a.display_name or user_a.first_name}
Bio: {user_a.bio or 'N/A'}
Looking for: {user_a.looking_for or 'N/A'}
Can help: {user_a.can_help_with or 'N/A'}
Interests: {', '.join(user_a.interests or [])}
"""

    profile_b = f"""
Name: {user_b.display_name or user_b.first_name}
Bio: {user_b.bio or 'N/A'}
Looking for: {user_b.looking_for or 'N/A'}
Can help: {user_b.can_help_with or 'N/A'}
Interests: {', '.join(user_b.interests or [])}
"""

    prompt = f"""Match these two people at "{event_name}" event.

PERSON A:
{profile_a}

PERSON B:
{profile_b}

Score 0.0-1.0 based on:
- Can A help B with what B is looking for? (+0.3)
- Can B help A with what A is looking for? (+0.3)
- Shared interests? (+0.2)
- General networking value? (+0.2)

Return JSON only:
{{"score": 0.0-1.0, "explanation": "Why match in Russian, 1-2 sentences", "icebreaker": "Conversation starter in Russian"}}
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)

        return json.loads(text)
    except Exception as e:
        log(f"    ❌ LLM error: {e}")
        return None


async def run_event_matching():
    """Run simplified matching for POSTSW24 event"""
    from infrastructure.database.supabase_client import supabase
    from infrastructure.database.event_repository import SupabaseEventRepository
    from infrastructure.database.match_repository import SupabaseMatchRepository
    from infrastructure.database.user_repository import SupabaseUserRepository
    from infrastructure.ai.embedding_service import EmbeddingService

    event_repo = SupabaseEventRepository()
    match_repo = SupabaseMatchRepository()
    user_repo = SupabaseUserRepository()
    embedding_service = EmbeddingService()

    # Get event
    event = await event_repo.get_by_id(EVENT_ID)
    event_name = event.name if event else "Post Software"

    # Get participants
    participants = await event_repo.get_participants(EVENT_ID)
    log(f"  👥 Participants: {len(participants)}")

    if len(participants) < 2:
        log("  ⏭️ Not enough participants")
        return 0

    # Generate missing embeddings
    for user in participants:
        if user.profile_embedding is None:
            log(f"  📊 Generating embeddings for {user.display_name}...")
            try:
                result = await embedding_service.generate_embeddings(user)
                if result:
                    await user_repo.update_embeddings(user.id, *result)
                    log(f"    ✅ Done")
            except Exception as e:
                log(f"    ⚠️ Failed: {e}")

    # Match all pairs
    new_matches = []
    for i, user_a in enumerate(participants):
        for user_b in participants[i+1:]:
            # Check if match exists
            if await match_repo.exists(EVENT_ID, user_a.id, user_b.id):
                continue

            log(f"  🔍 Matching: {user_a.display_name} <-> {user_b.display_name}")

            # Get match result from LLM
            result = await simple_match_users(user_a, user_b, event_name)

            if not result:
                continue

            score = result.get('score', 0)
            log(f"    Score: {score}")

            # Create match if score >= 0.3 (low threshold for testing)
            if score >= 0.3:
                try:
                    match_data = {
                        "event_id": str(EVENT_ID),
                        "user_a_id": str(user_a.id),
                        "user_b_id": str(user_b.id),
                        "compatibility_score": score,
                        "match_type": "professional",
                        "ai_explanation": result.get('explanation', ''),
                        "icebreaker": result.get('icebreaker', ''),
                        "status": "pending"
                    }

                    supabase.table("matches").insert(match_data).execute()

                    new_matches.append({
                        "user_a": user_a.display_name,
                        "user_b": user_b.display_name,
                        "score": score,
                        "explanation": result.get('explanation', '')
                    })
                    log(f"    ✅ Match created!")
                except Exception as e:
                    log(f"    ❌ DB error: {e}")

    return new_matches


async def main():
    log("🚀 Event Matching Test started for POSTSW24")
    log(f"⏰ Running every {INTERVAL_MINUTES} min until {END_TIME.strftime('%H:%M')}")
    log("-" * 50)

    # Notify admin on start
    await send_admin_notification(
        "🚀 <b>Event Matching Started</b>\n\n"
        f"Event: POSTSW24\n"
        f"Interval: {INTERVAL_MINUTES} min\n"
        f"Until: {END_TIME.strftime('%H:%M')}"
    )

    iteration = 0
    while datetime.now() < END_TIME:
        iteration += 1
        log(f"🔄 Iteration #{iteration}")

        try:
            new_matches = await run_event_matching()

            if new_matches:
                log(f"  ✅ Created {len(new_matches)} new matches!")

                # Notify admin about new matches
                match_text = "\n".join([
                    f"• {m['user_a']} ↔ {m['user_b']} ({m['score']:.2f})"
                    for m in new_matches
                ])
                await send_admin_notification(
                    f"🎯 <b>New Matches Created!</b>\n\n{match_text}"
                )
            else:
                log(f"  ℹ️ No new matches")

        except Exception as e:
            log(f"  ❌ Error: {e}")
            await send_admin_notification(f"⚠️ Matching error: {str(e)[:100]}")

        # Next run
        next_run = datetime.now() + timedelta(minutes=INTERVAL_MINUTES)
        if next_run > END_TIME:
            break

        log(f"  ⏳ Next: {next_run.strftime('%H:%M:%S')}")
        await asyncio.sleep(INTERVAL_MINUTES * 60)

    log("🏁 Event Matching Test completed!")
    await send_admin_notification("🏁 Event Matching completed for today")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("⛔ Stopped by user")
