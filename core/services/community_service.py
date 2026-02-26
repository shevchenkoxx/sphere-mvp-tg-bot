"""
Community service — business logic for Telegram group communities.
Handles bot lifecycle in groups, admin sync, membership verification, and deep links.
"""

import logging
from typing import Optional, List
from uuid import UUID

from core.domain.models import Community, CommunityMember

logger = logging.getLogger(__name__)


class CommunityService:
    """Orchestrates community lifecycle and membership."""

    def __init__(self, community_repo, user_repo, bot):
        self.community_repo = community_repo
        self.user_repo = user_repo
        self.bot = bot

    async def on_bot_added_to_group(
        self, chat_id: int, chat_title: Optional[str], adder_user_id: Optional[int]
    ) -> Community:
        """Called when bot is added to a Telegram group. Creates or reactivates community."""
        existing = await self.community_repo.get_by_telegram_group_id(chat_id)
        if existing:
            if not existing.is_active:
                await self.community_repo.update_settings(existing.id, existing.settings)
                # Reactivate
                from infrastructure.database.supabase_client import supabase, run_sync
                import asyncio
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: supabase.table("communities").update({"is_active": True, "name": chat_title}).eq("id", str(existing.id)).execute())
                logger.info(f"[COMMUNITY] Reactivated community {existing.id} for group {chat_id}")
            return await self.community_repo.get_by_telegram_group_id(chat_id)

        # Find owner user (the person who added the bot)
        owner_user_id = None
        if adder_user_id:
            owner = await self.user_repo.get_by_platform_id("telegram", str(adder_user_id))
            if owner:
                owner_user_id = owner.id

        community = await self.community_repo.create(
            telegram_group_id=chat_id,
            name=chat_title,
            owner_user_id=owner_user_id,
        )
        logger.info(f"[COMMUNITY] Created community {community.id} for group {chat_id} ({chat_title})")

        # Sync TG group admins
        try:
            await self.sync_group_admins(community)
        except Exception as e:
            logger.warning(f"[COMMUNITY] Failed to sync admins for {chat_id}: {e}")

        return community

    async def on_bot_removed_from_group(self, chat_id: int) -> None:
        """Called when bot is removed from a group. Deactivates community."""
        community = await self.community_repo.get_by_telegram_group_id(chat_id)
        if community:
            await self.community_repo.deactivate(community.id)
            logger.info(f"[COMMUNITY] Deactivated community {community.id} for group {chat_id}")

    async def sync_group_admins(self, community: Community) -> None:
        """Fetch TG group admins via Bot API and sync to community_members with admin role."""
        try:
            admins = await self.bot.get_chat_administrators(community.telegram_group_id)
        except Exception as e:
            logger.warning(f"[COMMUNITY] getChatAdministrators failed for {community.telegram_group_id}: {e}")
            return

        for admin in admins:
            if admin.user.is_bot:
                continue
            # Get or create user in our DB
            user = await self.user_repo.get_by_platform_id("telegram", str(admin.user.id))
            if not user:
                from core.domain.models import MessagePlatform
                user = await self.user_repo.create(
                    platform=MessagePlatform.TELEGRAM,
                    platform_user_id=str(admin.user.id),
                    username=admin.user.username,
                    first_name=admin.user.first_name,
                )
            await self.community_repo.add_member(
                community.id, user.id, role="admin", joined_via="tg_admin_sync"
            )
            logger.info(f"[COMMUNITY] Synced admin {admin.user.id} ({admin.user.username}) for community {community.id}")

    async def verify_membership(self, user_tg_id: int, community: Community) -> bool:
        """Check if a TG user is actually in the group (even without deep link)."""
        try:
            member = await self.bot.get_chat_member(community.telegram_group_id, user_tg_id)
            return member.status in ("member", "administrator", "creator")
        except Exception as e:
            logger.warning(f"[COMMUNITY] getChatMember failed for user {user_tg_id} in {community.telegram_group_id}: {e}")
            return False

    async def auto_associate_user(self, user_id: UUID, user_tg_id: int) -> List[Community]:
        """Check all active communities and auto-add user if they're a TG group member."""
        associated = []
        communities = await self.community_repo.get_all_active()
        for community in communities:
            # Skip virtual communities (Sphere Global sentinel)
            if community.telegram_group_id == self.SPHERE_GLOBAL_TG_GROUP_ID:
                continue
            # Skip if already a member
            existing = await self.community_repo.get_member(community.id, user_id)
            if existing:
                associated.append(community)
                continue
            if await self.verify_membership(user_tg_id, community):
                await self.community_repo.add_member(
                    community.id, user_id, role="member", joined_via="auto_detected"
                )
                await self.community_repo.update_member_count(community.id)
                associated.append(community)
                logger.info(f"[COMMUNITY] Auto-associated user {user_id} with community {community.id}")
        return associated

    async def get_community_for_group(self, chat_id: int) -> Optional[Community]:
        """Get community by Telegram group chat ID."""
        return await self.community_repo.get_by_telegram_group_id(chat_id)

    def generate_deep_link(self, community_id: UUID, bot_username: str) -> str:
        """Generate deep link for community onboarding."""
        return f"https://t.me/{bot_username}?start=community_{community_id}"

    def generate_referral_deep_link(self, community_id: UUID, referrer_tg_id: int, bot_username: str) -> str:
        """Generate deep link with referral tracking."""
        return f"https://t.me/{bot_username}?start=community_{community_id}_ref_{referrer_tg_id}"

    # === SPHERE GLOBAL COMMUNITY ===

    SPHERE_GLOBAL_TG_GROUP_ID = -1  # Sentinel — not a real TG group

    async def get_or_create_global_community(self) -> Community:
        """Get or create the virtual 'Sphere Global' community."""
        existing = await self.community_repo.get_by_telegram_group_id(self.SPHERE_GLOBAL_TG_GROUP_ID)
        if existing:
            return existing

        community = await self.community_repo.create(
            telegram_group_id=self.SPHERE_GLOBAL_TG_GROUP_ID,
            name="Sphere Global",
            owner_user_id=None,
        )
        logger.info(f"[COMMUNITY] Created Sphere Global community: {community.id}")
        return community

    async def add_to_global_community(self, user_id: UUID) -> Optional[CommunityMember]:
        """Add a user to the Sphere Global community."""
        try:
            global_community = await self.get_or_create_global_community()
            existing = await self.community_repo.get_member(global_community.id, user_id)
            if existing:
                return existing

            member = await self.community_repo.add_member(
                global_community.id, user_id,
                role="member", joined_via="post_onboarding",
            )
            await self.community_repo.update_member_count(global_community.id)
            logger.info(f"[COMMUNITY] Added user {user_id} to Sphere Global")
            return member
        except Exception as e:
            logger.error(f"[COMMUNITY] Failed to add user {user_id} to global: {e}")
            return None
