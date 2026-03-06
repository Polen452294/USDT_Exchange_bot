from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Tuple

from vk_api.keyboard import VkKeyboard, VkKeyboardColor


_RU_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def main_menu_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("📝 Создать заявку", color=VkKeyboardColor.PRIMARY)
    return kb.get_keyboard()


def direction_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("USDT в наличные", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("Наличные в USDT", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_openlink_button("💳 Купить USDT с карты СБП", "https://t.me/CoinPlata_bot")
    return kb.get_keyboard()


def offices_keyboard(offices: Iterable[Tuple[str, str]]) -> str:
    kb = VkKeyboard(one_time=False)
    first = True
    for _office_id, label in offices:
        if not first:
            kb.add_line()
        kb.add_button(label, color=VkKeyboardColor.PRIMARY)
        first = False
    return kb.get_keyboard()


def dates_keyboard(start: date | None = None, days: int = 7) -> str:
    start = start or date.today()

    kb = VkKeyboard(one_time=False)
    for i in range(days):
        d = start + timedelta(days=i)
        wd = _RU_WEEKDAYS[d.weekday()]
        if i == 0:
            text = f"Сегодня · {wd} · {d.strftime('%d.%m')}"
        else:
            text = f"{wd} · {d.strftime('%d.%m')}"
        if i > 0:
            kb.add_line()
        kb.add_button(text, color=VkKeyboardColor.PRIMARY)
    return kb.get_keyboard()


def confirm_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("✅ Да, всё отлично", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("✍️ Хочу внести изменения", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def hide_keyboard() -> str:
    return VkKeyboard.get_empty_keyboard()


def nudge1_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("✅ Да, актуально", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("❌ Нет, не актуально", color=VkKeyboardColor.NEGATIVE)
    kb.add_line()
    kb.add_openlink_button("💬 Написать менеджеру", "https://t.me/coinpointlara")
    return kb.get_keyboard()


def nudge2_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("➡️ Продолжить", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_openlink_button("💬 Написать менеджеру", "https://t.me/coinpointlara")
    kb.add_line()
    kb.add_button("⏳ Я ещё подумаю", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def nudge3_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("✅ Да, зафиксировать", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("⏳ Не сейчас", color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_openlink_button("💬 Написать менеджеру", "https://t.me/coinpointlara")
    return kb.get_keyboard()


def nudge4_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("✅ Да", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_openlink_button("💬 Написать менеджеру", "https://t.me/coinpointlara")
    return kb.get_keyboard()


def nudge5_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("✅ Да", color=VkKeyboardColor.POSITIVE)
    kb.add_button("❌ Нет", color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()


def nudge6_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("✅ Да", color=VkKeyboardColor.POSITIVE)
    kb.add_button("❌ Нет", color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()


def nudge7_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("✅ Да", color=VkKeyboardColor.POSITIVE)
    kb.add_button("❌ Нет", color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()