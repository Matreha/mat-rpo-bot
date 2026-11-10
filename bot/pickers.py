from __future__ import annotations

import calendar
from datetime import date, datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

MONTHS_RU = (
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)

WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

TIME_STEP_MIN = 30
TIME_VISIBLE = 3


class CalCB(CallbackData, prefix="cal"):
    a: str  # d day, p prev, n next, i ignore
    y: int = 0
    m: int = 0
    d: int = 0


class ClockCB(CallbackData, prefix="clk"):
    a: str  # s select, l left, r right, b back calendar, i ignore
    v: int = 0


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def _blank(kind: str) -> InlineKeyboardButton:
    if kind == "cal":
        return InlineKeyboardButton(text=" ", callback_data=CalCB(a="i").pack())
    return InlineKeyboardButton(text=" ", callback_data=ClockCB(a="i").pack())


def calendar_kb(year: int, month: int, today: date) -> InlineKeyboardMarkup:
    title = f"{MONTHS_RU[month]} {year}"
    cur_y, cur_m = today.year, today.month
    prev_y, prev_m = _shift_month(year, month, -1)
    next_y, next_m = _shift_month(year, month, 1)

    nav = []
    if (year, month) > (cur_y, cur_m):
        nav.append(InlineKeyboardButton(text="‹", callback_data=CalCB(a="p", y=prev_y, m=prev_m).pack()))
    else:
        nav.append(_blank("cal"))
    nav.append(InlineKeyboardButton(text=title, callback_data=CalCB(a="i").pack()))
    nav.append(InlineKeyboardButton(text="›", callback_data=CalCB(a="n", y=next_y, m=next_m).pack()))

    rows: list[list[InlineKeyboardButton]] = [
        nav,
        [InlineKeyboardButton(text=w, callback_data=CalCB(a="i").pack()) for w in WEEKDAYS],
    ]

    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    for week in cal.monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(_blank("cal"))
                continue
            chosen = date(year, month, day)
            if chosen < today:
                row.append(InlineKeyboardButton(text="·", callback_data=CalCB(a="i").pack()))
            else:
                row.append(
                    InlineKeyboardButton(
                        text=str(day),
                        callback_data=CalCB(a="d", y=year, m=month, d=day).pack(),
                    )
                )
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def available_times(selected_date: date, now: datetime) -> list[int]:
    slots = list(range(0, 24 * 60, TIME_STEP_MIN))
    if selected_date > now.date():
        return slots
    if selected_date < now.date():
        return []
    current = now.hour * 60 + now.minute
    return [slot for slot in slots if slot > current]


def default_time_start(selected_date: date, now: datetime) -> int:
    slots = available_times(selected_date, now)
    if not slots:
        return 0
    prefer = 18 * 60
    for index, slot in enumerate(slots):
        if slot >= prefer:
            return index
    return 0


def time_scroll_kb(selected_date: date, now: datetime, start: int) -> InlineKeyboardMarkup:
    slots = available_times(selected_date, now)
    back = [InlineKeyboardButton(text="← Календарь", callback_data=ClockCB(a="b").pack())]
    if not slots:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="На сегодня свободного времени нет", callback_data=ClockCB(a="i").pack())],
                back,
            ]
        )

    max_start = max(0, len(slots) - TIME_VISIBLE)
    start = max(0, min(start, max_start))
    window = slots[start : start + TIME_VISIBLE]

    row: list[InlineKeyboardButton] = []
    if start > 0:
        row.append(
            InlineKeyboardButton(
                text="‹",
                callback_data=ClockCB(a="l", v=start - 1).pack(),
            )
        )
    else:
        row.append(_blank("clk"))

    for minutes in window:
        hour, minute = divmod(minutes, 60)
        row.append(
            InlineKeyboardButton(
                text=f"{hour:02d}:{minute:02d}",
                callback_data=ClockCB(a="s", v=minutes).pack(),
            )
        )

    if start < max_start:
        row.append(
            InlineKeyboardButton(
                text="›",
                callback_data=ClockCB(a="r", v=start + 1).pack(),
            )
        )
    else:
        row.append(_blank("clk"))

    return InlineKeyboardMarkup(inline_keyboard=[row, back])


def parse_state_date(raw: str) -> date:
    return date.fromisoformat(raw)
