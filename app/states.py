from aiogram.fsm.state import State, StatesGroup


class ExchangeFlow(StatesGroup):
    choosing_direction = State()
    entering_amount = State()
    choosing_office = State()
    entering_date = State()
    entering_username = State()
    confirming = State()