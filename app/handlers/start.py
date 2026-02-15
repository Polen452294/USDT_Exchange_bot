from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        await session.commit()

    await message.answer(START_TEXT, reply_markup=kb_start())
    await state.set_state(ExchangeFlow.choosing_direction)


@router.callback_query(F.data.startswith("dir:"))
async def choose_dir(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    direction = cb.data.split(":", 1)[1]
    tg_id = cb.from_user.id

    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    draft.direction = Direction(direction)
    draft.client_request_id = None  # на всякий случай
    draft.last_step = "direction"
    await session.commit()

    await cb.message.answer("Введите, пожалуйста, сумму, которую вы отдаёте.")
    await state.set_state(ExchangeFlow.entering_amount)