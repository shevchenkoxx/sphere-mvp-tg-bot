"""
Supabase client initialization.
Single point of database connection.
"""

from supabase import create_client, Client
from config.settings import settings
import asyncio
from functools import wraps

# Initialize Supabase client
supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_key
)


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
