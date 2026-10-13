from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from bot.config import load_settings
from bot.db import Database
from bot.handlers import build_dispatcher
from bot.scheduler import setup_scheduler


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    db = Database(settings.db_path, settings.tz)
    await db.connect()
    bot = Bot(settings.bot_token)
    dp = build_dispatcher(settings, db)
    scheduler = setup_scheduler(bot, db, settings.tz, settings.admin_ids)
    scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
