from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import date, timedelta

from app.models import Direction, direction_button_label


def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=direction_button_label(Direction.USDT_TO_TRY_CASH),
                    callback_data="dir:USDT_TO_TRY_CASH",
                )
            ],
            [
                InlineKeyboardButton(
                    text=direction_button_label(Direction.TRY_CASH_TO_USDT),
                    callback_data="dir:TRY_CASH_TO_USDT",
                )
            ],
        ]
    )


def kb_offices(offices: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for o in offices:
        rows.append([InlineKeyboardButton(text="🏢 " + o["button_text"], callback_data=f"office:{o['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_next() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➡️ Далее", callback_data="next")]])


def kb_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, всё отлично", callback_data="confirm:yes")],
            [InlineKeyboardButton(text="✍️ Хочу внести изменения", callback_data="confirm:no")],
        ]
    )


def kb_nudge2() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➡️ Продолжить", callback_data="n2:continue")
    kb.button(text="💬 Задать вопрос менеджеру", callback_data="n2:manager")
    kb.button(text="⏳ Я ещё подумаю", callback_data="n2:later")
    kb.adjust(1)
    return kb.as_markup()


def kb_nudge1() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, актуально", callback_data="n1:yes")
    kb.button(text="❌ Нет, не актуально", callback_data="n1:no")
    kb.button(text="💬 Написать менеджеру: @coinpointlara", callback_data="n1:manager")
    kb.adjust(1)
    return kb.as_markup()


def kb_nudge3():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, зафиксировать", callback_data="n3:yes")
    kb.button(text="⏳ Не сейчас", callback_data="n3:no")
    kb.adjust(1)
    return kb.as_markup()


def kb_nudge4() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да", callback_data="n4:yes")
    kb.adjust(1)
    return kb.as_markup()


def kb_nudge5(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data=f"n5_yes:{request_id}")],
            [InlineKeyboardButton(text="❌ Нет", callback_data=f"n5_no:{request_id}")],
        ]
    )


def kb_nudge6(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data=f"n6_yes:{request_id}")],
            [InlineKeyboardButton(text="❌ Нет", callback_data=f"n6_no:{request_id}")],
        ]
    )


def kb_nudge7(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data=f"n7_yes:{request_id}")],
            [InlineKeyboardButton(text="❌ Нет", callback_data=f"n7_no:{request_id}")],
        ]
    )


_RU_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def kb_dates_7(start: date | None = None, days: int = 7) -> InlineKeyboardMarkup:
    start = start or date.today()

    kb = InlineKeyboardBuilder()
    for i in range(days):
        d = start + timedelta(days=i)
        wd = _RU_WEEKDAYS[d.weekday()]
        if i == 0:
            text = f"Сегодня · {wd} · {d.strftime('%d.%m')}"
        else:
            text = f"{wd} · {d.strftime('%d.%m')}"
        kb.button(text=text, callback_data=f"date:{d.isoformat()}")

    kb.adjust(1)
    return kb.as_markup()