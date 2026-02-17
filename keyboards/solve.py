from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from utils.callback_data import OptionCB, SolveCB
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.callback_data import SolveCB

def subjects_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🧬 Биология", callback_data=SolveCB(action="subject", id=1).pack())
    b.button(text="📈 Экономика", callback_data=SolveCB(action="subject", id=2).pack())
    b.adjust(1)
    return b.as_markup()

def yes_no_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Да", callback_data=SolveCB(action="want_subtopics_yes").pack())
    b.button(text="Нет (все подтемы)", callback_data=SolveCB(action="want_subtopics_no").pack())
    b.adjust(2)
    return b.as_markup()

def session_controls_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➡️ Следующее задание", callback_data=SolveCB(action="next").pack())
    b.button(text="⏹️ Завершить сессию", callback_data=SolveCB(action="stop").pack())
    b.adjust(1)
    return b.as_markup()




def single_options_kb(qid: int, options: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for oid, txt in options:
        b.button(text=txt, callback_data=OptionCB(qid=qid, oid=oid).pack())
    b.adjust(1)
    return b.as_markup()

def multi_options_kb(qid: int, options: list[tuple[int, str]], selected: set[int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for oid, txt in options:
        mark = "☑" if oid in selected else "☐"
        b.button(text=f"{mark} {txt}", callback_data=OptionCB(qid=qid, oid=oid).pack())
    b.button(text="✅ Ответить", callback_data=SolveCB(action="submit_multi").pack())
    b.adjust(1)
    return b.as_markup()
