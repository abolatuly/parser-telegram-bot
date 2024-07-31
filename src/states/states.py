from aiogram.fsm.state import State, StatesGroup


class AddToWishlist(StatesGroup):
    adding = State()


class AdminMessage(StatesGroup):
    typing_message = State()