from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.infrastructure.crm_client import get_crm_client
from app.keyboards import kb_nudge1, kb_nudge2, kb_nudge3, kb_nudge4
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

NUDGE3_TEXT = (
    "Небольшое напоминание: срок действия текущего курса скоро закончится.\n"
    "Хотите, чтобы менеджер помог быстро зафиксировать условия по вашей заявке?"
)

NUDGE4_TEXT = (
    "Пишу напомнить, что наши менеджеры на связи и готовы предложить вам "
    "специальные условия обмена. Нажмите Да, чтобы получить специальное "
    "предложение"
)

STEPS_FOR_NUDGE2 = [
    "amount_wait",
    "amount",
    "office",
    "date",
    "date_default",
    "username_auto",
    "username_manual",
    #"summary",
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
        await self._check_nudge3()
        await self._check_nudge4()

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

                    draft = await session.get(Draft, draft_id)
                    if draft:
                        draft.nudge2_sent_at = datetime.utcnow()
                        await session.commit()

                    log.info("n2 sent: uid=%s step=%s", uid, last_step)

                except Exception:
                    await session.rollback()
                    log.exception("n2 send failed: uid=%s", uid)

    async def _check_nudge3(self) -> None:
        now = datetime.utcnow()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Draft.id, Draft.telegram_user_id, Draft.client_request_id)
                .where(Draft.step6_at.is_not(None))
                .where(Draft.nudge3_planned_at.is_not(None))
                .where(Draft.nudge3_planned_at <= now)
                .where(Draft.nudge3_sent_at.is_(None))
                .where(Draft.nudge3_answer.is_(None))
                .limit(50)
            )

            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            log.info("n3 candidates=%d", len(rows))

            for draft_id, uid, client_request_id in rows:
                uid = int(uid)

                try:
                    if client_request_id:
                        req_exists = await session.scalar(
                            select(Request.id).where(Request.client_request_id == str(client_request_id))
                        )
                        if req_exists:
                            draft = await session.get(Draft, draft_id)
                            if draft and draft.nudge3_answer is None:
                                draft.nudge3_answer = "skip_confirmed"
                                draft.nudge3_sent_at = now
                                await session.commit()
                            continue

                    await self.bot.send_message(
                        chat_id=uid,
                        text=NUDGE3_TEXT,
                        reply_markup=kb_nudge3(),
                    )

                    draft = await session.get(Draft, draft_id)
                    if draft and draft.nudge3_sent_at is None:
                        draft.nudge3_sent_at = datetime.utcnow()
                        await session.commit()

                    log.info("n3 sent: uid=%s draft_id=%s", uid, draft_id)

                except Exception:
                    await session.rollback()
                    log.exception("n3 send failed: uid=%s", uid)
    async def _check_nudge4(self) -> None:
        now = datetime.utcnow()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Draft.id, Draft.telegram_user_id)
                .where(Draft.nudge2_answer == "later")
                .where(Draft.nudge4_planned_at.is_not(None))
                .where(Draft.nudge4_planned_at <= now)
                .where(Draft.nudge4_sent_at.is_(None))
                .where(Draft.nudge4_answer.is_(None))
                .limit(50)
            )

            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            log.info("n4 candidates=%d", len(rows))

            for draft_id, uid in rows:
                uid = int(uid)
                try:
                    await self.bot.send_message(
                        chat_id=uid,
                        text=NUDGE4_TEXT,
                        reply_markup=kb_nudge4(),
                    )

                    draft = await session.get(Draft, draft_id)
                    if draft and draft.nudge4_sent_at is None:
                        draft.nudge4_sent_at = datetime.utcnow()
                        await session.commit()

                    log.info("n4 sent: uid=%s draft_id=%s", uid, draft_id)

                except Exception:
                    await session.rollback()
                    log.exception("n4 send failed: uid=%s", uid)