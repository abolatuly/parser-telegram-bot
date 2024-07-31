import logging
from sqlalchemy import select, update
from fuzzywuzzy import process
from config import config
from src.database.models import async_session, Fragrance, Wishlist

config.setup_logging()
logger = logging.getLogger(__name__)


async def set_wishlist(tg_id):
    async with async_session() as session:
        try:
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
        fragrances = await session.execute(select(Fragrance.name))
        fragrance_names = [fragrance[0] for fragrance in fragrances.fetchall()]

        closest_match, score = process.extractOne(name, fragrance_names)

        if score > 80:
            return closest_match
        else:
            return None


async def add_fragrance_to_wishlist(telegram_id, fragrance_name):
    async with async_session() as session:
        try:
            wishlist = await session.scalar(select(Wishlist).where(Wishlist.telegram_id == telegram_id))
            fragrance = await session.scalar(select(Fragrance).where(Fragrance.name == fragrance_name))

            if fragrance:
                if fragrance not in wishlist.fragrances:
                    wishlist.fragrances.append(fragrance)
                    await session.commit()
                    logger.info(
                        f"Added fragrance '{fragrance_name}' to wishlist for user with Telegram ID: {telegram_id}")
                    return True
                else:
                    logger.info(
                        f"Fragrance '{fragrance_name}' is already in wishlist for user with Telegram ID: {telegram_id}")
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


async def get_all_fragrances():
    async with async_session() as session:
        try:
            result = await session.execute(select(Fragrance.name, Fragrance.is_sold_out))
            all_fragrances = result.all()
            return all_fragrances
        except Exception as e:
            logger.error(f"Error retrieving all fragrances: {e}")
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


async def get_notification_status_by_telegram_id(telegram_id):
    async with async_session() as session:
        try:
            notification_status = await session.scalar(select(Wishlist.receive_notification)
                                                       .where(Wishlist.telegram_id == telegram_id))
            return notification_status
        except Exception as e:
            logger.error(f"Error retrieving notification status: {e}")
            return None


async def toggle_notification_status_in_db(telegram_id):
    async with async_session() as session:
        try:
            current_status = await session.scalar(
                select(Wishlist.receive_notification).where(Wishlist.telegram_id == telegram_id)
            )
            new_status = not current_status
            await session.execute(
                update(Wishlist).where(Wishlist.telegram_id == telegram_id).values(receive_notification=new_status)
            )
            await session.commit()
            return new_status
        except Exception as e:
            logger.error(f"Error toggling notification status: {e}")
            await session.rollback()
            return None


async def get_users_by_fragrance(fragrance):
    async with async_session() as session:
        try:
            users = await session.execute(
                select(Wishlist.telegram_id)
                .join(Wishlist.fragrances)
                .where(Fragrance.id == fragrance.id)
                .where(Wishlist.receive_notification == True)
            )
            users = [row[0] for row in users.all()]
            return users
        except Exception as e:
            logger.error(f"Error retrieving notification status: {e}")
            return None


async def get_all_wishlists():
    async with async_session() as session:
        try:
            users = await session.execute(
                select(Wishlist.telegram_id).where(Wishlist.receive_notification == True)
            )
            users = [row[0] for row in users.all()]
            return users
        except Exception as e:
            logger.error(f"Error retrieving users with notifications: {e}")
            return None


async def get_all_users():
    async with async_session() as session:
        try:
            result = await session.execute(select(Wishlist.telegram_id))
            all_users = [row[0] for row in result.all()]
            return all_users
        except Exception as e:
            logger.error(f"Error retrieving all users: {e}")
            return []