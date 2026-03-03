from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import settings

try:
    from aiogram import Bot  # type: ignore
except Exception:
    Bot = Any  # type: ignore

from app.db import AsyncSessionLocal
from app.infrastructure.crm_client import get_crm_client
from app.models import Draft, Request

try:
    from app.vk.keyboards import (
        nudge1_keyboard as vk_kb_n1,
        nudge2_keyboard as vk_kb_n2,
        nudge3_keyboard as vk_kb_n3,
        nudge4_keyboard as vk_kb_n4,
        nudge5_keyboard as vk_kb_n5,
        nudge6_keyboard as vk_kb_n6,
        nudge7_keyboard as vk_kb_n7,
    )
except Exception:
    vk_kb_n1 = vk_kb_n2 = vk_kb_n3 = vk_kb_n4 = vk_kb_n5 = vk_kb_n6 = vk_kb_n7 = None

try:
    from app.keyboards import (
        kb_nudge1,
        kb_nudge2,
        kb_nudge3,
        kb_nudge4,
        kb_nudge5,
        kb_nudge6,
        kb_nudge7,
    )
except Exception:

    def kb_nudge1(*args, **kwargs):
        return None

    def kb_nudge2(*args, **kwargs):
        return None

    def kb_nudge3(*args, **kwargs):
        return None

    def kb_nudge4(*args, **kwargs):
        return None

    def kb_nudge5(*args, **kwargs):
        return None

    def kb_nudge6(*args, **kwargs):
        return None

    def kb_nudge7(*args, **kwargs):
        return None


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


def _crm_terminal(payload: dict) -> bool:
    status = str(payload.get("status") or "").strip().lower()
    return status in _TERMINAL_STATUSES


def _today_istanbul():
    ist = ZoneInfo("Europe/Istanbul")
    return datetime.now(tz=ist).date()


