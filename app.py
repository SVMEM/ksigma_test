# app.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import load_config
from db.session import make_engine, make_sessionmaker, init_db
from db.repo import Repo

from handlers import start, menu, solve
from handlers import admin as admin_handlers
from handlers import admin_manage as admin_manage_handlers

from utils.permissions import IsDbAdmin, IsSuperAdmin


logging.basicConfig(level=logging.INFO)


async def main() -> None:
    config = load_config()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    engine = make_engine(config.db_url)
    await init_db(engine)

    sm = make_sessionmaker(engine)

    # (Опционально, но рекомендую) — засеять супер-админов в таблицу admins,
    # чтобы они тоже проходили IsDbAdmin-фильтр и могли добавлять задания.
    async with sm() as s:
        repo = Repo(s)
        for sid in config.admin_ids:  # тут лежат SUPERADMIN_IDS (если ты так настроил config)
            await repo.add_admin(sid, added_by_tg_id=None)

    dp = Dispatcher()

    # DI: это позволит принимать sessionmaker в хэндлерах как аргумент
    dp["sessionmaker"] = sm
    
    dp["superadmin_ids"] = config.admin_ids

    # Public routers
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(solve.router)

    # Admin: добавление заданий (любой DB-админ)
    admin_handlers.router.message.filter(IsDbAdmin(sm))
    admin_handlers.router.callback_query.filter(IsDbAdmin(sm))
    dp.include_router(admin_handlers.router)

    # Superadmin: управление админами (только SUPERADMIN_IDS)
    admin_manage_handlers.router.message.filter(IsSuperAdmin(config.admin_ids))
    admin_manage_handlers.router.callback_query.filter(IsSuperAdmin(config.admin_ids))
    dp.include_router(admin_manage_handlers.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())