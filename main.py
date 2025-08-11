import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from cachetools import TTLCache

import config
from app.db import init_database
from app.handlers.admin import admin_router
from app.handlers.user import user_router
from app.scheduler import setup_scheduler


async def on_startup(bot: Bot, scheduler: AsyncIOScheduler):
    """Function to run on bot startup."""
    await setup_scheduler(bot, scheduler)
    scheduler.start()
    logging.info("Scheduler started.")
    
    logging.info("Bot Started.")
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "✅ Bot has been started/restarted successfully!")
        except Exception as e:
            logging.error(f"Could not notify admin {admin_id}: {e}")


async def on_shutdown(scheduler: AsyncIOScheduler):
    """Function to run on bot shutdown."""
    if scheduler.running:
        scheduler.shutdown()
    logging.info("Scheduler stopped.")
    logging.info("Bot Stopped.")


async def main():
    """Main function to initialize and run the bot."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )

    # Initialize database before anything else
    await init_database()

    # Initialize bot, dispatcher, and scheduler
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    scheduler = AsyncIOScheduler()

    # Create a TTLCache for analysis results
    analysis_cache = TTLCache(maxsize=100, ttl=300)
    
    # Make dependencies available to handlers
    dp['scheduler'] = scheduler
    dp['analysis_cache'] = analysis_cache
    dp['bot'] = bot

    # Register startup and shutdown handlers
    dp.startup.register(lambda: on_startup(bot, scheduler))
    dp.shutdown.register(lambda: on_shutdown(scheduler))

    # Include routers
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Start polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped manually.")
