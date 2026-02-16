from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Draft
from app.states import ExchangeFlow
from app.utils import parse_amount
from app.keyboards import kb_offices
from app.infrastructure.crm_client import get_crm_client, CRMTemporaryError, CRMPermanentError

router = Router()


@router.message(ExchangeFlow.entering_amount)
async def enter_amount(message: Message, state: FSMContext, session: AsyncSession):
    try:
        amount = parse_amount(message.text)
    except Exception:
        await message.answer(
            "Введите число больше 0.\n"
            "Можно использовать дробную часть (например: 1500 или 1500.50)."
        )
        return

    tg_id = message.from_user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        draft = Draft(telegram_user_id=tg_id, last_step="start")
        session.add(draft)

    draft.give_amount = float(amount)
    draft.last_step = "amount"
    draft.updated_at = datetime.utcnow()
    await session.commit()

    crm = get_crm_client()
    try:
        offices = await crm.get_offices()
    except (CRMTemporaryError, CRMPermanentError):
        await message.answer(
            "Сейчас не могу получить список офисов. Попробуйте чуть позже или напишите менеджеру @coinpointlara."
        )
        return
    except Exception:
        await message.answer(
            "Произошла ошибка при получении офисов. Попробуйте чуть позже."
        )
        return

    await message.answer(
        "Выберите, пожалуйста, где вам удобнее провести обмен",
        reply_markup=kb_offices(offices),
    )

    await state.set_state(ExchangeFlow.choosing_office)