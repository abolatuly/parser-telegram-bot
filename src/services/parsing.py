import aiohttp
from bs4 import BeautifulSoup
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from src.database.models import Fragrance, engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONTAGNE_URL = "https://www.montagneparfums.com/fragrance"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 "
                  "Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
              "application/signed-exchange;v=b3;q=0.9",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8"
}

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def update_fragrances():
    """Check the availability of products and update the database."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(MONTAGNE_URL, headers=HEADERS) as response:
                response.raise_for_status()  # Raise an error for bad responses
                html = await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching the product page: {e}")
            return

        soup = BeautifulSoup(html, "lxml")
        products = soup.findAll("div", class_="ProductList-item")

        async with async_session() as db_session:
            for product in products:
                product_name = product.find('h1').text.strip() if product.find('h1') else None

                if product_name:
                    product_name_upper = product_name.upper()
                    sold_out_marker = product.find('div', class_='product-mark sold-out')

                    # Check if the fragrance already exists in the database
                    fragrance = await db_session.scalar(select(Fragrance).where(Fragrance.name == product_name_upper))

                    if fragrance:
                        # Update the existing fragrance
                        if fragrance.is_sold_out != bool(sold_out_marker):
                            fragrance.is_sold_out = bool(sold_out_marker)
                            logger.info(f"Updated fragrance {product_name_upper}: is_sold_out={bool(sold_out_marker)}")
                    else:
                        # Create a new fragrance
                        fragrance = Fragrance(name=product_name_upper, is_sold_out=bool(sold_out_marker))
                        db_session.add(fragrance)
                        logger.info(f"Added new fragrance {product_name_upper}: is_sold_out={bool(sold_out_marker)}")

            await db_session.commit()
            logger.info("Database update completed.")
