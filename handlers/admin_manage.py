import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import async_sessionmaker

from db.repo import Repo
from states import SuperAdminSG

router = Router()


def _parse_id_arg(text: str) -> int | None:
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _broadcast_confirm_kb():
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить всем", callback_data="bc_send")
    b.button(text="❌ Отменить", callback_data="bc_cancel")
    b.adjust(1)
    return b.as_markup()


@router.message(Command("subjects"))
async def subjects_list(message: Message, sessionmaker: async_sessionmaker):
    async with sessionmaker() as s:
        repo = Repo(s)
        subjects = await repo.list_subjects()
    if not subjects:
        await message.answer("Subjects пусто.")
        return
    txt = "Subjects:\n" + "\n".join([f"{x.id}: {x.code} — {x.name}" for x in subjects])
    await message.answer(txt)


@router.message(F.text.startswith("/add_subject"))
async def add_subject(message: Message, sessionmaker: async_sessionmaker):
    # /add_subject biology Биология
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /add_subject code name\nПример: /add_subject biology Биология")
        return
    code, name = parts[1], parts[2]

    async with sessionmaker() as s:
        repo = Repo(s)
        if await repo.subject_exists(code):
            await message.answer("Такой subject code уже существует.")
            return
        sid = await repo.create_subject(code=code, name=name)

    await message.answer(f"Добавлен subject id={sid}: {code} — {name}")


@router.message(Command("add_topic"))
async def add_topic(message: Message, sessionmaker: async_sessionmaker):
    # /add_topic biology Анатомия человека
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /add_topic subject_code topic_name\nПример: /add_topic biology Анатомия человека")
        return

    subject_code, topic_name = parts[1], parts[2]

    async with sessionmaker() as s:
        repo = Repo(s)
        subj = await repo.get_subject_by_code(subject_code)
        if subj is None:
            await message.answer("Subject не найден. Сначала создай его: /add_subject ...")
            return
        tid = await repo.create_topic(subject_id=subj.id, name=topic_name)

    await message.answer(f"Добавлена тема id={tid} в subject={subject_code}: {topic_name}")


@router.message(F.text.startswith("/admins"))
async def admins_list(message: Message, sessionmaker: async_sessionmaker):
    async with sessionmaker() as s:
        repo = Repo(s)
        ids = await repo.list_admins()
    if not ids:
        await message.answer("Админов в БД пока нет.")
    else:
        await message.answer("Админы в БД:\n" + "\n".join(str(x) for x in ids))


@router.message(F.text.startswith("/add_admin"))
async def add_admin_cmd(message: Message, sessionmaker: async_sessionmaker):
    tg_id = _parse_id_arg(message.text)
    if tg_id is None:
        await message.answer("Использование: /add_admin 123456789")
        return
    async with sessionmaker() as s:
        repo = Repo(s)
        added = await repo.add_admin(tg_id=tg_id, added_by_tg_id=message.from_user.id)
    await message.answer("Добавлен." if added else "Этот tg_id уже админ.")


@router.message(F.text.startswith("/del_admin"))
async def del_admin_cmd(message: Message, sessionmaker: async_sessionmaker):
    tg_id = _parse_id_arg(message.text)
    if tg_id is None:
        await message.answer("Использование: /del_admin 123456789")
        return
    async with sessionmaker() as s:
        repo = Repo(s)
        removed = await repo.remove_admin(tg_id=tg_id)
    await message.answer("Удалён." if removed else "Такого админа нет.")


@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext, sessionmaker: async_sessionmaker):
    await state.clear()
    async with sessionmaker() as s:
        repo = Repo(s)
        total_users = len(await repo.list_user_tg_ids())
    await state.set_state(SuperAdminSG.broadcast_wait_text)
    await message.answer(
        "Режим рассылки.\n"
        f"Сейчас в базе пользователей: {total_users}\n\n"
        "Отправь текст сообщения для рассылки.\n"
        "Отмена: /broadcast_cancel"
    )


@router.message(Command("broadcast_cancel"))
async def broadcast_cancel_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Рассылка отменена.")


@router.message(StateFilter(SuperAdminSG.broadcast_wait_text), F.text)
async def broadcast_preview(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 3:
        await message.answer("Слишком короткий текст. Отправь нормальное сообщение.")
        return
    if len(text) > 3800:
        await message.answer("Слишком длинно. Лимит 3800 символов.")
        return

    await state.update_data(broadcast_text=text)
    await state.set_state(SuperAdminSG.broadcast_confirm)
    await message.answer(
        "Предпросмотр рассылки:\n\n"
        f"{text}\n\n"
        "Подтвердить отправку всем пользователям?",
        reply_markup=_broadcast_confirm_kb(),
    )


@router.message(StateFilter(SuperAdminSG.broadcast_wait_text))
async def broadcast_wait_text_hint(message: Message):
    await message.answer("Отправь текст сообщения для рассылки или /broadcast_cancel.")


@router.callback_query(StateFilter(SuperAdminSG.broadcast_confirm), F.data == "bc_cancel")
async def broadcast_cancel_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Отменено")
    await state.clear()
    await callback.message.edit_text("Рассылка отменена.")


@router.callback_query(StateFilter(SuperAdminSG.broadcast_confirm), F.data == "bc_send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext, sessionmaker: async_sessionmaker):
    await callback.answer()
    data = await state.get_data()
    text = (data.get("broadcast_text") or "").strip()
    if not text:
        await state.clear()
        await callback.message.edit_text("Текст рассылки не найден. Запусти заново: /broadcast")
        return

    await callback.message.edit_text("Запускаю рассылку...")

    async with sessionmaker() as s:
        repo = Repo(s)
        tg_ids = await repo.list_user_tg_ids()

    sent = 0
    failed = 0
    failed_ids: list[int] = []
    skipped_self = 0

    for tg_id in tg_ids:
        if callback.from_user and tg_id == callback.from_user.id:
            skipped_self += 1
            continue
        try:
            await callback.bot.send_message(chat_id=tg_id, text=text)
            sent += 1
            await asyncio.sleep(0.03)
        except TelegramRetryAfter as e:
            await asyncio.sleep(float(e.retry_after) + 0.2)
            try:
                await callback.bot.send_message(chat_id=tg_id, text=text)
                sent += 1
            except Exception:
                failed += 1
                if len(failed_ids) < 20:
                    failed_ids.append(tg_id)
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
            if len(failed_ids) < 20:
                failed_ids.append(tg_id)
        except Exception:
            failed += 1
            if len(failed_ids) < 20:
                failed_ids.append(tg_id)

    await state.clear()

    report = (
        "Рассылка завершена.\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}\n"
        f"Пропущено (ты сам): {skipped_self}"
    )
    if failed_ids:
        report += "\n\nПервые проблемные tg_id:\n" + ", ".join(str(x) for x in failed_ids)

    await callback.message.answer(report)


@router.message(StateFilter(SuperAdminSG.broadcast_confirm))
async def broadcast_wait_confirm_hint(message: Message):
    await message.answer("Используй кнопки подтверждения под предпросмотром или /broadcast_cancel.")