class NudgeService:
    def __init__(self, bot: Bot | None = None, *, vk_sender=None) -> None:
        self.bot = bot
        self.vk_sender = vk_sender

    async def tick(self, *, transport_filter: str | None = None) -> None:
        await self._check_nudge1(transport_filter=transport_filter)
        await self._check_nudge2(transport_filter=transport_filter)
        await self._check_nudge3(transport_filter=transport_filter)
        await self._check_nudge4(transport_filter=transport_filter)
        await self._check_nudge5(transport_filter=transport_filter)
        await self._check_nudge6(transport_filter=transport_filter)
        await self._check_nudge7(transport_filter=transport_filter)

    async def _send(self, transport: str, peer_id: int, text: str, reply_markup=None) -> None:
        if transport == "tg":
            if self.bot is None:
                raise RuntimeError("tg bot is not configured")
            await self.bot.send_message(chat_id=peer_id, text=text, reply_markup=reply_markup)
            return

        if transport == "vk":
            if self.vk_sender is None:
                raise RuntimeError("vk_sender is not configured")

            vk_keyboard = reply_markup if isinstance(reply_markup, str) else None
            await self.vk_sender(peer_id, text, keyboard=vk_keyboard)
            return

        raise ValueError(f"unsupported transport: {transport}")

    def _retry_delay(self) -> timedelta:
        return timedelta(seconds=int(getattr(settings, "nudge_retry_delay_seconds", 60)))

    async def _backoff_request(self, session, req_id: int, sent_field: str, planned_field: str) -> None:
        await session.rollback()
        req = await session.get(Request, req_id)
        if req is None:
            return
        if getattr(req, sent_field) is not None:
            setattr(req, sent_field, None)
        setattr(req, planned_field, datetime.utcnow() + self._retry_delay())
        await session.commit()

    async def _backoff_draft(self, session, draft_id: int, sent_field: str, planned_field: str) -> None:
        await session.rollback()
        draft = await session.get(Draft, draft_id)
        if draft is None:
            return
        if getattr(draft, sent_field) is not None:
            setattr(draft, sent_field, None)
        setattr(draft, planned_field, datetime.utcnow() + self._retry_delay())
        await session.commit()

    async def _check_nudge1(self, *, transport_filter: str | None) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Request.id)
                .where(Request.nudge1_answer.is_(None))
                .where(Request.nudge1_sent_at.is_(None))
                .where(Request.nudge1_planned_at.is_not(None))
                .where(Request.nudge1_planned_at <= now)
                .order_by(Request.id.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            if transport_filter:
                stmt = stmt.where(Request.transport == transport_filter)

            ids = [r[0] for r in (await session.execute(stmt)).all()]
            if not ids:
                return

            crm = get_crm_client()

            for req_id in ids:
                try:
                    req = await session.get(Request, req_id)
                    if not req:
                        continue

                    transport = str(req.transport)
                    peer_id = int(req.peer_id)

                    if req.nudge1_answer is not None or req.nudge1_sent_at is not None:
                        continue

                    if req.crm_request_id:
                        st = await crm.check_status(str(req.crm_request_id))
                        if isinstance(st, dict) and _crm_contacted(st):
                            req.nudge1_sent_at = now
                            req.nudge1_answer = "skip_contacted"
                            await session.commit()
                            continue

                    if transport == "vk" and vk_kb_n1 is not None:
                        markup = vk_kb_n1()
                    else:
                        markup = kb_nudge1()

                    # reserve
                    req.nudge1_sent_at = now
                    await session.commit()

                    # send
                    await self._send(transport, peer_id, NUDGE1_TEXT, reply_markup=markup)

                except Exception:
                    log.exception("n1 send failed: req_id=%s", req_id)
                    await self._backoff_request(session, int(req_id), "nudge1_sent_at", "nudge1_planned_at")

    async def _check_nudge2(self, *, transport_filter: str | None) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Draft.id)
                .where(Draft.last_step.in_(STEPS_FOR_NUDGE2))
                #.where(Draft.give_amount.is_not(None))
                .where(Draft.nudge2_answer.is_(None))
                .where(Draft.nudge2_sent_at.is_(None))
                .where(Draft.nudge2_planned_at.is_not(None))
                .where(Draft.nudge2_planned_at <= now)
                .order_by(Draft.id.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            if transport_filter:
                stmt = stmt.where(Draft.transport == transport_filter)

            ids = [r[0] for r in (await session.execute(stmt)).all()]
            if not ids:
                return

            for draft_id in ids:
                try:
                    draft = await session.get(Draft, draft_id)
                    if not draft:
                        continue

                    transport = str(draft.transport)
                    peer_id = int(draft.peer_id)

                    if draft.nudge2_answer is not None or draft.nudge2_sent_at is not None:
                        continue

                    if transport == "vk" and vk_kb_n2 is not None:
                        markup = vk_kb_n2()
                    else:
                        markup = kb_nudge2()

                    # reserve
                    draft.nudge2_sent_at = now
                    await session.commit()

                    # send
                    await self._send(transport, peer_id, NUDGE2_TEXT, reply_markup=markup)
                    log.info("n2 sent: transport=%s peer_id=%s step=%s", transport, peer_id, draft.last_step)

                except Exception:
                    log.exception("n2 send failed: draft_id=%s", draft_id)
                    await self._backoff_draft(session, int(draft_id), "nudge2_sent_at", "nudge2_planned_at")

    async def _check_nudge3(self, *, transport_filter: str | None) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Draft.id)
                .where(Draft.step6_at.is_not(None))
                .where(Draft.nudge3_planned_at.is_not(None))
                .where(Draft.nudge3_planned_at <= now)
                .where(Draft.nudge3_sent_at.is_(None))
                .where(Draft.nudge3_answer.is_(None))
                .order_by(Draft.id.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            if transport_filter:
                stmt = stmt.where(Draft.transport == transport_filter)

            ids = [r[0] for r in (await session.execute(stmt)).all()]
            if not ids:
                return

            for draft_id in ids:
                try:
                    draft = await session.get(Draft, draft_id)
                    if not draft:
                        continue

                    transport = str(draft.transport)
                    peer_id = int(draft.peer_id)

                    if draft.nudge3_answer is not None or draft.nudge3_sent_at is not None:
                        continue

                    if draft.client_request_id:
                        req_exists = await session.scalar(
                            select(Request.id).where(Request.client_request_id == str(draft.client_request_id))
                        )
                        if req_exists:
                            draft.nudge3_answer = "skip_confirmed"
                            draft.nudge3_sent_at = now
                            await session.commit()
                            continue

                    if transport == "vk" and vk_kb_n3 is not None:
                        markup = vk_kb_n3()
                    else:
                        markup = kb_nudge3()

                    # reserve
                    draft.nudge3_sent_at = now
                    await session.commit()

                    # send
                    await self._send(transport, peer_id, NUDGE3_TEXT, reply_markup=markup)

                except Exception:
                    log.exception("n3 send failed: draft_id=%s", draft_id)
                    await self._backoff_draft(session, int(draft_id), "nudge3_sent_at", "nudge3_planned_at")

    async def _check_nudge4(self, *, transport_filter: str | None) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Draft.id)
                .where(Draft.nudge2_answer == "later")
                .where(Draft.nudge4_planned_at.is_not(None))
                .where(Draft.nudge4_planned_at <= now)
                .where(Draft.nudge4_sent_at.is_(None))
                .where(Draft.nudge4_answer.is_(None))
                .order_by(Draft.id.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            if transport_filter:
                stmt = stmt.where(Draft.transport == transport_filter)

            ids = [r[0] for r in (await session.execute(stmt)).all()]
            if not ids:
                return

            for draft_id in ids:
                try:
                    draft = await session.get(Draft, draft_id)
                    if not draft:
                        continue

                    transport = str(draft.transport)
                    peer_id = int(draft.peer_id)

                    if draft.nudge4_answer is not None or draft.nudge4_sent_at is not None:
                        continue

                    if transport == "vk" and vk_kb_n4 is not None:
                        markup = vk_kb_n4()
                    else:
                        markup = kb_nudge4()

                    # reserve
                    draft.nudge4_sent_at = now
                    await session.commit()

                    # send
                    await self._send(transport, peer_id, NUDGE4_TEXT, reply_markup=markup)

                except Exception:
                    log.exception("n4 send failed: draft_id=%s", draft_id)
                    await self._backoff_draft(session, int(draft_id), "nudge4_sent_at", "nudge4_planned_at")
    async def _check_nudge5(self, *, transport_filter: str | None) -> None:
        now = datetime.utcnow()
        today = now.date()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Request.id)
                .where(Request.nudge5_planned_at.is_not(None))
                .where(Request.nudge5_planned_at <= now)
                .where(Request.nudge5_sent_at.is_(None))
                .where(Request.nudge5_answer.is_(None))
                .order_by(Request.id.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            if transport_filter:
                stmt = stmt.where(Request.transport == transport_filter)

            ids = [r[0] for r in (await session.execute(stmt)).all()]
            if not ids:
                return

            crm = get_crm_client()

            for req_id in ids:
                try:
                    req = await session.get(Request, req_id)
                    if req is None:
                        continue

                    transport = str(req.transport)
                    peer_id = int(req.peer_id)

                    if req.nudge5_answer is not None or req.nudge5_sent_at is not None:
                        continue

                    if req.desired_date is None or req.desired_date == today:
                        req.nudge5_sent_at = now
                        req.nudge5_answer = "skip_date"
                        await session.commit()
                        continue

                    if req.crm_request_id:
                        st = await asyncio.wait_for(crm.check_status(str(req.crm_request_id)), timeout=15)
                        if isinstance(st, dict) and _crm_terminal(st):
                            req.nudge5_sent_at = now
                            req.nudge5_answer = "skip_terminal"
                            await session.commit()
                            continue

                    if transport == "vk" and vk_kb_n5 is not None:
                        markup = vk_kb_n5()
                    else:
                        markup = kb_nudge5(int(req_id))

                    # reserve
                    req.nudge5_sent_at = now
                    await session.commit()

                    # send
                    await self._send(transport, peer_id, NUDGE5_TEXT, reply_markup=markup)

                except Exception:
                    log.exception("n5 send failed: req_id=%s", req_id)
                    await self._backoff_request(session, int(req_id), "nudge5_sent_at", "nudge5_planned_at")

    async def _check_nudge6(self, *, transport_filter: str | None) -> None:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Request.id)
                .where(Request.nudge6_planned_at.is_not(None))
                .where(Request.nudge6_planned_at <= now)
                .where(Request.nudge6_sent_at.is_(None))
                .where(Request.nudge6_answer.is_(None))
                .order_by(Request.id.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            if transport_filter:
                stmt = stmt.where(Request.transport == transport_filter)

            ids = [r[0] for r in (await session.execute(stmt)).all()]
            if not ids:
                return

            crm = get_crm_client()

            for req_id in ids:
                try:
                    req = await session.get(Request, req_id)
                    if req is None:
                        continue

                    transport = str(req.transport)
                    peer_id = int(req.peer_id)

                    if req.nudge6_answer is not None or req.nudge6_sent_at is not None:
                        continue

                    if req.crm_request_id:
                        st = await asyncio.wait_for(crm.check_status(str(req.crm_request_id)), timeout=15)
                        if isinstance(st, dict) and _crm_terminal(st):
                            req.nudge6_sent_at = now
                            req.nudge6_answer = "skip_terminal"
                            await session.commit()
                            continue

                    if transport == "vk" and vk_kb_n6 is not None:
                        markup = vk_kb_n6()
                    else:
                        markup = kb_nudge6(int(req_id))

                    # reserve
                    req.nudge6_sent_at = now
                    await session.commit()

                    # send
                    await self._send(transport, peer_id, NUDGE6_TEXT, reply_markup=markup)

                except Exception:
                    log.exception("n6 send failed: req_id=%s", req_id)
                    await self._backoff_request(session, int(req_id), "nudge6_sent_at", "nudge6_planned_at")

    async def _check_nudge7(self, *, transport_filter: str | None) -> None:
        now = datetime.utcnow()
        today_ist = _today_istanbul()

        ist = ZoneInfo("Europe/Istanbul")
        now_ist = datetime.now(tz=ist)
        ten_ist_today = now_ist.replace(hour=10, minute=0, second=0, microsecond=0)

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Request.id)
                .where(Request.nudge7_planned_at.is_not(None))
                .where(Request.nudge7_planned_at <= now)
                .where(Request.nudge7_sent_at.is_(None))
                .where(Request.nudge7_answer.is_(None))
                .order_by(Request.id.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            if transport_filter:
                stmt = stmt.where(Request.transport == transport_filter)

            ids = [r[0] for r in (await session.execute(stmt)).all()]
            if not ids:
                return

            crm = get_crm_client()

            for req_id in ids:
                try:
                    req = await session.get(Request, req_id)
                    if req is None:
                        continue

                    transport = str(req.transport)
                    peer_id = int(req.peer_id)

                    if req.nudge7_answer is not None or req.nudge7_sent_at is not None:
                        continue

                    if req.desired_date and req.desired_date != today_ist:
                        req.nudge7_sent_at = now
                        req.nudge7_answer = "skip_not_today"
                        await session.commit()
                        continue

                    # Отправляем строго после 10:00 по Турции
                    if now_ist < ten_ist_today:
                        continue

                    if req.crm_request_id:
                        st = await asyncio.wait_for(crm.check_status(str(req.crm_request_id)), timeout=15)
                        if isinstance(st, dict) and _crm_terminal(st):
                            req.nudge7_sent_at = now
                            req.nudge7_answer = "skip_terminal"
                            await session.commit()
                            continue

                    if transport == "vk" and vk_kb_n7 is not None:
                        markup = vk_kb_n7()
                    else:
                        markup = kb_nudge7(int(req_id))

                    # reserve
                    req.nudge7_sent_at = now
                    await session.commit()

                    # send
                    await self._send(transport, peer_id, NUDGE7_TEXT, reply_markup=markup)

                except Exception:
                    log.exception("n7 send failed: req_id=%s", req_id)
                    await self._backoff_request(session, int(req_id), "nudge7_sent_at", "nudge7_planned_at")