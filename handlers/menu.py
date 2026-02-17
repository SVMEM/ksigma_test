# handlers/menu.py

from aiogram import Router, F
from aiogram.types import Message

router = Router()


@router.message(F.text == "🧠 Решать тесты")
async def go_solve(message: Message):
    await message.answer("Запускаю решение тестов…")
    # просто вызываем /solve
    await message.answer("/solve")


@router.message(F.text == "📊 Статистика")
async def go_stats(message: Message):
    await message.answer("Статистика пока в разработке 📊")