from __future__ import annotations

import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

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

HOUR_POS = {
    12: (0, 2),
    1: (0, 4),
    2: (1, 4),
    3: (2, 4),
    4: (3, 4),
    5: (4, 4),
    6: (4, 2),
    7: (4, 0),
    8: (3, 0),
    9: (2, 0),
    10: (1, 0),
    11: (0, 0),
}

MINUTE_AT_HOUR = {12: 0, 1: 5, 2: 10, 3: 15, 4: 20, 5: 25, 6: 30, 7: 35, 8: 40, 9: 45, 10: 50, 11: 55}


class CalCB(CallbackData, prefix="cal"):
    a: str  # d day, p prev, n next, i ignore
    y: int = 0
    m: int = 0
    d: int = 0


class ClockCB(CallbackData, prefix="clk"):
    a: str  # h hour, m minute, p period, b back calendar, n back hours, i ignore
    v: int = 0
    h: int = 0
    p: int = 0


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


def _face_rows(buttons: dict[tuple[int, int], InlineKeyboardButton], center: InlineKeyboardButton) -> list[list[InlineKeyboardButton]]:
    grid: dict[tuple[int, int], InlineKeyboardButton] = dict(buttons)
    grid[(2, 2)] = center
    rows = []
    for r in range(5):
        row = []
        for c in range(5):
            row.append(grid.get((r, c), _blank("clk")))
        rows.append(row)
    return rows


def hour_clock_kb(selected_date: date, now: datetime, *, pm: bool) -> InlineKeyboardMarkup:
    today = now.date()
    buttons: dict[tuple[int, int], InlineKeyboardButton] = {}
    for face in range(1, 13):
        hour24 = (0 if face == 12 else face) + (12 if pm else 0)
        disabled = selected_date < today or (selected_date == today and hour24 < now.hour)
        pos = HOUR_POS[face]
        label = f"{hour24:02d}"
        if disabled:
            buttons[pos] = InlineKeyboardButton(text="·", callback_data=ClockCB(a="i").pack())
        else:
            buttons[pos] = InlineKeyboardButton(
                text=label,
                callback_data=ClockCB(a="h", v=hour24, p=int(pm)).pack(),
            )
    center = InlineKeyboardButton(text="●", callback_data=ClockCB(a="i").pack())
    rows = _face_rows(buttons, center)
    rows.append(
        [
            InlineKeyboardButton(
                text="☀️ 00–11" if not pm else "00–11",
                callback_data=ClockCB(a="p", p=0).pack(),
            ),
            InlineKeyboardButton(
                text="🌙 12–23" if pm else "12–23",
                callback_data=ClockCB(a="p", p=1).pack(),
            ),
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="← Календарь", callback_data=ClockCB(a="b").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def minute_clock_kb(selected_date: date, hour24: int, now: datetime) -> InlineKeyboardMarkup:
    today = now.date()
    buttons: dict[tuple[int, int], InlineKeyboardButton] = {}
    for face, minute in MINUTE_AT_HOUR.items():
        disabled = selected_date < today or (
            selected_date == today and (hour24 < now.hour or (hour24 == now.hour and minute <= now.minute))
        )
        pos = HOUR_POS[face]
        label = f"{minute:02d}"
        if disabled:
            buttons[pos] = InlineKeyboardButton(text="·", callback_data=ClockCB(a="i").pack())
        else:
            buttons[pos] = InlineKeyboardButton(
                text=label,
                callback_data=ClockCB(a="m", v=minute, h=hour24).pack(),
            )
    center = InlineKeyboardButton(text=f"{hour24:02d}:", callback_data=ClockCB(a="i").pack())
    rows = _face_rows(buttons, center)
    rows.append(
        [InlineKeyboardButton(text="← Часы", callback_data=ClockCB(a="n", p=int(hour24 >= 12)).pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_state_date(raw: str) -> date:
    return date.fromisoformat(raw)
