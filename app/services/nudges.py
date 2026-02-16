from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.infrastructure.crm_client import get_crm_client
from app.keyboards import kb_nudge1, kb_nudge2
from app.models import Draft, Request

log = logging.getLogger("nudges")

NUDGE1_TEXT = (
    "Извините, похоже, менеджер задерживается. Это редко бывает, но я хочу помочь.\n"
    "Ваша заявка всё ещё актуальна?"
)

NUDGE2_TEXT = (
    "Похоже, вы отвлеклись.\n"
    "Если хотите, я могу продолжить с того места, где вы остановились. "
    "Нажмите «Продолжить», и я покажу сводку и текущий курс."
)

STEPS_FOR_NUDGE2 = [
    "amount_wait",
    "amount",
    "office",
    "date",
    "date_default",
    "username_auto",
    "username_manual",
    "summary",
]

_TERMINAL_STATUSES = {"done", "completed", "paid", "fixed", "closed"}
_CONTACTED_STATUSES = {"in_work", "in_progress", "contacted", "working"} | _TERMINAL_STATUSES


def _crm_contacted(payload: dict) -> bool:
    status = str(payload.get("status") or "").strip().lower()
    if status in _CONTACTED_STATUSES:
        return True

    flags = payload.get("flags")
    if isinstance(flags, dict):
        for k in ("contacted", "in_work", "manager_contacted", "inProgress"):
            if flags.get(k) is True:
                return True

    return False


class NudgeService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def tick(self) -> None:
        await self._check_nudge1()
        await self._check_nudge2()

    async def _check_nudge1(self) -> None:
        now = datetime.utcnow()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(
                    Request.id,
                    Request.telegram_user_id,
                    Request.crm_request_id,
                )
                .where(Request.nudge1_answer.is_(None))
                .where(Request.nudge1_sent_at.is_(None))
                .where(Request.nudge1_planned_at.is_not(None))
                .where(Request.nudge1_planned_at <= now)
                .order_by(Request.id.asc())
                .limit(50)
            )

            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            log.info("n1 candidates=%d", len(rows))

            crm = get_crm_client()

            for req_id, uid, crm_request_id in rows:
                uid = int(uid)

                try:
                    if crm_request_id:
                        st = await crm.check_status(str(crm_request_id))
                        if isinstance(st, dict) and _crm_contacted(st):
                            req = await session.get(Request, req_id)
                            if req and req.nudge1_sent_at is None and req.nudge1_answer is None:
                                req.nudge1_sent_at = now
                                req.nudge1_answer = "skip_contacted"
                                await session.commit()
                            continue

                    await self.bot.send_message(
                        chat_id=uid,
                        text=NUDGE1_TEXT,
                        reply_markup=kb_nudge1(),
                    )

                    req = await session.get(Request, req_id)
                    if req and req.nudge1_sent_at is None:
                        req.nudge1_sent_at = datetime.utcnow()
                        await session.commit()

                    log.info("n1 sent: uid=%s req_id=%s", uid, req_id)

                except Exception:
                    await session.rollback()
                    log.exception("n1 send failed: uid=%s req_id=%s", uid, req_id)

    async def _check_nudge2(self) -> None:
        now = datetime.utcnow()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(
                    Draft.id,
                    Draft.telegram_user_id,
                    Draft.last_step,
                )
                .where(Draft.last_step.in_(STEPS_FOR_NUDGE2))
                .where(Draft.give_amount.is_not(None))
                .where(Draft.nudge2_answer.is_(None))
                .where(Draft.nudge2_sent_at.is_(None))
                .where(Draft.nudge2_planned_at.is_not(None))
                .where(Draft.nudge2_planned_at <= now)
            )

            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            log.info("n2 candidates=%d", len(rows))

            for draft_id, uid, last_step in rows:
                uid = int(uid)

                try:
                    await self.bot.send_message(
                        chat_id=uid,
                        text=NUDGE2_TEXT,
                        reply_markup=kb_nudge2(),
                    )

                    await session.execute(select(Draft).where(Draft.id == draft_id))
                    draft = await session.get(Draft, draft_id)
                    if draft:
                        draft.nudge2_sent_at = datetime.utcnow()
                        await session.commit()

                    log.info("n2 sent: uid=%s step=%s", uid, last_step)

                except Exception:
                    await session.rollback()
                    log.exception("n2 send failed: uid=%s", uid)