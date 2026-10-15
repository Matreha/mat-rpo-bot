from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


class NavCB(CallbackData, prefix="nav"):
    to: str


class StudentCB(CallbackData, prefix="st"):
    action: str
    sid: int = 0


class ItemCB(CallbackData, prefix="it"):
    kind: str  # hw | mat | ls
    action: str
    iid: int = 0


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Ученики"), KeyboardButton(text="📅 Занятия")],
            [
                KeyboardButton(text="📝 Домашнее задание"),
                KeyboardButton(text="📚 Справочные материалы"),
            ],
        ],
        resize_keyboard=True,
    )


def student_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Домашнее задание")],
            [KeyboardButton(text="📚 Справочные материалы")],
            [KeyboardButton(text="📅 Мои занятия")],
        ],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def skip_or_cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пропустить")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def students_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Создать приглашение",
                    callback_data=StudentCB(action="invite").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Список учеников",
                    callback_data=StudentCB(action="list").pack(),
                )
            ],
        ]
    )


def homework_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить задание",
                    callback_data=ItemCB(kind="hw", action="add").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Список заданий",
                    callback_data=ItemCB(kind="hw", action="list").pack(),
                )
            ],
        ]
    )


def materials_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить материал",
                    callback_data=ItemCB(kind="mat", action="add").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Список материалов",
                    callback_data=ItemCB(kind="mat", action="list").pack(),
                )
            ],
        ]
    )


def lessons_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Назначить занятие",
                    callback_data=ItemCB(kind="ls", action="add").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Ближайшие занятия",
                    callback_data=ItemCB(kind="ls", action="list").pack(),
                )
            ],
        ]
    )


def audience_kb(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Всем ученикам",
                    callback_data=ItemCB(kind=kind, action="aud", iid=0).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Выбрать ученика",
                    callback_data=ItemCB(kind=kind, action="pick").pack(),
                )
            ],
        ]
    )


def browse_by_student_kb(students: list[tuple[int, str]], kind: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🌐 Общие (для всех)",
                callback_data=ItemCB(kind=kind, action="of", iid=0).pack(),
            )
        ]
    ]
    for sid, name in students:
        rows.append(
            [
                InlineKeyboardButton(
                    text=name,
                    callback_data=ItemCB(kind=kind, action="of", iid=sid).pack(),
                )
            ]
        )
    if len(rows) == 1 and not students:
        rows.append([InlineKeyboardButton(text="Нет учеников", callback_data="noop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def students_pick_kb(students: list[tuple[int, str]], action: str, kind: str = "st") -> InlineKeyboardMarkup:
    rows = []
    for sid, name in students:
        if kind in {"hw", "ls", "mat"}:
            data = ItemCB(kind=kind, action=action, iid=sid).pack()
        else:
            data = StudentCB(action=action, sid=sid).pack()
        rows.append([InlineKeyboardButton(text=name, callback_data=data)])
    if not rows:
        rows.append([InlineKeyboardButton(text="Нет учеников", callback_data="noop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_actions_kb(
    kind: str, iid: int, *, can_delete: bool, can_edit: bool = False
) -> InlineKeyboardMarkup | None:
    rows = []
    if can_edit:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✏️ Изменить дату и время",
                    callback_data=ItemCB(kind=kind, action="edit", iid=iid).pack(),
                )
            ]
        )
    if can_delete:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑 Удалить" if kind != "ls" else "🚫 Отменить занятие",
                    callback_data=ItemCB(kind=kind, action="del", iid=iid).pack(),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
