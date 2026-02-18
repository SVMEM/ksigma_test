# handlers/menu.py

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types.input_file import BufferedInputFile
from sqlalchemy.ext.asyncio import async_sessionmaker

from db.repo import Repo
from keyboards.menu import main_menu_kb
from services.stats_graphs import bar_topics_png

router = Router()


@router.message(StateFilter(None), Command("menu"))
async def show_menu(message: Message):
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


@router.message(StateFilter(None), F.text == "🧠 Решать тесты")
async def go_solve(message: Message, state: FSMContext, sessionmaker: async_sessionmaker):
    # Reuse solve entry flow directly instead of sending plain text "/solve".
    from handlers.solve import solve_cmd

    await solve_cmd(message, state, sessionmaker)


@router.message(StateFilter(None), F.text == "📊 Статистика")
async def go_stats(message: Message, sessionmaker: async_sessionmaker):
    async with sessionmaker() as s:
        repo = Repo(s)
        user = await repo.get_or_create_user(
            tg_id=message.from_user.id,
            full_name=message.from_user.full_name or "-",
            username=message.from_user.username,
        )
        total, correct = await repo.user_totals(user.id)
        pairs = await repo.solved_by_topic(user.id, limit=12)

    acc = (correct / total * 100.0) if total else 0.0
    text = (
        "Твоя статистика:\n"
        f"Всего решено: {total}\n"
        f"Верно: {correct}\n"
        f"Точность: {acc:.1f}%"
    )
    await message.answer(text, reply_markup=main_menu_kb())

    if pairs:
        png = bar_topics_png(pairs)
        await message.answer_photo(
            BufferedInputFile(png, filename="topics.png"),
            caption="Решено по темам (топ)",
        )


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def unknown_text(message: Message):
    # Catch unknown free text and keep UX inside main menu.
    await message.answer("Не понял сообщение. Выбери действие в меню 👇", reply_markup=main_menu_kb())
