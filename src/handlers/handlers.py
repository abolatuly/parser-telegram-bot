import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
import src.keyboards.keyboards as kb
from config import config
from src.database import requests
from src.database.requests import get_fragrance_by_name, add_fragrance_to_wishlist, get_wishlist_by_telegram_id, \
    delete_fragrance_from_wishlist, get_notification_status_by_telegram_id, \
    toggle_notification_status_in_db, get_users_by_fragrance, get_all_wishlists
from src.states.states import Add_to_wishlist

TELEGRAM_MESSAGE_LIMIT = 4096

config.setup_logging()
logger = logging.getLogger(__name__)

router: Router = Router()


@router.message(CommandStart())
async def process_any_message(message: Message):
    await requests.set_wishlist(tg_id=message.from_user.id)
    await message.answer(text="Welcome to Montagne Parfums fragrance tracker!", reply_markup=kb.main)


@router.message(F.text == "◀️ Back to menu")
async def menu(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(text="Main menu", reply_markup=kb.main)


@router.message(F.text == "📄 Wishlist")
async def show_wishlist(message: Message):
    try:
        telegram_id = message.from_user.id
        wishlist = await get_wishlist_by_telegram_id(telegram_id)

        if wishlist is None or not wishlist.fragrances:
            await message.answer("Your wishlist is empty.")
        else:
            for fragrance in wishlist.fragrances:
                delete_from_wishlist = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Delete",
                                                           callback_data=f"_{fragrance.name[:60] if len(fragrance.name) > 60 else fragrance.name}")]])
                await message.answer(text=f"{fragrance.name.title()}", reply_markup=delete_from_wishlist)

        await message.answer(text="If you want to add a new fragrance, press \"Add fragrance to wishlist\" below",
                             reply_markup=kb.add_to_wishlist)

    except Exception as e:
        logger.error(f"Error showing wishlist: {e}")
        await message.answer("An error occurred while showing your wishlist. Please try again later.")


@router.message(F.text == "➕ Add fragrance to wishlist")
async def type_fragrance(message: Message, state: FSMContext):
    await state.set_state(Add_to_wishlist.adding)
    await message.answer(text="Type the name of a fragrance you want to add")


@router.message(Add_to_wishlist.adding)
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
    await state.set_state(Add_to_wishlist.adding)
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
    try:
        fragrances = await requests.get_all_fragrances()

        messages = []
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
    try:
        telegram_id = message.from_user.id
        notification_status = await get_notification_status_by_telegram_id(telegram_id)

        if notification_status is not None:
            status_text = "On" if notification_status else "Off"
            status = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=f"Receive Notification: {status_text}",
                                                       callback_data="toggle_notification_status")]])
            await message.answer(text="Your notification status:", reply_markup=status)
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

        for user_id in users:
            try:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=fragrance.image_url,  # Use the image URL from the fragrance object
                    caption=f"The fragrance {fragrance.name} is now available!"
                )
            except Exception as e:
                logger.error(f"Error sending notification to user {user_id}: {e}")
    except Exception as e:
        logger.error(f"Error sending notification: {e}")


async def send_notification_new_fragrance(bot: Bot, fragrance):
    try:
        users = await get_all_wishlists()

        for user_id in users:
            try:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=fragrance.image_url,  # Use the image URL from the fragrance object
                    caption=f"New fragrance is at the store! Check out {fragrance.name}!"
                )
            except Exception as e:
                logger.error(f"Error sending notification to user {user_id}: {e}")
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
