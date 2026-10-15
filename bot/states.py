from aiogram.fsm.state import State, StatesGroup


class AddHomework(StatesGroup):
    title = State()
    content = State()
    audience = State()


class AddMaterial(StatesGroup):
    title = State()
    content = State()
    audience = State()


class ScheduleLesson(StatesGroup):
    student = State()
    date = State()
    time = State()
    topic = State()


class RescheduleLesson(StatesGroup):
    date = State()
    time = State()
