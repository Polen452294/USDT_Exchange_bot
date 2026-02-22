from __future__ import annotations

from typing import Iterable, Tuple

from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def main_menu_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Создать заявку", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("Информация", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def direction_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("USDT в наличные", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("Наличные в USDT", color=VkKeyboardColor.PRIMARY)
    return kb.get_keyboard()


def next_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Далее", color=VkKeyboardColor.PRIMARY)
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


def confirm_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Да, все отлично", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("Нет, хочу внести изменения", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()

def hide_keyboard() -> str:
    return '{"one_time": true, "buttons": []}'