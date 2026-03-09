"""
Repository for bot_config table.
"""

import logging
from infrastructure.database.supabase_client import supabase, run_sync

logger = logging.getLogger(__name__)


class ConfigRepository:
    """Reads bot_config table."""

    async def get_menu_buttons(self) -> dict | None:
        """Get menu_buttons config. Returns the value dict or None."""
        try:
            @run_sync
            def _do():
                resp = supabase.table("bot_config").select("value").eq("key", "menu_buttons").execute()
                if resp.data:
                    return resp.data[0]["value"]
                return None
            return await _do()
        except Exception as e:
            # Don't spam logs if table simply doesn't exist
            err_str = str(e).lower()
            if "not found" in err_str or "does not exist" in err_str or "relation" in err_str:
                logger.debug(f"bot_config table not found, using defaults")
            else:
                logger.warning(f"Failed to read bot_config: {e}")
            return None
