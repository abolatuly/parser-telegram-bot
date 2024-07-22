import logging

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
import src.keyboards.keyboards as kb
from src.database import requests
from src.database.requests import get_fragrance_by_name, add_fragrance_to_wishlist, get_wishlist_by_telegram_id, \
    delete_fragrance_from_wishlist, parse_website
from src.states.states import Add_to_wishlist

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router: Router = Router()


@router.message(CommandStart())
async def process_any_message(message: Message):
    await requests.set_wishlist(tg_id=message.from_user.id)
    await message.answer(text=message.text, reply_markup=kb.main)


@router.message(F.text == "◀️ Back to menu")
async def menu(msg: Message):
    await msg.answer(text="Main menu", reply_markup=kb.main)


@router.message(F.text == "📄 Wishlist")
async def show_wishlist(message: Message):
    await parse_website()
    try:
        telegram_id = message.from_user.id
        wishlist = await get_wishlist_by_telegram_id(telegram_id)

        if wishlist is None or not wishlist.fragrances:
            await message.answer("Your wishlist is empty.")
        else:
            for fragrance in wishlist.fragrances:
                delete_from_wishlist = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Delete",
                                                           callback_data=f"delete_{fragrance.name}")]])
                await message.answer(text=f"{fragrance.name}", reply_markup=delete_from_wishlist)

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
        # Retrieve the user's Telegram ID
        telegram_id = message.from_user.id

        # Get the closest matching fragrance name
        fragrance_name = await get_fragrance_by_name(message.text)

        if fragrance_name:
            # Add the fragrance to the wishlist
            result = await add_fragrance_to_wishlist(telegram_id, fragrance_name)

            if result:
                await message.answer(f"{fragrance_name} was added to your wishlist!", reply_markup=kb.add_more)
            else:
                await message.answer(f"{fragrance_name} is already in your wishlist!", reply_markup=kb.add_more)
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


@router.callback_query(F.data.startswith("delete_"))
async def delete(callback: CallbackQuery):
    try:
        fragrance_name = callback.data.split("_")[1]
        telegram_id = callback.from_user.id

        logger.info(f"Trying to delete {fragrance_name}")
        result = await delete_fragrance_from_wishlist(telegram_id, fragrance_name)
        if result:
            await callback.answer()
            await callback.message.answer(text=f"Deleted: {fragrance_name}")
        else:
            await callback.answer(text="Item not found in wishlist", show_alert=True)

    except Exception as e:
        logger.error(f"Error in delete handler: {e}")
        await callback.answer(text="An error occurred while deleting the fragrance", show_alert=True)
