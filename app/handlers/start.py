from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from datetime import timedelta
from app.config import settings

from app.models import Direction
from app.keyboards import kb_start
from app.models import Draft
from app.states import ExchangeFlow

router = Router()

START_TEXT = (
    "Привет!\n"
    "Я помогу быстро оформить заявку на обмен USDT ↔ наличные в Турции за несколько шагов:\n"
    "➔ выберите направление обмена\n"
    "➔ укажите сумму, которую отдаете\n"
    "➔ выберите офис в Анталье или Стамбуле\n"
    "➔ выберите желаемую дату сделки\n"
    "Потом я покажу вам условия обмена и, если вы согласны, попрошу подтвердить их.\n"
    "После наш менеджер свяжется с вами в Telegram для обсуждения деталей. "
    "Если нужно быстро задать вопрос — пишите менеджеру напрямую @coinpointlara.\n\n"
    "Нажмите кнопку ниже, чтобы начать 👇"
)


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()

    tg_id = message.from_user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        draft = Draft(telegram_user_id=tg_id, last_step="start")
        session.add(draft)
    else:
        draft.nudge2_planned_at = None
        draft.nudge2_sent_at = None
        draft.nudge2_answer = None

        draft.last_step = "start"
        draft.updated_at = datetime.utcnow()

    await session.commit()

    await message.answer(START_TEXT, reply_markup=kb_start())
    await state.set_state(ExchangeFlow.choosing_direction)


@router.callback_query(F.data.startswith("dir:"))
async def choose_dir(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    direction_value = cb.data.split(":", 1)[1]
    direction = Direction(direction_value)

    tg_id = cb.from_user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        draft = Draft(telegram_user_id=tg_id, last_step="start")
        session.add(draft)

    draft.direction = direction
    draft.last_step = "amount_wait"
    draft.updated_at = datetime.utcnow()
    delay = int(getattr(settings, "nudge2_delay_seconds", 900))
    draft.nudge2_planned_at = datetime.utcnow() + timedelta(seconds=delay)
    draft.nudge2_sent_at = None
    draft.nudge2_answer = None
    await session.commit()

    await cb.message.answer("Введите, пожалуйста, сумму, которую вы отдаёте.")
    await state.set_state(ExchangeFlow.entering_amount)