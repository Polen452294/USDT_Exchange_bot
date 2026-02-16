from __future__ import annotations

from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Draft
from app.infrastructure.crm_client import get_crm_client

router = Router()


async def _send_crm_event(draft: Draft, action: str) -> None:
    crm = get_crm_client()
    payload = {
        "event_type": "nudge4",
        "action": action,
        "telegram_user_id": int(draft.telegram_user_id),
        "client_request_id": draft.client_request_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        await crm.send_event(
            payload,
            idempotency_key=f"n4:{draft.telegram_user_id}:{action}:{int(datetime.utcnow().timestamp())}",
        )
    except Exception:
        return


@router.callback_query(F.data == "n4:yes")
async def n4_yes(cb: CallbackQuery, session: AsyncSession):
    await cb.answer()

    tg_id = cb.from_user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        return

    if draft.nudge4_answer is not None:
        return

    draft.nudge4_answer = "yes"
    draft.updated_at = datetime.utcnow()
    await session.commit()

    await _send_crm_event(draft, "yes")

    await cb.message.answer("Отлично ✅ Передал менеджеру, он свяжется с вами.")