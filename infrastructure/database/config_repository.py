"""
Repository for bot_config table.
"""

import logging

from infrastructure.database.supabase_client import run_sync, supabase

logger = logging.getLogger(__name__)


class ConfigRepository:
    """Reads bot_config table."""

    async def _get_config(self, key: str) -> dict | None:
        """Get a config value by key. Returns the value dict or None."""
        try:
            @run_sync
            def _do():
                resp = supabase.table("bot_config").select("value").eq("key", key).execute()
                if resp.data:
                    return resp.data[0]["value"]
                return None
            return await _do()
        except Exception as e:
            err_str = str(e).lower()
            if "not found" in err_str or "does not exist" in err_str or "relation" in err_str:
                logger.debug("bot_config table not found, using defaults")
            else:
                logger.warning(f"Failed to read bot_config[{key}]: {e}")
            return None

    async def get_menu_buttons(self) -> dict | None:
        """Get menu_buttons config."""
        return await self._get_config("menu_buttons")

    async def get_onboarding_steps(self) -> dict | None:
        """Get onboarding_steps config."""
        return await self._get_config("onboarding_steps")
