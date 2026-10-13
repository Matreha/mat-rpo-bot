from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.content import display_name, send_item, student_label
from bot.db import Database
from bot.keyboards import (
    ItemCB,
    StudentCB,
    admin_menu,
    homework_admin_kb,
    item_actions_kb,
    lessons_admin_kb,
    materials_admin_kb,
    student_menu,
    students_admin_kb,
    students_pick_kb,
)
from bot.scheduler import lesson_text

router = Router()


def _is_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.admin_ids


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, db: Database, settings: Settings, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    assert user
    if _is_admin(user.id, settings):
        await db.upsert_user(user.id, "admin", display_name(user), user.username)
        await message.answer(
            "Здравствуйте! Это кабинет учителя.\n\n"
            "Здесь можно приглашать учеников, выдавать домашние задания, "
            "публиковать справочные материалы и назначать занятия — ученик получит уведомления.",
            reply_markup=admin_menu(),
        )
        return

    existing = await db.get_user(user.id)
    token = (command.args or "").strip()
    if token.startswith("inv_"):
        token = token[4:]
    if token:
        ok = await db.consume_invite(token, user.id)
        if not ok and not existing:
            await message.answer(
                "Приглашение недействительно или уже использовано. "
                "Попросите учителя прислать новую ссылку."
            )
            return
        if ok or not existing:
            await db.upsert_user(user.id, "student", display_name(user), user.username)
            await message.answer(
                "Добро пожаловать на занятия по математике!\n\n"
                "Откройте разделы ниже: домашние задания, справочные материалы и расписание.",
                reply_markup=student_menu(),
            )
            for admin_id in settings.admin_ids:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"Новый ученик: {student_label(await db.get_user(user.id))}",
                    )
                except Exception:
                    pass
            return

    if existing and existing["role"] == "student":
        await db.upsert_user(user.id, "student", display_name(user), user.username)
        await message.answer("Снова здравствуйте!", reply_markup=student_menu())
        return

    await message.answer(
        "Этот бот только для учеников, приглашённых учителем.\n"
        "Попросите ссылку-приглашение и откройте её в Telegram."
    )


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cancel_any(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    kb = admin_menu() if _is_admin(message.from_user.id, settings) else student_menu()
    await message.answer("Действие отменено.", reply_markup=kb)


@router.callback_query(F.data == "noop")
async def noop(query: CallbackQuery) -> None:
    await query.answer("Список пуст")


@router.message(F.text == "👥 Ученики")
async def admin_students(message: Message, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    await message.answer("Ученики и приглашения:", reply_markup=students_admin_kb())


@router.callback_query(StudentCB.filter(F.action == "invite"))
async def make_invite(query: CallbackQuery, db: Database, settings: Settings) -> None:
    if not _is_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    token = await db.create_invite()
    me = await query.bot.get_me()
    link = f"https://t.me/{me.username}?start=inv_{token}"
    await query.message.answer(
        "Ссылка-приглашение (одноразовая):\n"
        f"{link}\n\n"
        "Отправьте её ученику. После перехода он появится в списке."
    )
    await query.answer()


@router.callback_query(StudentCB.filter(F.action == "list"))
async def list_students(query: CallbackQuery, db: Database, settings: Settings) -> None:
    if not _is_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    students = await db.list_students()
    if not students:
        await query.message.answer("Пока нет учеников. Создайте приглашение.")
        await query.answer()
        return
    lines = ["Ученики (нажмите, чтобы удалить):"]
    pairs = []
    for s in students:
        lines.append(f"• {student_label(s)}")
        pairs.append((s["telegram_id"], student_label(s)))
    await query.message.answer(
        "\n".join(lines),
        reply_markup=students_pick_kb(pairs, action="del"),
    )
    await query.answer()


@router.callback_query(StudentCB.filter(F.action == "del"))
async def delete_student(query: CallbackQuery, callback_data: StudentCB, db: Database, settings: Settings) -> None:
    if not _is_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    ok = await db.remove_student(callback_data.sid)
    await query.answer("Ученик удалён" if ok else "Не найден", show_alert=True)
    if ok:
        await query.message.answer("Ученик убран из списка. Чтобы войти снова, ему понадобится новое приглашение.")


@router.message(F.text == "📝 Домашнее задание")
async def homework_entry(message: Message, db: Database, settings: Settings) -> None:
    if _is_admin(message.from_user.id, settings):
        await message.answer("Домашние задания:", reply_markup=homework_admin_kb())
        return
    user = await db.get_user(message.from_user.id)
    if not user or user["role"] != "student":
        return
    items = await db.list_homework(message.from_user.id)
    if not items:
        await message.answer("Пока нет домашних заданий.")
        return
    await message.answer("Ваши домашние задания:")
    for item in items:
        audience = "для всех" if item["student_id"] is None else "личное"
        header = f"📝 {item['title']} ({audience})"
        await send_item(message.bot, message.chat.id, item, header)


@router.message(F.text == "📚 Справочные материалы")
async def materials_entry(message: Message, db: Database, settings: Settings) -> None:
    if _is_admin(message.from_user.id, settings):
        await message.answer("Справочные материалы:", reply_markup=materials_admin_kb())
        return
    user = await db.get_user(message.from_user.id)
    if not user or user["role"] != "student":
        return
    items = await db.list_materials()
    if not items:
        await message.answer("Пока нет справочных материалов.")
        return
    await message.answer("Справочные материалы:")
    for item in items:
        await send_item(message.bot, message.chat.id, item, f"📚 {item['title']}")


@router.message(F.text == "📅 Занятия")
async def lessons_admin_entry(message: Message, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        return
    await message.answer("Расписание занятий:", reply_markup=lessons_admin_kb())


@router.message(F.text == "📅 Мои занятия")
async def lessons_student_entry(message: Message, db: Database, settings: Settings) -> None:
    if _is_admin(message.from_user.id, settings):
        return
    user = await db.get_user(message.from_user.id)
    if not user or user["role"] != "student":
        return
    lessons = await db.list_lessons(student_id=message.from_user.id)
    if not lessons:
        await message.answer("Ближайших занятий нет.")
        return
    lines = ["Ваши ближайшие занятия:"]
    for lesson in lessons:
        lines.append("• " + lesson_text(lesson, settings.tz, for_student=True).replace("\n", " — "))
    await message.answer("\n".join(lines))


@router.callback_query(ItemCB.filter((F.kind == "hw") & (F.action == "list")))
async def admin_hw_list(query: CallbackQuery, db: Database, settings: Settings) -> None:
    if not _is_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    items = await db.list_homework()
    if not items:
        await query.message.answer("Заданий ещё нет.")
        await query.answer()
        return
    await query.message.answer("Последние домашние задания:")
    for item in items:
        who = "всем" if item["student_id"] is None else f"ученику {item['student_id']}"
        header = f"📝 {item['title']} ({who})"
        await send_item(query.bot, query.message.chat.id, item, header)
        kb = item_actions_kb("hw", item["id"], can_delete=True)
        if kb:
            await query.message.answer("Действия:", reply_markup=kb)
    await query.answer()


@router.callback_query(ItemCB.filter((F.kind == "mat") & (F.action == "list")))
async def admin_mat_list(query: CallbackQuery, db: Database, settings: Settings) -> None:
    if not _is_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    items = await db.list_materials()
    if not items:
        await query.message.answer("Материалов ещё нет.")
        await query.answer()
        return
    await query.message.answer("Справочные материалы:")
    for item in items:
        await send_item(query.bot, query.message.chat.id, item, f"📚 {item['title']}")
        kb = item_actions_kb("mat", item["id"], can_delete=True)
        if kb:
            await query.message.answer("Действия:", reply_markup=kb)
    await query.answer()


@router.callback_query(ItemCB.filter((F.kind == "ls") & (F.action == "list")))
async def admin_ls_list(query: CallbackQuery, db: Database, settings: Settings) -> None:
    if not _is_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    lessons = await db.list_lessons()
    if not lessons:
        await query.message.answer("Ближайших занятий нет.")
        await query.answer()
        return
    await query.message.answer("Ближайшие занятия:")
    for lesson in lessons:
        text = lesson_text(lesson, settings.tz, for_student=False)
        await query.message.answer(text, reply_markup=item_actions_kb("ls", lesson["id"], can_delete=True))
    await query.answer()


@router.callback_query(ItemCB.filter(F.action == "del"))
async def delete_item(query: CallbackQuery, callback_data: ItemCB, db: Database, settings: Settings) -> None:
    if not _is_admin(query.from_user.id, settings):
        await query.answer("Нет доступа", show_alert=True)
        return
    if callback_data.kind == "hw":
        ok = await db.delete_homework(callback_data.iid)
        await query.answer("Задание удалено" if ok else "Не найдено", show_alert=True)
    elif callback_data.kind == "mat":
        ok = await db.delete_material(callback_data.iid)
        await query.answer("Материал удалён" if ok else "Не найден", show_alert=True)
    elif callback_data.kind == "ls":
        lesson = await db.get_lesson(callback_data.iid)
        ok = await db.cancel_lesson(callback_data.iid)
        await query.answer("Занятие отменено" if ok else "Не найдено", show_alert=True)
        if ok and lesson:
            try:
                await query.bot.send_message(
                    lesson["student_id"],
                    "Занятие отменено учителем:\n"
                    + lesson_text(lesson, settings.tz, for_student=True),
                )
            except Exception:
                pass
    else:
        await query.answer()
