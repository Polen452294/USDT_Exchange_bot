from __future__ import annotations
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.config import settings
from app.models import Draft
from app.keyboards import kb_start
from app.states import ExchangeFlow
from app.infrastructure.crm_client import get_crm_client

router = Router()


async def _send_crm_event(draft: Draft, action: str) -> None:
    crm = get_crm_client()
    payload = {
        "event_type": "nudge2",
        "action": action,
        "telegram_user_id": int(draft.telegram_user_id),
        "client_request_id": draft.client_request_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        await crm.send_event(payload, idempotency_key=f"n2:{draft.telegram_user_id}:{action}:{int(datetime.utcnow().timestamp())}")
    except Exception:
        return


@router.callback_query(F.data.startswith("n2:"))
async def n2_click(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    action = cb.data.split(":", 1)[1]
    tg_id = cb.from_user.id

    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        await cb.message.answer("Нажмите /start чтобы начать заново.", reply_markup=kb_start())
        return

    if action == "continue":
        draft.nudge2_answer = "continue"
        draft.updated_at = datetime.utcnow()
        await session.commit()

        await _send_crm_event(draft, "continue")

        if draft.direction and draft.give_amount and draft.office_id and draft.desired_date:
            from app.handlers.summary import send_summary
            await send_summary(cb.message, state, session, user_id=tg_id)
            return

        if not draft.give_amount:
            await cb.message.answer("Введите, пожалуйста, сумму, которую вы отдаёте.")
            await state.set_state(ExchangeFlow.entering_amount)
            return

        if not draft.office_id:
            await cb.message.answer("Нажмите /start чтобы продолжить выбор офиса.")
            return

        await cb.message.answer("Нажмите /start чтобы продолжить.")
        return

    if action == "manager":
        draft.nudge2_answer = "manager"
        draft.updated_at = datetime.utcnow()
        await session.commit()

        await _send_crm_event(draft, "manager")

        await cb.message.answer(
            "Передал запрос менеджеру ✅ Если нужно — можете написать напрямую: @coinpointlara"
        )
        return

    if action == "later":
        draft.nudge2_answer = "later"
        draft.nudge2_answered_at = datetime.utcnow()
        delay = int(getattr(settings, "nudge4_delay_seconds", 86400))
        draft.nudge4_planned_at = draft.nudge2_answered_at + timedelta(seconds=delay)
        draft.nudge4_sent_at = None
        draft.nudge4_answer = None
        draft.updated_at = datetime.utcnow()
        await session.commit()

        await _send_crm_event(draft, "later")

        await cb.message.answer("Хорошо, понял. Если решите продолжить — нажмите /start.")
        return