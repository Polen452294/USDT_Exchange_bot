from __future__ import annotations

from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.crm_client import get_crm_client
from app.models import Request

router = Router()


async def _send_crm_event(req: Request, action: str) -> None:
    crm = get_crm_client()
    payload = {
        "event_type": "nudge1",
        "action": action,
        "telegram_user_id": int(req.telegram_user_id),
        "client_request_id": req.client_request_id,
        "crm_request_id": req.crm_request_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        await crm.send_event(
            payload,
            idempotency_key=f"n1:{req.telegram_user_id}:{req.client_request_id}:{action}:{int(datetime.utcnow().timestamp())}",
        )
    except Exception:
        return


@router.callback_query(F.data.startswith("n1:"))
async def n1_click(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    action = cb.data.split(":", 1)[1]
    tg_id = cb.from_user.id

    req = await session.scalar(
        select(Request).where(Request.telegram_user_id == tg_id).order_by(Request.id.desc())
    )
    if req is None:
        await cb.message.answer("Заявка не найдена. Нажмите /start чтобы создать новую.")
        return

    if req.nudge1_answer is not None:
        return

    if action == "yes":
        req.nudge1_answer = "actual"
        req.nudge1_sent_at = req.nudge1_sent_at or datetime.utcnow()
        await session.commit()
        await _send_crm_event(req, "actual")
        await cb.message.answer("Отлично ✅ Передал менеджеру, он свяжется с вами.")
        return

    if action == "no":
        req.nudge1_answer = "not_actual"
        req.nudge1_sent_at = req.nudge1_sent_at or datetime.utcnow()
        await session.commit()
        await _send_crm_event(req, "not_actual")
        await cb.message.answer("Понял ✅ Если понадобится обмен — можете начать заново через /start.")
        return

    if action == "manager":
        req.nudge1_answer = "manager"
        req.nudge1_sent_at = req.nudge1_sent_at or datetime.utcnow()
        await session.commit()
        await _send_crm_event(req, "manager")
        await cb.message.answer("Конечно. Напишите менеджеру напрямую: @coinpointlara")
        return