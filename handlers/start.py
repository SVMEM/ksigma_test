# handlers/start.py

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import async_sessionmaker

from db.repo import Repo
from keyboards.menu import main_menu_kb

router = Router()


@router.message(CommandStart())
async def start_cmd(
    message: Message,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    await state.clear()

    async with sessionmaker() as s:
        repo = Repo(s)
        await repo.get_or_create_user(
            tg_id=message.from_user.id,
            full_name=message.from_user.full_name or "-",
            username=message.from_user.username,
        )

    await message.answer(
        "Привет 👋\n\nВыбери действие:",
        reply_markup=main_menu_kb(),
    )
