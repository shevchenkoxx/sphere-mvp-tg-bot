"""
Sphere Bot - Main entry point.

Multi-platform matching bot for meaningful connections.
Currently supports Telegram, with WhatsApp and Web API planned.
"""

import asyncio
import logging
import os
import secrets
import sys
from aiohttp import web
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from adapters.telegram.loader import bot, dp, user_repo, user_service, match_repo, event_repo
from adapters.telegram.handlers import routers
from adapters.telegram.middleware import ThrottlingMiddleware
from adapters.telegram.web.stats import create_stats_app
from config.features import features

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Set DEBUG level only for our app loggers, not for noisy libraries
if features.DEBUG_MODE:
    for name in ['adapters', 'core', 'infrastructure', '__main__']:
        logging.getLogger(name).setLevel(logging.DEBUG)
    # Silence noisy HTTP debug logs
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('hpack').setLevel(logging.WARNING)

# Retry settings
MAX_RETRIES = 5
RETRY_DELAY = 10  # seconds


async def run_web_server(stats_token: str):
    """Run aiohttp stats dashboard alongside the bot."""
    port = int(os.environ.get("PORT", 8080))
    app = create_stats_app(user_repo, stats_token, bot, user_service, match_repo, event_repo)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Stats dashboard running on port {port} — /stats?token={stats_token}")


async def main():
    """Main function - starts the bot with graceful error handling."""

    # Log feature status
    logger.info("=== Sphere Bot Starting ===")
    logger.info("Feature Flags:")
    for key, value in features.to_dict().items():
        logger.info(f"  {key}: {value}")

    # Register rate limiting middleware
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    logger.info("Rate limiting middleware registered")

    # Register Telegram routers
    for router in routers:
        dp.include_router(router)

    # Start stats web server
    stats_token = os.environ.get("STATS_TOKEN", secrets.token_urlsafe(16))
    await run_web_server(stats_token)

    # Delete webhook (if exists) and start polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except TelegramUnauthorizedError:
        logger.error("Invalid bot token! Check TELEGRAM_BOT_TOKEN env var.")
        sys.exit(1)

    logger.info("Sphere Bot started!")

    retries = 0
    try:
        while retries < MAX_RETRIES:
            try:
                await dp.start_polling(bot)
                break  # Normal exit

            except TelegramConflictError:
                retries += 1
                if retries >= MAX_RETRIES:
                    logger.error(
                        "Another bot instance is running with the same token.\n"
                        "   This can happen when:\n"
                        "   - Bot is running locally AND on Railway\n"
                        "   - Multiple Railway deployments\n"
                        "   - Previous instance didn't shut down properly\n\n"
                        "   Solutions:\n"
                        "   1. Stop other instances\n"
                        "   2. Wait 1-2 minutes for Telegram to release the connection\n"
                        "   3. Regenerate bot token in @BotFather"
                    )
                    sys.exit(1)
                else:
                    logger.warning(
                        f"Conflict detected (another instance running). "
                        f"Retry {retries}/{MAX_RETRIES} in {RETRY_DELAY}s..."
                    )
                    await asyncio.sleep(RETRY_DELAY)

            except TelegramUnauthorizedError:
                logger.error("Bot token was revoked or is invalid.")
                sys.exit(1)

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                retries += 1
                if retries < MAX_RETRIES:
                    logger.info(f"Retrying in {RETRY_DELAY}s... ({retries}/{MAX_RETRIES})")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    raise
    finally:
        await bot.session.close()
        logger.info("Bot session closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except SystemExit as e:
        sys.exit(e.code)
