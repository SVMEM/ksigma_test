from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .base import Base

def make_engine(db_url: str):
    return create_async_engine(db_url, echo=False)

def make_sessionmaker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)

async def init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight SQLite migration for existing DBs.
        cols = await conn.exec_driver_sql("PRAGMA table_info(users)")
        user_cols = {row[1] for row in cols.fetchall()}
        if "username" not in user_cols:
            await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN username VARCHAR(64)")
