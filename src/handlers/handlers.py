import asyncio
import logging
from os import getenv

from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

import src.keyboards.keyboards as kb
from config import config
from src.database import requests
from src.database.requests import (
    get_fragrance_by_name, add_fragrance_to_wishlist, get_wishlist_by_telegram_id,
    delete_fragrance_from_wishlist, get_notification_status_by_telegram_id,
    toggle_notification_status_in_db, get_users_by_fragrance, get_all_wishlists
)
from src.states.states import AddToWishlist

TELEGRAM_MESSAGE_LIMIT = 4096

config.setup_logging()
logger = logging.getLogger(__name__)

router: Router = Router()


@router.message(CommandStart())
async def process_any_message(message: Message):
    if str(message.from_user.id) == getenv("ADMIN_ID"):
        await requests.set_wishlist(tg_id=message.from_user.id)
        await message.answer(text="Welcome to Montagne Parfums fragrance tracker!",
                             reply_markup=kb.get_main_keyboard())


@router.message(F.text == "◀️ Back to menu")
async def menu(message: Message, state: FSMContext):
    if str(message.from_user.id) == getenv("ADMIN_ID"):
        await state.clear()
        await message.answer(text="Main menu", reply_markup=kb.get_main_keyboard())


@router.message(F.text == "📄 Wishlist")
async def show_wishlist(message: Message):
    if str(message.from_user.id) == getenv("ADMIN_ID"):
        try:
            telegram_id = message.from_user.id
            wishlist = await get_wishlist_by_telegram_id(telegram_id)

            if not wishlist or not wishlist.fragrances:
                await message.answer("Your wishlist is empty.")
            else:
                for fragrance in wishlist.fragrances:
                    status_symbol = '✅' if not fragrance.is_sold_out else '❌'
                    delete_from_wishlist = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(
                                text="Delete",
                                callback_data=f"_{fragrance.name[:60] if len(fragrance.name) > 60 else fragrance.name}")]])
                    await message.answer(text=f"{status_symbol} {fragrance.name.title()}",
                                         reply_markup=delete_from_wishlist)

            await message.answer(text="If you want to add a new fragrance, press \"Add fragrance to wishlist\" below",
                                 reply_markup=kb.add_to_wishlist)

        except Exception as e:
            logger.error(f"Error showing wishlist: {e}")
            await message.answer("An error occurred while showing your wishlist. Please try again later.")


@router.message(F.text == "➕ Add fragrance to wishlist")
async def type_fragrance(message: Message, state: FSMContext):
    if str(message.from_user.id) == getenv("ADMIN_ID"):
        await state.set_state(AddToWishlist.adding)
        await message.answer(text="Type the name of a fragrance you want to add")


@router.message(AddToWishlist.adding)
async def add_to_wishlist(message: Message, state: FSMContext):
    if str(message.from_user.id) == getenv("ADMIN_ID"):
        try:
            telegram_id = message.from_user.id
            fragrance_name = await get_fragrance_by_name(message.text)

            if fragrance_name:
                result = await add_fragrance_to_wishlist(telegram_id, fragrance_name)

                if result:
                    await message.answer(f"{fragrance_name.title()} was added to your wishlist!", reply_markup=kb.add_more)
                else:
                    await message.answer(f"{fragrance_name.title()} is already in your wishlist!", reply_markup=kb.add_more)
                await state.clear()
            else:
                await message.answer("Sorry, we couldn't find a matching fragrance. "
                                     "Please try again with a different name.")
        except Exception as e:
            logger.error(f"Error in add_to_wishlist handler: {e}")
            await message.answer("An error occurred while processing your request. Please try again later.")


@router.callback_query(F.data == "add_more")
async def add_more(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddToWishlist.adding)
    await callback.message.answer(text="Type the name of a fragrance you want to add")


@router.callback_query(F.data.startswith("_"))
async def delete(callback: CallbackQuery):
    try:
        fragrance_name = await get_fragrance_by_name(callback.data.split("_")[1])
        telegram_id = callback.from_user.id

        result = await delete_fragrance_from_wishlist(telegram_id, fragrance_name)
        if result:
            await callback.answer()
            await callback.message.answer(text=f"Deleted: {fragrance_name.title()}")
        else:
            await callback.answer(text="Item not found in wishlist", show_alert=True)

    except Exception as e:
        logger.error(f"Error in delete handler: {e}")
        await callback.answer(text="An error occurred while deleting the fragrance", show_alert=True)


