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
        "event_type": "nudge3",
        "action": action,
        "telegram_user_id": int(draft.telegram_user_id),
        "client_request_id": draft.client_request_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        await crm.send_event(
            payload,
            idempotency_key=f"n3:{draft.telegram_user_id}:{action}:{int(datetime.utcnow().timestamp())}",
        )
    except Exception:
        return


@router.callback_query(F.data.startswith("n3:"))
async def n3_click(cb: CallbackQuery, session: AsyncSession):
    await cb.answer()

    action = cb.data.split(":", 1)[1]
    tg_id = cb.from_user.id

    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        return

    if draft.nudge3_answer is not None:
        return

    draft.nudge3_answer = "yes" if action == "yes" else "no"
    await session.commit()

    await _send_crm_event(draft, draft.nudge3_answer)

    if draft.nudge3_answer == "yes":
        await cb.message.answer("Отлично ✅ Передал менеджеру, он поможет зафиксировать условия.")
    else:
        await cb.message.answer("Хорошо 👍 Если решите продолжить — нажмите /start.")