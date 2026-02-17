# keyboards/menu.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧠 Решать тесты")],
            [KeyboardButton(text="📊 Статистика")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )