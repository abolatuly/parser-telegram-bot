import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, Chat

from config import Config, load_config
from config import config
from src.database.models import async_main
from src.handlers import handlers

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.services.parsing import update_fragrances

config.setup_logging()
logger = logging.getLogger(__name__)


def create_dummy_message(bot: Bot):
    chat = Chat(id=0, type='private')
    msg = Message(message_id=0, date=datetime.now(), chat=chat, bot=bot)

    return msg


async def main():
    logger.info("Starting bot")
    await async_main()
    config: Config = load_config()

    bot: Bot = Bot(token=config.tg_bot.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp: Dispatcher = Dispatcher()

    dp.include_router(handlers.router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_fragrances, IntervalTrigger(minutes=10),
                      args=(create_dummy_message(bot), bot))  # Pass bot and message
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
