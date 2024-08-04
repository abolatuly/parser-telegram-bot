import asyncio
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot
from aiogram.types import Message
from bs4 import BeautifulSoup
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from src.database.models import Fragrance, engine
from config import config
from src.handlers.handlers import redis_client

config.setup_logging()
logger = logging.getLogger(__name__)
logger_new_fragrance = logging.getLogger("new_fragrance")
new_fragrance_handler = RotatingFileHandler(os.path.join('logs', 'new_fragrance.log'), maxBytes=1024 * 1024, backupCount=5)
new_fragrance_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger_new_fragrance.addHandler(new_fragrance_handler)

MONTAGNE_URL = "https://www.montagneparfums.com/fragrance"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 "
                  "Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
              "application/signed-exchange;v=b3;q=0.9",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8"
}

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def update_fragrances(message: Message, bot: Bot):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(MONTAGNE_URL, headers=HEADERS) as response:
                response.raise_for_status()
                html = await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching the product page: {e}")
            return

        soup = BeautifulSoup(html, "lxml")
        products = soup.findAll("div", class_="ProductList-item")

        async with async_session() as db_session:
            for product in products:
                product_name = product.find('h1').text.strip() if product.find('h1') else None
                product_image_link = product.find('img')['data-src']

                if product_name:
                    product_name_upper = product_name.upper()
                    sold_out_marker = product.find('div', class_='product-mark sold-out')

                    fragrance = await db_session.scalar(select(Fragrance).where(Fragrance.name == product_name_upper))

                    if fragrance:
                        if fragrance.is_sold_out != bool(sold_out_marker):
                            fragrance.is_sold_out = bool(sold_out_marker)
                            fragrance.parsed_datetime = datetime.now(ZoneInfo('Asia/Almaty'))
                            logger_new_fragrance.info(
                                f"Updated fragrance {product_name_upper}: is_sold_out={bool(sold_out_marker)}, "
                                f"parsed_datetime={fragrance.parsed_datetime}")

                            # Retrieve the admin prioritize status
                            is_admin_prioritize = await redis_client.get("is_admin_prioritize")
                            from src.handlers.handlers import send_notification
                            if is_admin_prioritize.decode() == "True":
                                # Notify admin immediately
                                await send_notification(bot, fragrance, priority_queue=True)
                                # Notify other users 5 minutes later
                                await asyncio.sleep(300)  # 5 minutes
                                await send_notification(bot, fragrance, second_try=True)
                            else:
                                await send_notification(bot, fragrance)

                    else:
                        fragrance = Fragrance(name=product_name_upper, is_sold_out=bool(sold_out_marker),
                                              image_url=product_image_link,
                                              parsed_datetime=datetime.now(ZoneInfo('Asia/Almaty')))
                        db_session.add(fragrance)
                        logger_new_fragrance.info(
                            f"Added new fragrance {product_name_upper}: is_sold_out={bool(sold_out_marker)}, "
                            f"parsed_datetime={fragrance.parsed_datetime}")

                        # Notify users if the new fragrance has been added
                        from src.handlers.handlers import send_notification_new_fragrance
                        await send_notification_new_fragrance(bot, fragrance)

            await db_session.commit()
            logger.info("Database update completed.")
