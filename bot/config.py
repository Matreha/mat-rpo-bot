from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _parse_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part:
            ids.add(int(part))
    return frozenset(ids)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    tz: ZoneInfo
    db_path: str


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Укажите BOT_TOKEN в файле .env")
    admin_ids = _parse_ids(os.getenv("ADMIN_IDS", ""))
    if not admin_ids:
        raise RuntimeError("Укажите ADMIN_IDS в файле .env (Telegram ID учителя)")
    tz_name = os.getenv("TZ", "Europe/Moscow").strip() or "Europe/Moscow"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root, "data")
    os.makedirs(data_dir, exist_ok=True)
    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        tz=ZoneInfo(tz_name),
        db_path=os.path.join(data_dir, "bot.db"),
    )
