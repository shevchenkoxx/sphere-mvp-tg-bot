"""
Supabase client initialization.
Single point of database connection.
"""

from supabase import create_client, Client
import asyncio
import concurrent.futures
import sys
import os
from functools import wraps

# Get Supabase credentials directly from env (bypass pydantic for reliability)
_supabase_url = os.environ.get("SUPABASE_URL", "")
_supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

if not _supabase_url or not _supabase_key:
    print("❌ ERROR: Supabase credentials not configured!")
    print("   Required env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY (or SUPABASE_KEY)")
    print(f"   SUPABASE_URL: {'set' if _supabase_url else 'MISSING'}")
    print(f"   SUPABASE_KEY: {'set' if _supabase_key else 'MISSING'}")
    print(f"   Hint: check your .env or Railway variables")
    sys.exit(1)

# Schema isolation: staging uses v1_1, production uses public
_schema = os.environ.get("DB_SCHEMA", "public")

# Initialize Supabase client with schema option
if _schema != "public":
    from supabase.lib.client_options import ClientOptions
    supabase: Client = create_client(
        _supabase_url, _supabase_key,
        options=ClientOptions(schema=_schema)
    )
else:
    supabase: Client = create_client(_supabase_url, _supabase_key)


# Dedicated bounded thread pool for DB operations — prevents exhausting the
# default executor when many Supabase calls run concurrently.
_db_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=10,
    thread_name_prefix="supabase-db",
)


def run_sync(func):
    """
    Decorator to run synchronous Supabase operations in async context.
    Supabase Python SDK is synchronous, so we need this wrapper.
    Uses a dedicated bounded thread pool instead of the default executor.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_db_executor, lambda: func(*args, **kwargs))
    return wrapper
