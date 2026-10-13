from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.db import Database


def format_when(iso: str, tz: ZoneInfo) -> str:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz).strftime("%d.%m.%Y в %H:%M")


def lesson_text(lesson: dict, tz: ZoneInfo, *, for_student: bool) -> str:
    when = format_when(lesson["starts_at"], tz)
    topic = f"\nТема: {lesson['topic']}" if lesson.get("topic") else ""
    if for_student:
        return f"Занятие по математике {when}.{topic}"
    return f"Занятие с {lesson['student_name']} {when}.{topic}"


async def dispatch_reminders(bot: Bot, db: Database, tz: ZoneInfo, admin_ids: frozenset[int]) -> None:
    now = datetime.now(tz)
    for lesson in await db.due_reminders():
        starts = datetime.fromisoformat(lesson["starts_at"])
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=tz)
        starts = starts.astimezone(tz)
        student_id = lesson["student_id"]
        lid = lesson["id"]

        async def notify(prefix: str) -> None:
            body = lesson_text(lesson, tz, for_student=True)
            try:
                await bot.send_message(student_id, f"{prefix}\n\n{body}")
            except Exception:
                pass
            admin_body = lesson_text(lesson, tz, for_student=False)
            for admin_id in admin_ids:
                try:
                    await bot.send_message(admin_id, f"{prefix}\n\n{admin_body}")
                except Exception:
                    pass

        remaining = starts - now
        if not lesson["notified_day"]:
            if timedelta(hours=23) <= remaining <= timedelta(hours=24, minutes=5):
                await notify("⏰ Напоминание: занятие через сутки.")
                await db.mark_notified(lid, "notified_day")
            elif remaining < timedelta(hours=23):
                await db.mark_notified(lid, "notified_day")

        lesson = await db.get_lesson(lid) or lesson
        remaining = starts - now
        if not lesson["notified_hour"]:
            if timedelta(minutes=50) <= remaining <= timedelta(hours=1, minutes=5):
                await notify("⏰ Напоминание: занятие через час.")
                await db.mark_notified(lid, "notified_hour")
            elif remaining < timedelta(minutes=50):
                await db.mark_notified(lid, "notified_hour")

        lesson = await db.get_lesson(lid) or lesson
        if not lesson["notified_start"] and now >= starts:
            await notify("🔔 Занятие начинается.")
            await db.mark_notified(lid, "notified_start")


def setup_scheduler(bot: Bot, db: Database, tz: ZoneInfo, admin_ids: frozenset[int]) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        dispatch_reminders,
        "interval",
        minutes=1,
        args=(bot, db, tz, admin_ids),
        id="lesson_reminders",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
