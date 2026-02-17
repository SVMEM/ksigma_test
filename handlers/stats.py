
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import async_sessionmaker
from aiogram.types.input_file import BufferedInputFile

from utils.callback_data import MenuCB
from db.repo import Repo
from services.stats_graphs import bar_topics_png
from keyboards.common import main_menu_kb

router = Router()

@router.callback_query(MenuCB.filter(F.action == "stats"))
async def stats(callback: CallbackQuery, sessionmaker: async_sessionmaker):
    await callback.answer()

    async with sessionmaker() as s:
        repo = Repo(s)
        user = await repo.get_or_create_user(tg_id=callback.from_user.id)
        total, correct = await repo.user_totals(user.id)
        pairs = await repo.solved_by_topic(user.id, limit=12)

    acc = (correct / total * 100.0) if total else 0.0
    text = f"Статистика:\nВсего решено: {total}\nВерно: {correct}\nТочность: {acc:.1f}%"

    await callback.message.edit_text(text, reply_markup=main_menu_kb())

    if pairs:
        png = bar_topics_png(pairs)
        await callback.message.answer_photo(
            BufferedInputFile(png, filename="topics.png"),
            caption="Решено по темам (топ)",
        )


