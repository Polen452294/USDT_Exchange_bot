from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards import kb_next
from app.models import Draft
from app.states import ExchangeFlow

router = Router()


@router.callback_query(ExchangeFlow.choosing_office, F.data.startswith("office:"))
async def choose_office(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    office_id = cb.data.split(":", 1)[1]
    tg_id = cb.from_user.id

    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    draft.office_id = office_id
    draft.last_step = "office"
    await session.commit()

    await cb.message.answer(
    "Когда вам удобно получить наличные? По умолчанию стоит сегодняшняя дата — "
    "можете оставить её и нажать «Далее». Или нажмите на поле и введите желаемую дату\n"
    "Формат: дд.мм.гггг",
    reply_markup=kb_next(),
    )
    await state.set_state(ExchangeFlow.entering_date)