import asyncio
import logging
import time

import redis.asyncio as redis
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

import src.keyboards.keyboards as kb
from config import config
from config.base import getenv
from src.database import requests
from src.database.requests import (
    get_fragrance_by_name, add_fragrance_to_wishlist, get_wishlist_by_telegram_id,
    delete_fragrance_from_wishlist, get_notification_status_by_telegram_id,
    toggle_notification_status_in_db, get_users_by_fragrance, get_all_wishlists, get_all_users
)
from src.states.states import AddToWishlist, AdminMessage

TELEGRAM_MESSAGE_LIMIT = 4096

config.setup_logging()
logger = logging.getLogger(__name__)

router: Router = Router()
redis_client = redis.Redis(host='localhost', port=6381, db=0)

COOLDOWN_PERIOD = 3  # Cooldown period in seconds


def cooldown_key(user_id, action):
    return f"cooldown_{action}_{user_id}"


async def check_cooldown(user_id, action):
    last_interaction_time = await redis_client.get(cooldown_key(user_id, action))
    current_time = time.time()
    if last_interaction_time is not None and (current_time - float(last_interaction_time)) < COOLDOWN_PERIOD:
        return True
    await redis_client.set(cooldown_key(user_id, action), current_time)
    return False


@router.message(CommandStart())
async def process_any_message(message: Message):
    is_admin = str(message.from_user.id) == getenv("ADMIN_USER_ID")
    await requests.set_wishlist(tg_id=message.from_user.id)
    await message.answer(text="Welcome to Montagne Parfums fragrance tracker!",
                         reply_markup=kb.get_main_keyboard(is_admin))


@router.message(F.text == "◀️ Back to menu")
async def menu(message: Message, state: FSMContext):
    await state.clear()
    is_admin = str(message.from_user.id) == getenv("ADMIN_USER_ID")
    await message.answer(text="Main menu", reply_markup=kb.get_main_keyboard(is_admin))


@router.message(F.text == "📄 Wishlist")
async def show_wishlist(message: Message):
    user_id = message.from_user.id
    if await check_cooldown(user_id, "wishlist"):
        await message.answer("Please wait before requesting the wishlist again.")
        return

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
    user_id = message.from_user.id
    if await check_cooldown(user_id, "add_wishlist"):
        await message.answer("Please wait before requesting again.")
        return

    await state.set_state(AddToWishlist.adding)
    await message.answer(text="Type the name of a fragrance you want to add")


@router.message(AddToWishlist.adding)
async def add_to_wishlist(message: Message, state: FSMContext):
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
    user_id = message.from_user.id
    if await check_cooldown(user_id, "fragrances"):
        await message.answer("Please wait before requesting the list of fragrances again.")
        return

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
    is_admin = str(user_id) == getenv("ADMIN_USER_ID")

    if await check_cooldown(user_id, "settings"):
        await message.answer("Please wait before requesting the settings again.")
        return

    try:
        notification_status = await get_notification_status_by_telegram_id(user_id)
        admin_prioritize_status = await redis_client.get("is_admin_prioritize")
        admin_prioritize_status = admin_prioritize_status.decode()

        # Default to 'False' if the value is not set
        if admin_prioritize_status not in ["True", "False"]:
            admin_prioritize_status = "False"

        if notification_status is not None:
            status_text = "On" if notification_status else "Off"
            notification_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=f"Receive Notification: {status_text}",
                                                       callback_data="toggle_notification_status")]]
            )

            if is_admin:
                admin_prioritize_text = "On" if admin_prioritize_status == "True" else "Off"
                admin_prioritize_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=f"Admin Prioritize: {admin_prioritize_text}",
                                                           callback_data="toggle_admin_prioritize")]]
                )
                await message.answer(text="Your notification status:", reply_markup=notification_keyboard)
                await message.answer(text="Admin prioritize status:", reply_markup=admin_prioritize_keyboard)
            else:
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


@router.callback_query(F.data == "toggle_admin_prioritize")
async def toggle_admin_prioritize(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    is_admin = str(user_id) == getenv("ADMIN_USER_ID")
    if not is_admin:
        await callback_query.answer("You are not authorized to use this feature.")
        return

    current_status = await redis_client.get("is_admin_prioritize")
    if current_status is None:
        current_status = "False"  # Default to False if not set
    else:
        current_status = current_status.decode()
    new_status = "False" if current_status == "True" else "True"
    await redis_client.set("is_admin_prioritize", new_status)
    logger.info(f"Admin Prioritize status changed from {current_status} to {new_status}")

    status_text = "On" if new_status == "True" else "Off"
    await callback_query.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"Admin Prioritize: {status_text}",
                                                   callback_data="toggle_admin_prioritize")]]
        )
    )
    await callback_query.answer("Admin prioritize status updated.")


async def send_notification(bot: Bot, fragrance, priority_queue=False, second_try=False):
    try:
        users = await get_users_by_fragrance(fragrance)
        if priority_queue:
            # Notify the admin user immediately
            admin_user_id = getenv("ADMIN_USER_ID")
            await bot.send_photo(
                chat_id=admin_user_id,
                photo=fragrance.image_url,
                caption=f"The fragrance {fragrance.name} is now available!"
            )
            return

        if second_try:
            admin_user_id = int(getenv("ADMIN_USER_ID"))
            if admin_user_id in users:
                users.remove(int(admin_user_id))  # Remove admin from the list for later notifications

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


async def send_message_to_all_users(bot, message_text):
    users = await get_all_users()  # Implement this function to get all user IDs

    async def send_batch(batch, retries=3):
        for attempt in range(retries):
            tasks = [bot.send_message(chat_id=user_id, text=message_text) for user_id in batch]
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
                logger.error(f"Failed to send message to user {user_id} after {retries} attempts")

    batch_size = 50
    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        await send_batch(batch)
        await asyncio.sleep(1)  # Add a delay between batches to avoid rate limiting


async def send_photo_to_all_users(bot, photo_file_id, caption=None):
    users = await get_all_users()  # Implement this function to get all user IDs

    async def send_batch(batch, retries=3):
        for attempt in range(retries):
            tasks = [bot.send_photo(chat_id=user_id, photo=photo_file_id, caption=caption) for user_id in batch]
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
                logger.error(f"Failed to send photo to user {user_id} after {retries} attempts")

    batch_size = 50
    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        await send_batch(batch)
        await asyncio.sleep(1)  # Add a delay between batches to avoid rate limiting


@router.message(F.text == "👨🏻‍💼 Admin")
async def admin_button_pressed(message: Message, state: FSMContext):
    if str(message.from_user.id) == getenv("ADMIN_USER_ID"):
        await message.answer("Please enter the message you want to send to all users.", reply_markup=kb.back_to_menu)
        await state.set_state(AdminMessage.typing_message)
    else:
        await message.answer("You do not have permission to use this feature.")


@router.message(AdminMessage.typing_message)
async def send_admin_message(message: Message, state: FSMContext):
    await state.clear()

    if message.text or message.caption:
        text = message.text or message.caption
        if message.photo:
            photo = message.photo[-1]  # Get the largest photo
            photo_file_id = photo.file_id
            await send_photo_to_all_users(message.bot, photo_file_id, text)
        else:
            await send_message_to_all_users(message.bot, text)
    else:
        await message.answer("Only text and photo messages are supported.")
        return

    await message.answer("Your message has been sent to all users.")
