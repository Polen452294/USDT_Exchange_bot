from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.infrastructure.crm_client import get_crm_client
from app.keyboards import kb_nudge1, kb_nudge2, kb_nudge3, kb_nudge4, kb_nudge5, kb_nudge6, kb_nudge7
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

NUDGE5_TEXT = (
    "Напоминаю: через 14 дней у вас запланирован обмен.\n"
    "Подтвердите, пожалуйста — всё ещё актуально?"
)

NUDGE6_TEXT = "У нас есть для вас специальное предложение для заявки. Хотите узнать?"

NUDGE7_TEXT = (
    "Доброе утро! Сегодня у вас запланирован обмен: (данные заявки). "
    "Хотите, чтобы менеджер с вами?"
)

STEPS_FOR_NUDGE2 = [
    "amount_wait",
    "amount",
    "office",
    "date",
    "date_default",
    "username_auto",
    "username_manual",
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


def _today_istanbul():
    ist = ZoneInfo("Europe/Istanbul")
    return datetime.now(tz=ist).date()


def _crm_terminal(payload: dict) -> bool:
    status = str(payload.get("status") or "").strip().lower()
    return status in _TERMINAL_STATUSES


class NudgeService:
    def __init__(self, bot: Bot, *, vk_sender=None) -> None:
        self.bot = bot
        self.vk_sender = vk_sender

    async def tick(self) -> None:
        await self._check_nudge1()
        await self._check_nudge2()
        await self._check_nudge3()
        await self._check_nudge4()
        await self._check_nudge5()
        await self._check_nudge6()
        await self._check_nudge7()

    async def _send(self, transport: str, peer_id: int, text: str, *, reply_markup=None) -> None:
        if transport == "tg":
            await self.bot.send_message(chat_id=peer_id, text=text, reply_markup=reply_markup)
            return

        if transport == "vk":
            if self.vk_sender is None:
                raise RuntimeError("vk_sender is not configured")
            await self.vk_sender(peer_id, text)
            return

        raise ValueError(f"unsupported transport: {transport}")

    async def _check_nudge1(self) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Request.id, Request.transport, Request.peer_id, Request.crm_request_id)
                .where(Request.nudge1_answer.is_(None))
                .where(Request.nudge1_sent_at.is_(None))
                .where(Request.nudge1_planned_at.is_not(None))
                .where(Request.nudge1_planned_at <= now)
                .order_by(Request.id.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            crm = get_crm_client()

            for req_id, transport, peer_id, crm_request_id in rows:
                try:
                    req = await session.get(Request, req_id)
                    if not req:
                        continue

                    if req.nudge1_answer is not None or req.nudge1_sent_at is not None:
                        continue

                    if crm_request_id:
                        st = await crm.check_status(str(crm_request_id))
                        if isinstance(st, dict) and _crm_contacted(st):
                            req.nudge1_sent_at = now
                            req.nudge1_answer = "skip_contacted"
                            await session.commit()
                            continue

                    req.nudge1_sent_at = datetime.utcnow()
                    await session.commit()

                    await self._send(str(transport), int(peer_id), NUDGE1_TEXT, reply_markup=kb_nudge1())

                except Exception:
                    await session.rollback()
                    log.exception("n1 send failed: req_id=%s", req_id)

    async def _check_nudge2(self) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Draft.id, Draft.transport, Draft.peer_id, Draft.last_step)
                .where(Draft.last_step.in_(STEPS_FOR_NUDGE2))
                .where(Draft.give_amount.is_not(None))
                .where(Draft.nudge2_answer.is_(None))
                .where(Draft.nudge2_sent_at.is_(None))
                .where(Draft.nudge2_planned_at.is_not(None))
                .where(Draft.nudge2_planned_at <= now)
                .limit(50)
            )
            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            for draft_id, transport, peer_id, last_step in rows:
                try:
                    await self._send(str(transport), int(peer_id), NUDGE2_TEXT, reply_markup=kb_nudge2())

                    draft = await session.get(Draft, draft_id)
                    if draft:
                        draft.nudge2_sent_at = datetime.utcnow()
                        await session.commit()

                    log.info("n2 sent: transport=%s peer_id=%s step=%s", transport, peer_id, last_step)

                except Exception:
                    await session.rollback()
                    log.exception("n2 send failed: transport=%s peer_id=%s", transport, peer_id)

    async def _check_nudge3(self) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Draft.id, Draft.transport, Draft.peer_id, Draft.client_request_id)
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

            for draft_id, transport, peer_id, client_request_id in rows:
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

                    await self._send(str(transport), int(peer_id), NUDGE3_TEXT, reply_markup=kb_nudge3())

                    draft = await session.get(Draft, draft_id)
                    if draft and draft.nudge3_sent_at is None:
                        draft.nudge3_sent_at = datetime.utcnow()
                        await session.commit()

                except Exception:
                    await session.rollback()
                    log.exception("n3 send failed: transport=%s peer_id=%s", transport, peer_id)

    async def _check_nudge4(self) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Draft.id, Draft.transport, Draft.peer_id)
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

            for draft_id, transport, peer_id in rows:
                try:
                    await self._send(str(transport), int(peer_id), NUDGE4_TEXT, reply_markup=kb_nudge4())

                    draft = await session.get(Draft, draft_id)
                    if draft and draft.nudge4_sent_at is None:
                        draft.nudge4_sent_at = datetime.utcnow()
                        await session.commit()

                except Exception:
                    await session.rollback()
                    log.exception("n4 send failed: transport=%s peer_id=%s", transport, peer_id)

    async def _check_nudge5(self) -> None:
        now = datetime.utcnow()
        today = now.date()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Request.id, Request.transport, Request.peer_id, Request.crm_request_id)
                .where(Request.nudge5_planned_at.is_not(None))
                .where(Request.nudge5_planned_at <= now)
                .where(Request.nudge5_sent_at.is_(None))
                .where(Request.nudge5_answer.is_(None))
                .order_by(Request.id.asc())
                .limit(50)
            )
            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            crm = get_crm_client()

            for req_id, transport, peer_id, crm_request_id in rows:
                try:
                    req = await session.get(Request, req_id)
                    if req is None:
                        continue

                    if req.desired_date is None or req.desired_date == today:
                        req.nudge5_sent_at = now
                        req.nudge5_answer = "skip_date"
                        await session.commit()
                        continue

                    if crm_request_id:
                        st = await asyncio.wait_for(crm.check_status(str(crm_request_id)), timeout=15)
                        if isinstance(st, dict) and _crm_terminal(st):
                            req.nudge5_sent_at = now
                            req.nudge5_answer = "skip_terminal"
                            await session.commit()
                            continue

                    await self._send(str(transport), int(peer_id), NUDGE5_TEXT, reply_markup=kb_nudge5())

                    req.nudge5_sent_at = datetime.utcnow()
                    await session.commit()

                except Exception:
                    await session.rollback()
                    log.exception("n5 send failed: transport=%s peer_id=%s", transport, peer_id)

    async def _check_nudge6(self) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Request.id, Request.transport, Request.peer_id, Request.crm_request_id)
                .where(Request.nudge6_planned_at.is_not(None))
                .where(Request.nudge6_planned_at <= now)
                .where(Request.nudge6_sent_at.is_(None))
                .where(Request.nudge6_answer.is_(None))
                .order_by(Request.id.asc())
                .limit(50)
            )
            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            crm = get_crm_client()

            for req_id, transport, peer_id, crm_request_id in rows:
                try:
                    req = await session.get(Request, req_id)
                    if req is None:
                        continue

                    if crm_request_id:
                        st = await asyncio.wait_for(crm.check_status(str(crm_request_id)), timeout=15)
                        if isinstance(st, dict) and _crm_terminal(st):
                            req.nudge6_sent_at = now
                            req.nudge6_answer = "skip_terminal"
                            await session.commit()
                            continue

                    await self._send(str(transport), int(peer_id), NUDGE6_TEXT, reply_markup=kb_nudge6())

                    req.nudge6_sent_at = datetime.utcnow()
                    await session.commit()

                except Exception:
                    await session.rollback()
                    log.exception("n6 send failed: transport=%s peer_id=%s", transport, peer_id)

    async def _check_nudge7(self) -> None:
        now = datetime.utcnow()
        today_ist = _today_istanbul()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Request.id, Request.transport, Request.peer_id, Request.crm_request_id, Request.desired_date)
                .where(Request.nudge7_planned_at.is_not(None))
                .where(Request.nudge7_planned_at <= now)
                .where(Request.nudge7_sent_at.is_(None))
                .where(Request.nudge7_answer.is_(None))
                .order_by(Request.id.asc())
                .limit(50)
            )
            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            crm = get_crm_client()

            for req_id, transport, peer_id, crm_request_id, desired_date in rows:
                try:
                    req = await session.get(Request, req_id)
                    if req is None:
                        continue

                    if desired_date and desired_date != today_ist:
                        req.nudge7_sent_at = now
                        req.nudge7_answer = "skip_not_today"
                        await session.commit()
                        continue

                    if crm_request_id:
                        st = await asyncio.wait_for(crm.check_status(str(crm_request_id)), timeout=15)
                        if isinstance(st, dict) and _crm_terminal(st):
                            req.nudge7_sent_at = now
                            req.nudge7_answer = "skip_terminal"
                            await session.commit()
                            continue

                    await self._send(str(transport), int(peer_id), NUDGE7_TEXT, reply_markup=kb_nudge7())

                    req.nudge7_sent_at = datetime.utcnow()
                    await session.commit()

                except Exception:
                    await session.rollback()
                    log.exception("n7 send failed: transport=%s peer_id=%s", transport, peer_id)