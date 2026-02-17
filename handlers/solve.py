# handlers/solve.py
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Iterable

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import async_sessionmaker

from states import SolveSG
from db.repo import Repo

router = Router()

PAGE_SIZE = 10


# ---------------- CallbackData ----------------
class SolveCB(CallbackData, prefix="sol"):
    action: str
    id: int | None = None
    page: int | None = None


class OptionCB(CallbackData, prefix="opt"):
    qid: int
    oid: int


# ---------------- helpers ----------------
def h(s: str) -> str:
    # безопасно при HTML parse_mode по умолчанию
    return escape(s or "")


def _kb_back_to_menu() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ В меню", callback_data=SolveCB(action="back_menu").pack())
    b.adjust(1)
    return b


def _kb_subjects(subjects: list[tuple[int, str]]) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    for sid, name in subjects:
        b.button(text=name, callback_data=SolveCB(action="pick_subject", id=sid).pack())
    b.button(text="↩️ В меню", callback_data=SolveCB(action="back_menu").pack())
    b.adjust(1)
    return b


def _kb_topics(topics: list[tuple[int, str]]) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    for tid, name in topics:
        b.button(text=name, callback_data=SolveCB(action="pick_topic", id=tid).pack())
    b.button(text="↩️ В меню", callback_data=SolveCB(action="back_menu").pack())
    b.adjust(1)
    return b


def _kb_subtopics_mode() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Все подтемы", callback_data=SolveCB(action="sub_all").pack())
    b.button(text="🎯 Выбрать подтемы", callback_data=SolveCB(action="sub_pick").pack())
    b.button(text="↩️ Назад к темам", callback_data=SolveCB(action="back_topics").pack())
    b.adjust(1)
    return b


def _kb_subtopics_picker(subtopics: list[tuple[int, str]], selected: set[int]) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    for stid, name in subtopics:
        mark = "☑" if stid in selected else "☐"
        b.button(text=f"{mark} {name}", callback_data=SolveCB(action="toggle_sub", id=stid).pack())

    b.button(text="🚀 Начать", callback_data=SolveCB(action="start_session").pack())
    b.button(text="↩️ Назад к темам", callback_data=SolveCB(action="back_topics").pack())
    b.adjust(1)
    return b


def _kb_single_options(qid: int, options: list[tuple[int, str]]) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    for oid, txt in options:
        b.button(text=txt, callback_data=OptionCB(qid=qid, oid=oid).pack())
    b.adjust(1)
    return b


def _kb_multi_options(qid: int, options: list[tuple[int, str]], selected: set[int]) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    for oid, txt in options:
        mark = "☑" if oid in selected else "☐"
        b.button(text=f"{mark} {txt}", callback_data=OptionCB(qid=qid, oid=oid).pack())
    b.button(text="✅ Ответить", callback_data=SolveCB(action="submit_multi").pack())
    b.adjust(1)
    return b


def _kb_session_controls() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.button(text="➡️ Следующий", callback_data=SolveCB(action="next").pack())
    b.button(text="⏹ Завершить", callback_data=SolveCB(action="stop").pack())
    b.adjust(2)
    return b


async def _send_or_edit(callback: CallbackQuery, text: str, reply_markup):
    # Практичная обёртка: если edit_text падает — шлём новым сообщением
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


# ---------------- entry points ----------------
@router.message(Command("solve"))
async def solve_cmd(message: Message, state: FSMContext, sessionmaker: async_sessionmaker):
    await state.clear()
    await state.set_state(SolveSG.choose_subject)

    async with sessionmaker() as s:
        repo = Repo(s)
        subjects = await repo.get_subjects()

    if not subjects:
        await message.answer("Пока нет предметов в базе. Обратись к администратору.")
        return

    items = [(x.id, x.name) for x in subjects]
    kb = _kb_subjects(items).as_markup()
    await message.answer("Шаг 0: выбери предмет:", reply_markup=kb)


@router.callback_query(SolveCB.filter(F.action == "solve_entry"))
async def solve_entry_callback(callback: CallbackQuery, state: FSMContext, sessionmaker: async_sessionmaker):
    # если у тебя в меню кнопка ведёт сюда
    await callback.answer()
    await solve_cmd(Message.model_validate(callback.message.model_dump()), state, sessionmaker)  # безопасно переиспользовать
    # примечание: если PyCharm ругнётся на model_validate, скажи — дам версию без этого трюка.


# ---------------- navigation / back ----------------
@router.callback_query(SolveCB.filter(F.action == "back_menu"))
async def back_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("Ок. Вернуться в главное меню (у тебя тут должна быть своя клавиатура).")


