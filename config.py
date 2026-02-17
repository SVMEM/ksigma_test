import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    bot_username: str
    admin_ids: set[int]
    db_url: str
    web_session_secret: str

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    bot_username = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
    admins_raw = os.getenv("SUPERADMIN_IDS", "").strip()
    admin_ids = {int(x) for x in admins_raw.split(",") if x.strip().isdigit()}
    db_url = os.getenv("DB_URL", "sqlite+aiosqlite:///./bot.db")
    web_session_secret = os.getenv("WEB_SESSION_SECRET", "change-me-in-env")
    if not token:
        raise RuntimeError("BOT_TOKEN is empty")
    return Config(
        bot_token=token,
        bot_username=bot_username,
        admin_ids=admin_ids,
        db_url=db_url,
        web_session_secret=web_session_secret,
    )
