from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.db import AsyncSessionLocal
from app.models import Request
from app.services.crm_events import send_request_nudge_event

log = logging.getLogger("nudge6")

router = Router()


@router.callback_query(F.data.startswith("n6_yes:") | F.data.startswith("n6_no:"))
async def on_nudge6_answer(call: CallbackQuery):
    if call.from_user is None:
        return

    data = call.data or ""
    try:
        action, req_id_s = data.split(":", 1)
        req_id = int(req_id_s)
    except Exception:
        await call.answer("Некорректные данные", show_alert=True)
        return

    answer = "YES" if action == "n6_yes" else "NO"
    now = datetime.utcnow()

    async with AsyncSessionLocal() as session:
        req = await session.get(Request, req_id)
        if req is None or int(req.telegram_user_id) != int(call.from_user.id):
            await call.answer("Заявка не найдена", show_alert=True)
            return

        if req.nudge6_answered_at is not None:
            await call.answer("Ответ уже получен")
            return

        req.nudge6_answer = answer
        req.nudge6_answered_at = now
        await session.commit()
        try:
            await send_request_nudge_event(req, "nudge5", action)
        except Exception:
            log.exception("CRM event failed: nudge5")

    if answer == "YES":
        await call.message.answer("Отлично. Передал менеджеру, он свяжется с вами в Telegram.")
    else:
        await call.message.answer("Хорошо, понял. Если понадобится помощь — пишите @coinpointlara.")

    await call.answer()