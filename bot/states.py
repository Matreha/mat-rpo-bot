from aiogram.fsm.state import State, StatesGroup


class AddHomework(StatesGroup):
    title = State()
    content = State()
    audience = State()


class AddMaterial(StatesGroup):
    title = State()
    content = State()


class ScheduleLesson(StatesGroup):
    student = State()
    date = State()
    time = State()
    topic = State()
