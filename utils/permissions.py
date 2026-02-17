from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import async_sessionmaker
from db.repo import Repo

Event = Message | CallbackQuery

class IsSuperAdmin(BaseFilter):
    def __init__(self, superadmin_ids: set[int]):
        self.superadmin_ids = superadmin_ids

    async def __call__(self, event: Event) -> bool:
        uid = event.from_user.id if event.from_user else 0
        return uid in self.superadmin_ids

class IsDbAdmin(BaseFilter):
    def __init__(self, sessionmaker: async_sessionmaker):
        self.sessionmaker = sessionmaker

    async def __call__(self, event: Event) -> bool:
        uid = event.from_user.id if event.from_user else 0
        async with self.sessionmaker() as s:
            repo = Repo(s)
            return await repo.is_admin(uid)