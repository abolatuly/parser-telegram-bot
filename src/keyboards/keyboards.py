from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton

main = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📄 Wishlist"),
                                      KeyboardButton(text="🔍 Fragrances")]],
                           input_field_placeholder="Choose from the menu", resize_keyboard=True)

add_to_wishlist = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="➕ Add fragrance to wishlist")],
                                                [KeyboardButton(text="◀️ Back to menu")]],
                                      input_field_placeholder="Choose from the menu", resize_keyboard=True)

add_more = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕Add more", callback_data="add_more")]])
