import json
from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def main_menu_keyboard() -> str:
    kb = VkKeyboard(one_time=False)
    kb.add_button("Создать заявку", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("Информация", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()