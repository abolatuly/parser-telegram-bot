from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton


def get_main_keyboard(is_admin):
    keyboard = [
        [KeyboardButton(text="📄 Wishlist"), KeyboardButton(text="🔍 Fragrances")],
        [KeyboardButton(text="⚙️ Settings")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="👨🏻‍💼 Admin")])
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        input_field_placeholder="Choose from the menu",
        resize_keyboard=True
    )


add_to_wishlist = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="➕ Add fragrance to wishlist")],
                                                [KeyboardButton(text="◀️ Back to menu")]],
                                      input_field_placeholder="Choose from the menu", resize_keyboard=True)

add_more = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕Add more", callback_data="add_more")]])

back_to_menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Back to menu")]], resize_keyboard=True)
