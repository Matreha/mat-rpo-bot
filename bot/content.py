from __future__ import annotations

from aiogram import Bot
from aiogram.types import Message, User


def display_name(user: User) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or (f"@{user.username}" if user.username else str(user.id))


def student_label(row: dict) -> str:
    name = row["full_name"]
    if row.get("username"):
        return f"{name} (@{row['username']})"
    return f"{name} [{row['telegram_id']}]"


def extract_content(message: Message) -> tuple[str | None, str | None, str | None]:
    if message.photo:
        return message.caption, message.photo[-1].file_id, "photo"
    if message.document:
        return message.caption, message.document.file_id, "document"
    if message.text:
        return message.text, None, None
    return None, None, None


async def send_item(bot: Bot, chat_id: int, item: dict, header: str) -> None:
    text = header
    if item.get("body"):
        text = f"{header}\n\n{item['body']}"
    kind = item.get("file_kind")
    file_id = item.get("file_id")
    if kind == "photo" and file_id:
        await bot.send_photo(chat_id, file_id, caption=text[:1024])
    elif kind == "document" and file_id:
        await bot.send_document(chat_id, file_id, caption=text[:1024])
    else:
        await bot.send_message(chat_id, text)
