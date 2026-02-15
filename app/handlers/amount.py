from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards import kb_next, kb_offices
from app.models import Draft
from app.states import ExchangeFlow
from app.utils import parse_amount
from app.services.crm_client import CRMClientMock

router = Router()


@router.message(ExchangeFlow.entering_amount)
async def enter_amount(message: Message, state: FSMContext, session: AsyncSession):
    try:
        amount = parse_amount(message.text)
    except Exception:
        await message.answer("Введите число больше 0 (можно с точкой). Например: 1500 или 1500.50")
        return

    tg_id = message.from_user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        draft = Draft(telegram_user_id=tg_id, last_step="start")
        session.add(draft)

    draft.give_amount = float(amount)
    draft.last_step = "amount"
    await session.commit()

    await message.answer("Ок. Нажмите «Далее», чтобы выбрать офис.", reply_markup=kb_next())


@router.callback_query(ExchangeFlow.entering_amount, F.data == "next")
async def amount_next(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    crm = CRMClientMock()
    offices = crm.get_offices()

    await cb.message.answer("Выберите, пожалуйста, где вам удобнее провести обмен", reply_markup=kb_offices(offices))
    await state.set_state(ExchangeFlow.choosing_office)