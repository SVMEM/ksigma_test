from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.callback_data import MenuCB

def main_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📚 Решать задания", callback_data=MenuCB(action="solve").pack())
    b.button(text="📊 Моя статистика", callback_data=MenuCB(action="stats").pack())
    b.button(text="ℹ️ Помощь / О боте", callback_data=MenuCB(action="help").pack())
    b.adjust(1)
    return b.as_markup()