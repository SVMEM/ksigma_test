from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.callback_data import AdminCB

def admin_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить задание", callback_data=AdminCB(action="add").pack())
    b.adjust(1)
    return b.as_markup()

def qtype_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="single (1 правильный)", callback_data=AdminCB(action="qtype_single").pack())
    b.button(text="multi (несколько)", callback_data=AdminCB(action="qtype_multi").pack())
    b.adjust(1)
    return b.as_markup()

def photo_skip_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⏭ Пропустить фото", callback_data=AdminCB(action="skip_photo").pack())
    b.adjust(1)
    return b.as_markup()

def cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data=AdminCB(action="cancel").pack())
    b.adjust(1)
    return b.as_markup()

def admin_menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить задание", callback_data=AdminCB(action="add").pack())
    b.button(text="📋 Все вопросы", callback_data=AdminCB(action="q_list").pack())
    b.adjust(1)
    return b.as_markup()