@router.callback_query(SolveCB.filter(F.action == "back_topics"))
async def back_topics(callback: CallbackQuery, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    data = await state.get_data()
    subject_id = data.get("subject_id")
    if not subject_id:
        await solve_cmd(Message.model_validate(callback.message.model_dump()), state, sessionmaker)
        return

    async with sessionmaker() as s:
        repo = Repo(s)
        topics = await repo.get_topics(subject_id)

    items = [(t.id, t.name) for t in topics]
    await state.set_state(SolveSG.choose_topic)
    await _send_or_edit(callback, "Шаг 1: выбери тему:", _kb_topics(items).as_markup())


# ---------------- subject -> topic ----------------
@router.callback_query(SolveCB.filter(F.action == "pick_subject"))
async def pick_subject(callback: CallbackQuery, callback_data: SolveCB, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    subject_id = callback_data.id
    await state.update_data(subject_id=subject_id)

    async with sessionmaker() as s:
        repo = Repo(s)
        topics = await repo.get_topics(subject_id)

    if not topics:
        await callback.message.answer("Для этого предмета нет тем. Обратись к администратору.")
        return

    items = [(t.id, t.name) for t in topics]
    await state.set_state(SolveSG.choose_topic)
    await _send_or_edit(callback, "Шаг 1: выбери тему:", _kb_topics(items).as_markup())


# ---------------- topic -> subtopic mode ----------------
@router.callback_query(SolveCB.filter(F.action == "pick_topic"))
async def pick_topic(callback: CallbackQuery, callback_data: SolveCB, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    topic_id = callback_data.id
    await state.update_data(topic_id=topic_id)

    # подтемы могут быть пустыми — тогда пропускаем к старту сразу
    async with sessionmaker() as s:
        repo = Repo(s)
        subtopics = await repo.get_subtopics(topic_id)

    await state.update_data(
        subtopics_all=[(st.id, st.name) for st in subtopics],
        selected_subtopic_ids=set(),
        session_total=0,
        session_correct=0,
    )

    await state.set_state(SolveSG.choose_subtopics_mode)

    if not subtopics:
        # нет подтем — стартуем сразу
        await state.update_data(subtopic_ids=[])
        await state.set_state(SolveSG.solving)
        await callback.message.answer("Подтем нет — начинаю сессию.")
        await _send_next_question(callback, state, sessionmaker)
        return

    await _send_or_edit(callback, "Шаг 2: подтемы. Что выбираем?", _kb_subtopics_mode().as_markup())


@router.callback_query(SolveCB.filter(F.action == "sub_all"))
async def sub_all(callback: CallbackQuery, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    await state.update_data(subtopic_ids=[])  # пусто => все
    await state.set_state(SolveSG.solving)
    await _send_or_edit(callback, "Ок. Беру все подтемы. Начинаю.", reply_markup=None)
    await _send_next_question(callback, state, sessionmaker)


@router.callback_query(SolveCB.filter(F.action == "sub_pick"))
async def sub_pick(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    subtopics_all: list[tuple[int, str]] = data.get("subtopics_all") or []
    selected: set[int] = set(data.get("selected_subtopic_ids") or set())

    await state.set_state(SolveSG.choose_subtopics)
    await _send_or_edit(callback, "Шаг 3: выбери подтемы (можно несколько):", _kb_subtopics_picker(subtopics_all, selected).as_markup())


@router.callback_query(SolveCB.filter(F.action == "toggle_sub"))
async def toggle_sub(callback: CallbackQuery, callback_data: SolveCB, state: FSMContext):
    await callback.answer()
    stid = callback_data.id

    data = await state.get_data()
    subtopics_all: list[tuple[int, str]] = data.get("subtopics_all") or []
    selected: set[int] = set(data.get("selected_subtopic_ids") or set())

    if stid in selected:
        selected.remove(stid)
    else:
        selected.add(stid)

    await state.update_data(selected_subtopic_ids=selected)
    await callback.message.edit_reply_markup(reply_markup=_kb_subtopics_picker(subtopics_all, selected).as_markup())


@router.callback_query(SolveCB.filter(F.action == "start_session"))
async def start_session(callback: CallbackQuery, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    data = await state.get_data()
    selected: set[int] = set(data.get("selected_subtopic_ids") or set())
    if not selected:
        await callback.answer("Выбери хотя бы одну подтему или вернись и выбери «Все подтемы».", show_alert=False)
        return

    await state.update_data(subtopic_ids=sorted(selected))
    await state.set_state(SolveSG.solving)
    await _send_or_edit(callback, "Начинаю сессию.", reply_markup=None)
    await _send_next_question(callback, state, sessionmaker)


# ---------------- core: send question ----------------
async def _send_next_question(callback: CallbackQuery, state: FSMContext, sessionmaker: async_sessionmaker):
    data = await state.get_data()
    subject_id = data["subject_id"]
    topic_id = data["topic_id"]
    subtopic_ids = data.get("subtopic_ids") or None  # None/[] => все

    async with sessionmaker() as s:
        repo = Repo(s)
        user = await repo.get_or_create_user(tg_id=callback.from_user.id)
        qid = await repo.pick_next_question_id(
            user_id=user.id,
            subject_id=subject_id,
            topic_id=topic_id,
            subtopic_ids=subtopic_ids,
        )

        if qid is None:
            await state.clear()
            await callback.message.answer("Вопросы закончились (или всё недавно решено). Попробуй другую тему/подтемы.")
            return

        q = await repo.get_question(qid)
        opts = await repo.get_options(qid)

    await state.update_data(current_qid=qid, selected_option_ids=set())

    options_tuple = [(o.id, o.text) for o in opts]

    if q.qtype == "multi":
        kb = _kb_multi_options(qid, options_tuple, set()).as_markup()
    else:
        kb = _kb_single_options(qid, options_tuple).as_markup()

    # Не используем HTML-теги, чтобы не ловить parse errors на <...>
    text = q.text

    if getattr(q, "image_file_id", None):
        await callback.message.answer_photo(q.image_file_id, caption=text, reply_markup=kb)
    else:
        await callback.message.answer(text, reply_markup=kb)


# ---------------- answering: options click ----------------
@router.callback_query(OptionCB.filter())
async def on_option_click(callback: CallbackQuery, callback_data: OptionCB, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    data = await state.get_data()
    current_qid = data.get("current_qid")

    if current_qid != callback_data.qid:
        await callback.answer("Этот вопрос уже неактуален.", show_alert=False)
        return

    async with sessionmaker() as s:
        repo = Repo(s)
        q = await repo.get_question(current_qid)
        opts = await repo.get_options(current_qid)

    if q.qtype == "single":
        chosen = [callback_data.oid]

        async with sessionmaker() as s:
            repo = Repo(s)
            user = await repo.get_or_create_user(tg_id=callback.from_user.id)
            correct_ids = await repo.get_correct_option_ids(current_qid)
            is_correct = set(chosen) == correct_ids
            await repo.add_attempt(user.id, current_qid, is_correct, chosen)

        total = int(data.get("session_total", 0)) + 1
        correct = int(data.get("session_correct", 0)) + (1 if is_correct else 0)
        await state.update_data(session_total=total, session_correct=correct)

        msg = "✅ Верно!" if is_correct else "❌ Неверно."
        expl = getattr(q, "explanation", "") or "-"
        await callback.message.answer(
            f"{msg}\n\nПояснение:\n{expl}\n\nСчёт: {correct}/{total}",
            reply_markup=_kb_session_controls().as_markup(),
        )
        return

    # multi: toggle selected + redraw
    selected: set[int] = set(data.get("selected_option_ids") or set())
    if callback_data.oid in selected:
        selected.remove(callback_data.oid)
    else:
        selected.add(callback_data.oid)

    await state.update_data(selected_option_ids=selected)

    options_tuple = [(o.id, o.text) for o in opts]
    await callback.message.edit_reply_markup(
        reply_markup=_kb_multi_options(current_qid, options_tuple, selected).as_markup()
    )


@router.callback_query(SolveCB.filter(F.action == "submit_multi"))
async def submit_multi(callback: CallbackQuery, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    data = await state.get_data()
    qid = data.get("current_qid")
    selected: set[int] = set(data.get("selected_option_ids") or set())

    if not qid:
        return
    if not selected:
        await callback.answer("Выбери хотя бы один вариант.", show_alert=False)
        return

    async with sessionmaker() as s:
        repo = Repo(s)
        user = await repo.get_or_create_user(tg_id=callback.from_user.id)
        correct_ids = await repo.get_correct_option_ids(qid)
        q = await repo.get_question(qid)

        is_correct = selected == correct_ids
        await repo.add_attempt(user.id, qid, is_correct, sorted(selected))

    total = int(data.get("session_total", 0)) + 1
    correct = int(data.get("session_correct", 0)) + (1 if is_correct else 0)
    await state.update_data(session_total=total, session_correct=correct)

    msg = "✅ Верно!" if is_correct else "❌ Неверно."
    expl = getattr(q, "explanation", "") or "-"
    await callback.message.answer(
        f"{msg}\n\nПояснение:\n{expl}\n\nСчёт: {correct}/{total}",
        reply_markup=_kb_session_controls().as_markup(),
    )


# ---------------- session controls ----------------
@router.callback_query(SolveCB.filter(F.action == "next"))
async def next_q(callback: CallbackQuery, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    await _send_next_question(callback, state, sessionmaker)


@router.callback_query(SolveCB.filter(F.action == "stop"))
async def stop_session(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    total = int(data.get("session_total", 0))
    correct = int(data.get("session_correct", 0))
    await state.clear()
    await callback.message.answer(f"Сессия завершена.\nРешено: {total}\nВерно: {correct}")


