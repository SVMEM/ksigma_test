# states.py
from aiogram.fsm.state import StatesGroup, State


class RegisterSG(StatesGroup):
    full_name = State()
    grade_group = State()


class SolveSG(StatesGroup):
    choose_subject = State()         # шаг 0: предмет
    choose_topic = State()           # шаг 1: тема
    choose_subtopics_mode = State()  # шаг 2: все подтемы / выбрать
    choose_subtopics = State()       # шаг 3: выбор подтем (тогглы)
    solving = State()                # процесс решения (вопросы)


class AdminSG(StatesGroup):
    add_q_choose_subject = State()   # шаг 0: предмет
    add_q_choose_topic = State()     # шаг 1: тема
    add_q_choose_subtopic = State()  # шаг 2: подтема (выбор/создание/нет)
    add_q_type = State()             # шаг 3: single/multi
    add_q_text = State()             # шаг 4: текст вопроса
    add_q_image = State()            # шаг 5: фото (опционально)
    add_q_options = State()          # шаг 6: варианты A)...
    add_q_correct = State()          # шаг 7: правильные (B или B,C)
    add_q_expl = State()             # шаг 8: объяснение


class SuperAdminSG(StatesGroup):
    broadcast_wait_text = State()
    broadcast_confirm = State()
