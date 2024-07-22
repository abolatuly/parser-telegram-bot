import logging
from src.database.models import async_session, Fragrance, Wishlist
from sqlalchemy import select
from fuzzywuzzy import process

from src.services.parsing import update_fragrances

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_fragrance_to_database():
    async with async_session() as session:
        wishlist = ['Imagination', 'Roja Elysium']

        for fragrance_name in wishlist:
            try:
                # Check if the fragrance already exists
                existing_fragrance = await session.scalar(select(Fragrance).where(Fragrance.name == fragrance_name))

                if not existing_fragrance:
                    new_fragrance = Fragrance(name=fragrance_name)
                    session.add(new_fragrance)
                    logger.info(f"Added new fragrance: {fragrance_name}")
                else:
                    logger.info(f"Fragrance already exists: {fragrance_name}")

            except Exception as e:
                logger.error(f"Error adding fragrance {fragrance_name}: {e}")
                await session.rollback()
                continue

        try:
            await session.commit()
            logger.info("Committed session")
        except Exception as e:
            logger.error(f"Error committing session: {e}")
            await session.rollback()


async def set_wishlist(tg_id):
    async with async_session() as session:
        try:
            # Check if the wishlist already exists
            wishlist = await session.scalar(select(Wishlist).where(Wishlist.telegram_id == tg_id))

            if not wishlist:
                new_wishlist = Wishlist(telegram_id=tg_id)
                session.add(new_wishlist)
                logger.info(f"Added new wishlist for user with Telegram ID: {tg_id}")
            else:
                logger.info(f"Wishlist already exists for user with Telegram ID: {tg_id}")

            await session.commit()
            logger.info("Committed session")

        except Exception as e:
            logger.error(f"Error setting wishlist for user with Telegram ID {tg_id}: {e}")
            await session.rollback()


async def get_fragrance_by_name(name):
    async with async_session() as session:
        # Get all fragrance names from the database
        fragrances = await session.execute(select(Fragrance.name))
        fragrance_names = [fragrance[0] for fragrance in fragrances.fetchall()]

        # Use fuzzy matching to find the closest match
        closest_match, score = process.extractOne(name, fragrance_names)

        if score > 80:  # You can adjust the threshold as needed
            return closest_match
        else:
            return None


async def add_fragrance_to_wishlist(telegram_id, fragrance_name):
    async with async_session() as session:
        try:
            # Retrieve the user's wishlist based on their Telegram ID
            wishlist = await session.scalar(select(Wishlist).where(Wishlist.telegram_id == telegram_id))

            # Get the fragrance
            fragrance = await session.scalar(select(Fragrance).where(Fragrance.name == fragrance_name))

            if fragrance:
                # Add the fragrance to the wishlist if it's not already there
                if fragrance not in wishlist.fragrances:
                    wishlist.fragrances.append(fragrance)
                    await session.commit()
                    logger.info(f"Added fragrance '{fragrance_name}' to wishlist for user with Telegram ID: {telegram_id}")
                    return True
                else:
                    logger.info(f"Fragrance '{fragrance_name}' is already in wishlist for user with Telegram ID: {telegram_id}")
                    return False
            else:
                logger.info(f"Fragrance '{fragrance_name}' not found in the database")
                return None

        except Exception as e:
            logger.error(f"Error adding fragrance to wishlist: {e}")
            await session.rollback()
            return False


async def get_wishlist_by_telegram_id(telegram_id):
    async with async_session() as session:
        try:
            wishlist = await session.scalar(select(Wishlist).where(Wishlist.telegram_id == telegram_id))
            return wishlist
        except Exception as e:
            logger.error(f"Error retrieving wishlist: {e}")
            return None


async def delete_fragrance_from_wishlist(telegram_id, fragrance_name):
    async with async_session() as session:
        try:
            wishlist = await session.scalar(select(Wishlist).where(Wishlist.telegram_id == telegram_id))
            if wishlist:
                logger.info("Found wishlist")
                fragrance = await session.scalar(select(Fragrance).where(Fragrance.name == fragrance_name))
                if fragrance and fragrance in wishlist.fragrances:
                    logger.info("Found fragrance in wishlist")
                    wishlist.fragrances.remove(fragrance)
                    await session.commit()
                    return True
            return False
        except Exception as e:
            logger.error(f"Error deleting fragrance from wishlist: {e}")
            await session.rollback()
            return False


async def parse_website():
    await update_fragrances()
