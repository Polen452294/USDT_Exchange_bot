from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="USDT в наличные", callback_data="dir:USDT_TO_CASH"),
            ],
            [
                InlineKeyboardButton(text="Наличные в USDT", callback_data="dir:CASH_TO_USDT"),
            ],
        ]
    )


def kb_offices(offices: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for o in offices:
        rows.append([InlineKeyboardButton(text=o["button_text"], callback_data=f"office:{o['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_next() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Далее", callback_data="next")]])


def kb_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, все отлично", callback_data="confirm:yes")],
            [InlineKeyboardButton(text="Нет, хочу внести изменения", callback_data="confirm:no")],
        ]
    )