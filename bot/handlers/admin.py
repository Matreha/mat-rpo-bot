from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.content import extract_content, send_item, student_label
from bot.db import Database
from bot.keyboards import (
    ItemCB,
    admin_menu,
    audience_kb,
    cancel_kb,
    skip_or_cancel_kb,
    students_pick_kb,
)
from bot.scheduler import lesson_text
from bot.states import AddHomework, AddMaterial, RescheduleLesson, ScheduleLesson

router = Router()


def _guard_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.admin_ids


@router.callback_query(ItemCB.filter((F.kind == "hw") & (F.action == "add")))
async def hw_add_start(query: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not _guard_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AddHomework.title)
    await query.message.answer("Введите название задания.", reply_markup=cancel_kb())
    await query.answer()


@router.message(AddHomework.title, F.text, F.text != "❌ Отмена")
async def hw_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AddHomework.content)
    await message.answer(
        "Отправьте текст задания, фото или документ (можно с подписью).",
        reply_markup=cancel_kb(),
    )


@router.message(AddHomework.content)
async def hw_content(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        return
    body, file_id, file_kind = extract_content(message)
    if not body and not file_id:
        await message.answer("Нужен текст, фото или файл.")
        return
    await state.update_data(body=body, file_id=file_id, file_kind=file_kind)
    await state.set_state(AddHomework.audience)
    await message.answer("Кому выдать задание?", reply_markup=audience_kb("hw"))


@router.callback_query(AddHomework.audience, ItemCB.filter((F.kind == "hw") & (F.action == "aud")))
async def hw_audience_all(
    query: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not _guard_admin(query.from_user.id, settings):
        return
    data = await state.get_data()
    hid = await db.add_homework(
        data["title"], data.get("body"), data.get("file_id"), data.get("file_kind"), None
    )
    await state.clear()
    await query.message.answer(f"Задание «{data['title']}» выдано всем ученикам.", reply_markup=admin_menu())
    item = await db.get_homework(hid)
    for s in await db.list_students():
        try:
            await send_item(query.bot, s["telegram_id"], item, f"Новое домашнее задание: {item['title']}")
        except Exception:
            pass
    await query.answer()


@router.callback_query(AddHomework.audience, ItemCB.filter((F.kind == "hw") & (F.action == "pick")))
async def hw_pick_student(query: CallbackQuery, db: Database, settings: Settings) -> None:
    if not _guard_admin(query.from_user.id, settings):
        return
    students = await db.list_students()
    pairs = [(s["telegram_id"], student_label(s)) for s in students]
    await query.message.answer("Выберите ученика:", reply_markup=students_pick_kb(pairs, action="to", kind="hw"))
    await query.answer()


@router.callback_query(AddHomework.audience, ItemCB.filter((F.kind == "hw") & (F.action == "to")))
async def hw_audience_one(
    query: CallbackQuery,
    callback_data: ItemCB,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not _guard_admin(query.from_user.id, settings):
        return
    data = await state.get_data()
    hid = await db.add_homework(
        data["title"],
        data.get("body"),
        data.get("file_id"),
        data.get("file_kind"),
        callback_data.iid,
    )
    await state.clear()
    await query.message.answer(f"Задание «{data['title']}» выдано ученику.", reply_markup=admin_menu())
    item = await db.get_homework(hid)
    try:
        await send_item(query.bot, callback_data.iid, item, f"Новое домашнее задание: {item['title']}")
    except Exception:
        pass
    await query.answer()


@router.callback_query(ItemCB.filter((F.kind == "mat") & (F.action == "add")))
async def mat_add_start(query: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not _guard_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AddMaterial.title)
    await query.message.answer("Введите название материала.", reply_markup=cancel_kb())
    await query.answer()


@router.message(AddMaterial.title, F.text, F.text != "❌ Отмена")
async def mat_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AddMaterial.content)
    await message.answer(
        "Отправьте текст, ссылку, фото или документ.",
        reply_markup=cancel_kb(),
    )


@router.message(AddMaterial.content)
async def mat_content(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        return
    body, file_id, file_kind = extract_content(message)
    if not body and not file_id:
        await message.answer("Нужен текст, фото или файл.")
        return
    await state.update_data(body=body, file_id=file_id, file_kind=file_kind)
    await state.set_state(AddMaterial.audience)
    await message.answer("Кому добавить материал?", reply_markup=audience_kb("mat"))


@router.callback_query(AddMaterial.audience, ItemCB.filter((F.kind == "mat") & (F.action == "aud")))
async def mat_audience_all(
    query: CallbackQuery,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not _guard_admin(query.from_user.id, settings):
        return
    data = await state.get_data()
    mid = await db.add_material(
        data["title"], data.get("body"), data.get("file_id"), data.get("file_kind"), None
    )
    await state.clear()
    await query.message.answer(
        f"Материал «{data['title']}» добавлен всем ученикам.",
        reply_markup=admin_menu(),
    )
    item = await db.get_material(mid)
    for s in await db.list_students():
        try:
            await send_item(query.bot, s["telegram_id"], item, f"Новый материал: {item['title']}")
        except Exception:
            pass
    await query.answer()


@router.callback_query(AddMaterial.audience, ItemCB.filter((F.kind == "mat") & (F.action == "pick")))
async def mat_pick_student(query: CallbackQuery, db: Database, settings: Settings) -> None:
    if not _guard_admin(query.from_user.id, settings):
        return
    students = await db.list_students()
    pairs = [(s["telegram_id"], student_label(s)) for s in students]
    await query.message.answer("Выберите ученика:", reply_markup=students_pick_kb(pairs, action="to", kind="mat"))
    await query.answer()


@router.callback_query(AddMaterial.audience, ItemCB.filter((F.kind == "mat") & (F.action == "to")))
async def mat_audience_one(
    query: CallbackQuery,
    callback_data: ItemCB,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not _guard_admin(query.from_user.id, settings):
        return
    data = await state.get_data()
    mid = await db.add_material(
        data["title"],
        data.get("body"),
        data.get("file_id"),
        data.get("file_kind"),
        callback_data.iid,
    )
    await state.clear()
    student = await db.get_user(callback_data.iid)
    who = student_label(student) if student else "ученику"
    await query.message.answer(f"Материал «{data['title']}» добавлен: {who}.", reply_markup=admin_menu())
    item = await db.get_material(mid)
    try:
        await send_item(query.bot, callback_data.iid, item, f"Новый материал: {item['title']}")
    except Exception:
        pass
    await query.answer()


@router.callback_query(ItemCB.filter((F.kind == "ls") & (F.action == "add")))
async def ls_add_start(query: CallbackQuery, state: FSMContext, db: Database, settings: Settings) -> None:
    if not _guard_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    students = await db.list_students()
    if not students:
        await query.message.answer("Сначала пригласите ученика.")
        await query.answer()
        return
    await state.set_state(ScheduleLesson.student)
    pairs = [(s["telegram_id"], student_label(s)) for s in students]
    await query.message.answer(
        "С кем назначить занятие?",
        reply_markup=students_pick_kb(pairs, action="pick", kind="ls"),
    )
    await query.answer()


@router.callback_query(ScheduleLesson.student, ItemCB.filter((F.kind == "ls") & (F.action == "pick")))
async def ls_pick(query: CallbackQuery, callback_data: ItemCB, state: FSMContext, settings: Settings) -> None:
    if not _guard_admin(query.from_user.id, settings):
        return
    await state.update_data(student_id=callback_data.iid)
    await state.set_state(ScheduleLesson.date)
    await query.message.answer(
        "Введите дату занятия в формате ДД.ММ.ГГГГ, например 02.09.2026",
        reply_markup=cancel_kb(),
    )
    await query.answer()


@router.message(ScheduleLesson.date, F.text, F.text != "❌ Отмена")
async def ls_date(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Не получилось прочитать дату. Пример: 02.09.2026")
        return
    await state.update_data(date=message.text.strip())
    await state.set_state(ScheduleLesson.time)
    await message.answer("Введите время в формате ЧЧ:ММ, например 18:30")


@router.message(ScheduleLesson.time, F.text, F.text != "❌ Отмена")
async def ls_time(message: Message, state: FSMContext, settings: Settings) -> None:
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Не получилось прочитать время. Пример: 18:30")
        return
    data = await state.get_data()
    starts = datetime.strptime(f"{data['date']} {message.text.strip()}", "%d.%m.%Y %H:%M")
    starts = starts.replace(tzinfo=settings.tz)
    if starts <= datetime.now(settings.tz):
        await message.answer("Это время уже прошло. Укажите дату и время заново, начиная с даты.")
        await state.set_state(ScheduleLesson.date)
        return
    await state.update_data(starts_at=starts.isoformat())
    await state.set_state(ScheduleLesson.topic)
    await message.answer(
        "Тема занятия (или нажмите «Пропустить»).",
        reply_markup=skip_or_cancel_kb(),
    )


@router.message(ScheduleLesson.topic, F.text, F.text != "❌ Отмена")
async def ls_topic(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    if not _guard_admin(message.from_user.id, settings):
        return
    data = await state.get_data()
    topic = None if message.text.strip() == "Пропустить" else message.text.strip()
    starts = datetime.fromisoformat(data["starts_at"])
    lid = await db.add_lesson(data["student_id"], starts, topic)
    await state.clear()
    lesson = await db.get_lesson(lid)
    await message.answer(
        "Занятие назначено.\n" + lesson_text(lesson, settings.tz, for_student=False),
        reply_markup=admin_menu(),
    )
    try:
        await message.bot.send_message(
            data["student_id"],
            "Вам назначено занятие.\n" + lesson_text(lesson, settings.tz, for_student=True)
            + "\n\nНапомню за сутки, за час и в момент начала.",
        )
    except Exception:
        await message.answer(
            "Не удалось сразу написать ученику (он мог не нажать Start). "
            "Напоминания всё равно будут отправлены, если диалог уже открыт."
        )


@router.callback_query(ItemCB.filter((F.kind == "ls") & (F.action == "edit")))
async def ls_edit_start(
    query: CallbackQuery,
    callback_data: ItemCB,
    state: FSMContext,
    db: Database,
    settings: Settings,
) -> None:
    if not _guard_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    lesson = await db.get_lesson(callback_data.iid)
    if not lesson or lesson["status"] != "scheduled":
        await query.answer("Занятие не найдено или уже отменено", show_alert=True)
        return
    await state.set_state(RescheduleLesson.date)
    await state.update_data(lesson_id=callback_data.iid)
    await query.message.answer(
        "Текущее время:\n"
        + lesson_text(lesson, settings.tz, for_student=False)
        + "\n\nВведите новую дату в формате ДД.ММ.ГГГГ, например 02.09.2026",
        reply_markup=cancel_kb(),
    )
    await query.answer()


@router.message(RescheduleLesson.date, F.text, F.text != "❌ Отмена")
async def ls_edit_date(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Не получилось прочитать дату. Пример: 02.09.2026")
        return
    await state.update_data(date=message.text.strip())
    await state.set_state(RescheduleLesson.time)
    await message.answer("Введите новое время в формате ЧЧ:ММ, например 18:30")


@router.message(RescheduleLesson.time, F.text, F.text != "❌ Отмена")
async def ls_edit_time(message: Message, state: FSMContext, db: Database, settings: Settings) -> None:
    if not _guard_admin(message.from_user.id, settings):
        return
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Не получилось прочитать время. Пример: 18:30")
        return
    data = await state.get_data()
    starts = datetime.strptime(f"{data['date']} {message.text.strip()}", "%d.%m.%Y %H:%M")
    starts = starts.replace(tzinfo=settings.tz)
    if starts <= datetime.now(settings.tz):
        await message.answer("Это время уже прошло. Укажите дату заново.")
        await state.set_state(RescheduleLesson.date)
        return
    old = await db.get_lesson(data["lesson_id"])
    ok = await db.update_lesson_starts(data["lesson_id"], starts)
    await state.clear()
    if not ok or not old:
        await message.answer("Не удалось изменить занятие. Возможно, его уже отменили.", reply_markup=admin_menu())
        return
    lesson = await db.get_lesson(data["lesson_id"])
    await message.answer(
        "Занятие перенесено.\n" + lesson_text(lesson, settings.tz, for_student=False),
        reply_markup=admin_menu(),
    )
    try:
        await message.bot.send_message(
            old["student_id"],
            "Занятие перенесено.\nБыло:\n"
            + lesson_text(old, settings.tz, for_student=True)
            + "\n\nСтало:\n"
            + lesson_text(lesson, settings.tz, for_student=True),
        )
    except Exception:
        await message.answer("Ученику не удалось сразу написать о переносе.")