@router.message(F.text == "🔍 Fragrances")
async def all_fragrances(message: Message):
    if str(message.from_user.id) == getenv("ADMIN_ID"):
        try:
            fragrances = await requests.get_all_fragrances()

            current_message = ""
            max_length = 4096

            for name, is_sold_out in fragrances:
                status_symbol = '✅' if not is_sold_out else '❌'
                fragrance_entry = f"{status_symbol} {name.title()}\n"

                if len(current_message) + len(fragrance_entry) > max_length:
                    if current_message:
                        await message.answer(current_message.strip())
                        current_message = ""

                current_message += fragrance_entry

            if current_message:
                await message.answer(current_message.strip())
            else:
                await message.answer("List of fragrances is empty.")
        except Exception as e:
            logger.error(f"Error showing all fragrances: {e}")
            await message.answer("An error occurred while showing all fragrances. Please try again later.")


@router.message(F.text == "⚙️ Settings")
async def settings(message: Message):
    user_id = message.from_user.id

    if str(user_id) == getenv("ADMIN_ID"):
        try:
            notification_status = await get_notification_status_by_telegram_id(user_id)

            if notification_status is not None:
                status_text = "On" if notification_status else "Off"
                notification_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=f"Receive Notification: {status_text}",
                                                           callback_data="toggle_notification_status")]]
                )
                await message.answer(text="Your notification status:", reply_markup=notification_keyboard)

            else:
                await message.answer("Could not retrieve your notification status. Please try again later.")
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            await message.answer("An error occurred while showing your settings. Please try again later.")


@router.callback_query(F.data == "toggle_notification_status")
async def toggle_notification_status(callback_query: CallbackQuery):
    try:
        telegram_id = callback_query.from_user.id
        new_status = await toggle_notification_status_in_db(telegram_id)

        if new_status is not None:
            status_text = "On" if new_status else "Off"
            status_markup = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=f"Receive Notification: {status_text}",
                                                       callback_data="toggle_notification_status")]])
            await callback_query.message.edit_text(text="Your notification status:", reply_markup=status_markup)
        else:
            await callback_query.message.answer("Could not update your notification status. Please try again later.")
    except Exception as e:
        logger.error(f"Error toggling notification status: {e}")
        await callback_query.message.answer("An error occurred while updating your notification status. "
                                            "Please try again later.")


async def send_notification(bot: Bot, fragrance):
    try:
        users = await get_users_by_fragrance(fragrance)

        async def send_batch(batch, retries=3):
            for attempt in range(retries):
                tasks = [bot.send_photo(
                    chat_id=user_id,
                    photo=fragrance.image_url,
                    caption=f"The fragrance {fragrance.name} is now available!"
                ) for user_id in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                failed_users = []
                for user_id, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.error(f"Attempt {attempt + 1} failed for user {user_id}: {result}")
                        failed_users.append(user_id)

                if not failed_users:
                    break

                batch = failed_users
            else:
                for user_id in batch:
                    logger.error(f"Failed to send notification to user {user_id} after {retries} attempts")

        batch_size = 50
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            await send_batch(batch)
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error sending notification: {e}")


async def send_notification_new_fragrance(bot: Bot, fragrance):
    try:
        users = await get_all_wishlists()

        async def send_batch(batch, retries=3):
            for attempt in range(retries):
                tasks = [bot.send_photo(
                    chat_id=user_id,
                    photo=fragrance.image_url,
                    caption=f"New fragrance is at the store! Check out {fragrance.name}!"
                ) for user_id in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                failed_users = []
                for user_id, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.error(f"Attempt {attempt + 1} failed for user {user_id}: {result}")
                        failed_users.append(user_id)

                if not failed_users:
                    break

                batch = failed_users
            else:
                for user_id in batch:
                    logger.error(f"Failed to send notification to user {user_id} after {retries} attempts")

        batch_size = 50
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            await send_batch(batch)
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error sending notification: {e}")
