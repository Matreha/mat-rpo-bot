from __future__ import annotations

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import Settings
from bot.db import Database
from bot.handlers import admin, common


def build_dispatcher(settings: Settings, db: Database) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp["settings"] = settings
    dp["db"] = db
    dp.include_router(common.router)
    dp.include_router(admin.router)
    return dp
