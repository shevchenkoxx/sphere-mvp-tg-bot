"""
Supabase client initialization.
Single point of database connection.
"""

from supabase import create_client, Client
from config.settings import settings
import asyncio
import sys
from functools import wraps

# Get Supabase credentials (support both KEY and SERVICE_KEY)
_supabase_url = settings.supabase_url
_supabase_key = settings.supabase_service_key or settings.supabase_key

if not _supabase_url or not _supabase_key:
    print("❌ ERROR: Supabase credentials not configured!")
    print("   Required env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY (or SUPABASE_KEY)")
    print(f"   SUPABASE_URL: {'set' if _supabase_url else 'MISSING'}")
    print(f"   SUPABASE_KEY: {'set' if _supabase_key else 'MISSING'}")
    sys.exit(1)

# Initialize Supabase client
supabase: Client = create_client(_supabase_url, _supabase_key)


def run_sync(func):
    """
    Decorator to run synchronous Supabase operations in async context.
    Supabase Python SDK is synchronous, so we need this wrapper.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper
