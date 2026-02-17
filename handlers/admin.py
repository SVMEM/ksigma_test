import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import async_sessionmaker


from states import AdminSG
from db.repo import Repo
from utils.callback_data import AdminCB
from keyboards.admin import admin_menu_kb, qtype_kb, photo_skip_kb


router = Router()


# ---------- utils parsing ----------
def parse_options(text: str) -> list[tuple[str, str]]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: list[tuple[str, str]] = []
    for line in lines:
        m = re.match(r"^([A-DА-Г])[\)\.\:]\s*(.+)$", line)
        if not m:
            continue
        out.append((m.group(1).upper(), m.group(2).strip()))
    if len(out) < 2:
        raise ValueError("Нужно минимум 2 варианта в формате A) ...")
    return out


def parse_correct(text: str) -> set[str]:
    s = text.strip().upper().replace(" ", "")
    parts = [p for p in s.split(",") if p]
    if not parts:
        raise ValueError("Пустой список правильных ответов")
    for p in parts:
        if p not in {"A", "B", "C", "D", "А", "Б", "В", "Г"}:
            raise ValueError("Допустимы только A,B,C,D (или А,Б,В,Г)")
    mp = {"А": "A", "Б": "B", "В": "C", "Г": "D"}
    return {mp.get(p, p) for p in parts}


def build_list_kb(items: list[tuple[int, str]], action: str, extra_buttons: list[tuple[str, str]] | None = None):
    b = InlineKeyboardBuilder()
    for _id, name in items:
        b.button(text=name, callback_data=AdminCB(action=action, id=_id).pack())
    if extra_buttons:
        for text, cb in extra_buttons:
            b.button(text=text, callback_data=cb)
    b.adjust(1)
    return b.as_markup()


# ---------- entry ----------
@router.message(Command("admin"))
async def admin_entry(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Админ-панель:", reply_markup=admin_menu_kb())


@router.callback_query(AdminCB.filter(F.action == "add"))
async def add_start(callback: CallbackQuery, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    await state.clear()


    async with sessionmaker() as s:
        repo = Repo(s)
        subjects = await repo.get_subjects()


    if not subjects:
        await callback.message.edit_text("В БД нет предметов (subjects). Сначала добавь их.")
        return


    items = [(subj.id, subj.name) for subj in subjects]
    kb = build_list_kb(items, action="pick_subject", extra_buttons=[("❌ Отмена", AdminCB(action="cancel").pack())])


    await state.set_state(AdminSG.add_q_choose_subject)
    await callback.message.edit_text("Шаг 0: выбери предмет:", reply_markup=kb)


@router.callback_query(AdminCB.filter(F.action == "cancel"))
async def cancel_any(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Отменено. /admin")


# ---------- subject -> topic ----------
@router.callback_query(AdminCB.filter(F.action == "pick_subject"))
async def pick_subject(callback: CallbackQuery, callback_data: AdminCB, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    subject_id = callback_data.id
    await state.update_data(subject_id=subject_id)


    async with sessionmaker() as s:
        repo = Repo(s)
        topics = await repo.get_topics(subject_id)


    if not topics:
        await callback.message.edit_text("Для этого предмета нет тем (topics). Сначала добавь темы.")
        return


    items = [(t.id, t.name) for t in topics]
    kb = build_list_kb(items, action="pick_topic", extra_buttons=[("❌ Отмена", AdminCB(action="cancel").pack())])


    await state.set_state(AdminSG.add_q_choose_topic)
    await callback.message.edit_text("Шаг 1: выбери тему:", reply_markup=kb)


# ---------- topic -> subtopic ----------
@router.callback_query(AdminCB.filter(F.action == "pick_topic"))
async def pick_topic(callback: CallbackQuery, callback_data: AdminCB, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    topic_id = callback_data.id
    await state.update_data(topic_id=topic_id)


    async with sessionmaker() as s:
        repo = Repo(s)
        subtopics = await repo.get_subtopics(topic_id)


    items = [(st.id, st.name) for st in subtopics]
    extra = [
        ("➕ Создать подтему", AdminCB(action="create_subtopic").pack()),
        ("— Без подтемы", AdminCB(action="no_subtopic").pack()),
        ("❌ Отмена", AdminCB(action="cancel").pack()),
    ]
    kb = build_list_kb(items, action="pick_subtopic", extra_buttons=extra)


    await state.set_state(AdminSG.add_q_choose_subtopic)
    await callback.message.edit_text("Шаг 2: выбери подтему (или создай):", reply_markup=kb)


@router.callback_query(AdminCB.filter(F.action == "no_subtopic"))
async def no_subtopic(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(subtopic_id=None)
    await state.set_state(AdminSG.add_q_type)
    await callback.message.edit_text("Шаг 3: выбери тип вопроса:", reply_markup=qtype_kb())


@router.callback_query(AdminCB.filter(F.action == "pick_subtopic"))
async def pick_subtopic(callback: CallbackQuery, callback_data: AdminCB, state: FSMContext):
    await callback.answer()
    await state.update_data(subtopic_id=callback_data.id)
    await state.set_state(AdminSG.add_q_type)
    await callback.message.edit_text("Шаг 3: выбери тип вопроса:", reply_markup=qtype_kb())


@router.callback_query(AdminCB.filter(F.action == "create_subtopic"))
async def ask_subtopic_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(waiting_new_subtopic=True)
    await callback.message.edit_text("Введи название новой подтемы текстом:")


@router.message(AdminSG.add_q_choose_subtopic)
async def create_subtopic_name(message: Message, state: FSMContext, sessionmaker: async_sessionmaker):
    data = await state.get_data()
    if not data.get("waiting_new_subtopic"):
        return


    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Слишком коротко. Введи название подтемы ещё раз:")
        return


    topic_id = data["topic_id"]
    async with sessionmaker() as s:
        repo = Repo(s)
        subtopic_id = await repo.create_subtopic(topic_id, name)


    await state.update_data(subtopic_id=subtopic_id, waiting_new_subtopic=False)
    await state.set_state(AdminSG.add_q_type)
    await message.answer("Подтема создана. Шаг 3: выбери тип вопроса:", reply_markup=qtype_kb())


# ---------- ввод вопроса ----------
@router.callback_query(AdminCB.filter(F.action.in_({"qtype_single", "qtype_multi"})))
async def pick_qtype(callback: CallbackQuery, callback_data: AdminCB, state: FSMContext):
    await callback.answer()
    qtype = "single" if callback_data.action == "qtype_single" else "multi"
    await state.update_data(qtype=qtype)
    await state.set_state(AdminSG.add_q_text)
    await callback.message.edit_text("Шаг 4: отправь текст вопроса (сообщением).")


@router.message(AdminSG.add_q_text)
async def got_q_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("Текст слишком короткий. Отправь нормальный текст вопроса.")
        return
    await state.update_data(q_text=text)
    await state.set_state(AdminSG.add_q_image)
    await message.answer("Шаг 5: отправь фото (если нужно) или нажми «Пропустить фото».", reply_markup=photo_skip_kb())


@router.callback_query(AdminCB.filter(F.action == "skip_photo"))
async def skip_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(image_file_id=None)
    await state.set_state(AdminSG.add_q_options)
    await callback.message.edit_text("Шаг 6: отправь варианты ответов:\nA) ...\nB) ...\nC) ...\nD) ...")


@router.message(AdminSG.add_q_image)
async def got_photo_or_ignore(message: Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        await state.update_data(image_file_id=file_id)
        await state.set_state(AdminSG.add_q_options)
        await message.answer("Шаг 6: отправь варианты ответов:\nA) ...\nB) ...\nC) ...\nD) ...")
        return
    await message.answer("Нужно фото или нажми кнопку «Пропустить фото».")


@router.message(AdminSG.add_q_options)
async def got_options(message: Message, state: FSMContext):
    try:
        opts = parse_options(message.text or "")
    except ValueError as e:
        await message.answer(f"Ошибка: {e}\nПример:\nA) ...\nB) ...")
        return
    await state.update_data(options=opts)
    await state.set_state(AdminSG.add_q_correct)
    await message.answer("Шаг 7: укажи правильные варианты.\nsingle: B\nmulti: B,C")


@router.message(AdminSG.add_q_correct)
async def got_correct(message: Message, state: FSMContext):
    data = await state.get_data()
    qtype = data["qtype"]


    try:
        correct_labels = parse_correct(message.text or "")
    except ValueError as e:
        await message.answer(f"Ошибка: {e}\nПример: B или B,C")
        return


    if qtype == "single" and len(correct_labels) != 1:
        await message.answer("Для single должен быть ровно 1 правильный вариант. Пример: B")
        return


    labels_present = {lbl for (lbl, _txt) in data["options"]}
    mp = {"А": "A", "Б": "B", "В": "C", "Г": "D"}
    normalized_present = {mp.get(x, x) for x in labels_present}
    if not correct_labels.issubset(normalized_present):
        await message.answer("Правильные варианты не совпадают с опциями. Проверь A/B/C/D.")
        return


    await state.update_data(correct_labels=correct_labels)
    await state.set_state(AdminSG.add_q_expl)
    await message.answer("Шаг 8: отправь пояснение (объяснение решения).")


@router.message(AdminSG.add_q_expl)
async def got_expl_and_save(message: Message, state: FSMContext, sessionmaker: async_sessionmaker):
    expl = (message.text or "").strip()
    if len(expl) < 3:
        await message.answer("Пояснение слишком короткое. Отправь нормальное объяснение.")
        return


    data = await state.get_data()


    options_raw: list[tuple[str, str]] = data["options"]
    correct_labels: set[str] = data["correct_labels"]


    mp = {"А": "A", "Б": "B", "В": "C", "Г": "D"}
    options_for_db: list[tuple[str, bool]] = []
    for label, text in options_raw:
        lab = mp.get(label, label)
        options_for_db.append((text, lab in correct_labels))


    async with sessionmaker() as s:
        repo = Repo(s)
        qid = await repo.create_question(
            subject_id=data["subject_id"],
            topic_id=data["topic_id"],
            subtopic_id=data.get("subtopic_id"),
            text=data["q_text"],
            qtype=data["qtype"],
            explanation=expl,
            image_file_id=data.get("image_file_id"),
            options=options_for_db,
        )


    await state.clear()
    await message.answer(f"Готово. Вопрос сохранён (id={qid}).\n/admin")

from aiogram.exceptions import TelegramBadRequest

PAGE_SIZE = 8

def questions_list_kb(question_ids: list[int], page: int, has_prev: bool, has_next: bool):
    b = InlineKeyboardBuilder()
    for qid in question_ids:
        b.button(text=f"Открыть #{qid}", callback_data=AdminCB(action="q_open", id=qid).pack())

    nav = InlineKeyboardBuilder()
    if has_prev:
        nav.button(text="⬅️ Назад", callback_data=AdminCB(action="q_page", page=page-1).pack())
    if has_next:
        nav.button(text="➡️ Вперёд", callback_data=AdminCB(action="q_page", page=page+1).pack())

    # кнопка назад в /admin
    b.button(text="↩️ В админ-меню", callback_data=AdminCB(action="back_admin").pack())
    b.adjust(1)
    if nav.buttons:
        # добавляем навигацию отдельным рядом
        b.row(*nav.buttons)
    return b.as_markup()

@router.callback_query(AdminCB.filter(F.action == "back_admin"))
async def back_admin(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Админ-панель:", reply_markup=admin_menu_kb())

@router.callback_query(AdminCB.filter(F.action.in_({"q_list", "q_page"})))
async def questions_list(callback: CallbackQuery, callback_data: AdminCB, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    page = callback_data.page or 0
    if page < 0:
        page = 0

    # (опционально) можно хранить фильтры в state: subject_id/topic_id
    data = await state.get_data()
    subject_id = data.get("q_filter_subject_id")
    topic_id = data.get("q_filter_topic_id")

    offset = page * PAGE_SIZE

    async with sessionmaker() as s:
        repo = Repo(s)
        total = await repo.count_questions(subject_id=subject_id, topic_id=topic_id)
        qs = await repo.list_questions_page(offset=offset, limit=PAGE_SIZE, subject_id=subject_id, topic_id=topic_id)

    has_prev = page > 0
    has_next = (offset + PAGE_SIZE) < total

    qids = [q.id for q in qs]
    text = f"Вопросы (страница {page+1}). Всего: {total}\n" \
           f"Показано: {len(qids)}\n\n" \
           f"Нажми «Открыть #id»."

    kb = questions_list_kb(qids, page, has_prev, has_next)

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        # если редактирование не удалось (например, message is not modified), отправим новым сообщением
        await callback.message.answer(text, reply_markup=kb)

@router.callback_query(AdminCB.filter(F.action == "q_open"))
async def question_open(callback: CallbackQuery, callback_data: AdminCB, sessionmaker: async_sessionmaker):
    await callback.answer()
    qid = callback_data.id

    async with sessionmaker() as s:
        repo = Repo(s)
        q = await repo.get_question_full(qid)
        if not q:
            await callback.message.answer("Вопрос не найден.")
            return
        opts = await repo.get_options(qid)

    lines = [f"Вопрос #{q.id}",
             f"Тип: {q.qtype}",
             "",
             q.text,
             "",
             "Варианты:"]
    for i, opt in enumerate(opts, start=1):
        mark = "✅" if opt.is_correct else " "
        lines.append(f"{i}. [{mark}] {opt.text}")

    lines.append("")
    lines.append("Пояснение:")
    lines.append(q.explanation or "-")

    text = "\n".join(lines)

    b = InlineKeyboardBuilder()
    b.button(text="🗑 Удалить", callback_data=AdminCB(action="q_del", id=q.id).pack())
    b.button(text="↩️ К списку", callback_data=AdminCB(action="q_list").pack())
    b.adjust(2)

    if q.image_file_id:
        await callback.message.answer_photo(q.image_file_id, caption=text[:900], reply_markup=b.as_markup())
        # caption ограничен, поэтому если длинно — отдельным сообщением
        if len(text) > 900:
            await callback.message.answer(text, reply_markup=b.as_markup())
    else:
        await callback.message.answer(text, reply_markup=b.as_markup())

@router.callback_query(AdminCB.filter(F.action == "q_del"))
async def question_delete(callback: CallbackQuery, callback_data: AdminCB, sessionmaker: async_sessionmaker):
    await callback.answer()
    qid = callback_data.id

    async with sessionmaker() as s:
        repo = Repo(s)
        ok = await repo.delete_question(qid)

    await callback.message.answer("Удалено." if ok else "Не найдено.")
    # вернёмся к списку
    await callback.message.answer("Возвращаю к списку:", reply_markup=admin_menu_kb())

