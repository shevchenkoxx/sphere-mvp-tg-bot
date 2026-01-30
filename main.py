"""
Sphere Bot - Main entry point.

Multi-platform matching bot for meaningful connections.
Currently supports Telegram, with WhatsApp and Web API planned.
"""

import asyncio
import logging
from adapters.telegram.loader import bot, dp
from adapters.telegram.handlers import routers
from config.features import features

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if features.DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function - starts the bot."""

    # Log feature status
    logger.info("=== Feature Flags ===")
    for key, value in features.to_dict().items():
        logger.info(f"  {key}: {value}")

    # Register Telegram routers
    for router in routers:
        dp.include_router(router)

    # Delete webhook (if exists) and start polling
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Sphere Bot started!")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
