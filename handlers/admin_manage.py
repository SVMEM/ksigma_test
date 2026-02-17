from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker
from db.repo import Repo
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession



router = Router()

def _parse_id_arg(text: str) -> int | None:
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None

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