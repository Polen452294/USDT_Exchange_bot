from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="USDT в наличные", callback_data="dir:USDT_TO_CASH")],
            [InlineKeyboardButton(text="Наличные в USDT", callback_data="dir:CASH_TO_USDT")],
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


def kb_nudge2() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Продолжить", callback_data="n2:continue")
    kb.button(text="Задать вопрос менеджеру", callback_data="n2:manager")
    kb.button(text="Я еще подумаю", callback_data="n2:later")
    kb.adjust(1)
    return kb.as_markup()


def kb_nudge1() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, актуально", callback_data="n1:yes")
    kb.button(text="Нет, не актуально", callback_data="n1:no")
    kb.button(text="Написать менеджеру самому: @coinpointlara", callback_data="n1:manager")
    kb.adjust(1)
    return kb.as_markup()

def kb_nudge3():
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, зафиксировать", callback_data="n3:yes")
    kb.button(text="Не сейчас", callback_data="n3:no")
    kb.adjust(1)
    return kb.as_markup()