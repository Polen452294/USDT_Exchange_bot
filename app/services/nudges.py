from __future__ import annotations

import logging
from datetime import datetime, timedelta, date
from datetime import timezone
from zoneinfo import ZoneInfo
import asyncio
from aiogram import Bot
from sqlalchemy import select

from app.config import Settings
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

NUDGE6_TEXT = (
    "У нас есть для вас специальное предложение для заявки. Хотите узнать?"
)

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

def _today_istanbul() -> datetime.date:
    ist = ZoneInfo("Europe/Istanbul")
    return datetime.now(tz=ist).date()

def _format_request_block(req: Request) -> str:
    try:
        direction = req.direction.value
    except Exception:
        direction = str(req.direction)
    office = getattr(req, "office_id", None) or "-"
    desired = req.desired_date.strftime("%d.%m.%Y") if req.desired_date else "-"
    give_amount = getattr(req, "give_amount", None)
    receive_amount = getattr(req, "receive_amount", None)
    rate = getattr(req, "rate", None)
    return (
        "Детали заявки:\n"
        f"• Направление: {direction}\n"
        f"• Сумма: {give_amount}\n"
        f"• Офис: {office}\n"
        f"• Дата: {desired}\n"
        f"• Курс: {rate}\n"
        f"• Получаете: {receive_amount}"
    )

def _crm_terminal(payload: dict) -> bool:
    status = str(payload.get("status") or "").strip().lower()
    return status in _TERMINAL_STATUSES


def _format_request_block(req: Request) -> str:
    try:
        direction = req.direction.value
    except Exception:
        direction = str(req.direction)

    office = getattr(req, "office_id", None) or getattr(req, "office", None) or "-"
    desired = req.desired_date.strftime("%d.%m.%Y") if req.desired_date else "-"

    give_amount = getattr(req, "give_amount", None)
    receive_amount = getattr(req, "receive_amount", None)
    rate = getattr(req, "rate", None)

    return (
        "Детали заявки:\n"
        f"• Направление: {direction}\n"
        f"• Сумма: {give_amount}\n"
        f"• Офис: {office}\n"
        f"• Дата: {desired}\n"
        f"• Курс: {rate}\n"
        f"• Получаете: {receive_amount}"
    )


class NudgeService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def tick(self) -> None:
        await self._check_nudge1()
        await self._check_nudge2()
        await self._check_nudge3()
        await self._check_nudge4()
        await self._check_nudge5()
        await self._check_nudge6()
        await self._check_nudge7()

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
                .with_for_update(skip_locked=True)
            )

            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            log.info("n1 candidates=%d", len(rows))

            crm = get_crm_client()

            for req_id, uid, crm_request_id in rows:
                uid = int(uid)

                try:
                    req = await session.get(Request, req_id)
                    if not req:
                        continue

                    # если уже ответил или уже отправляли — пропускаем
                    if req.nudge1_answer is not None or req.nudge1_sent_at is not None:
                        continue

                    # если CRM уже в работе — не отправляем
                    if crm_request_id:
                        st = await crm.check_status(str(crm_request_id))
                        if isinstance(st, dict) and _crm_contacted(st):
                            req.nudge1_sent_at = now
                            req.nudge1_answer = "skip_contacted"
                            await session.commit()
                            continue

                    # 🔐 СНАЧАЛА резервируем отправку
                    req.nudge1_sent_at = datetime.utcnow()
                    await session.commit()

                    # потом отправляем сообщение
                    await self.bot.send_message(
                        chat_id=uid,
                        text=NUDGE1_TEXT,
                        reply_markup=kb_nudge1(),
                    )

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

    async def _check_nudge5(self) -> None:
        now = datetime.utcnow()
        today = now.date()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(
                    Request.id,
                    Request.telegram_user_id,
                    Request.crm_request_id,
                )
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

            log.info("n5 candidates=%d", len(rows))

            crm = get_crm_client()

            for req_id, uid, crm_request_id in rows:
                uid = int(uid)

                log.info("n5 debug: start req_id=%s uid=%s crm_request_id=%s", req_id, uid, crm_request_id)

                try:
                    req = await session.get(Request, req_id)
                    log.info("n5 debug: request loaded req_id=%s", req_id)

                    if req is None:
                        continue

                    if req.desired_date is None or req.desired_date == today:
                        req.nudge5_sent_at = now
                        req.nudge5_answer = "skip_date"
                        await session.commit()
                        log.info("n5 debug: skipped by date req_id=%s", req_id)
                        continue

                    if crm_request_id:
                        log.info("n5 debug: before crm.check_status req_id=%s", req_id)
                        st = await asyncio.wait_for(
                            crm.check_status(str(crm_request_id)),
                            timeout=15,
                        )
                        log.info("n5 debug: after crm.check_status req_id=%s", req_id)

                        if isinstance(st, dict):
                            status = str(st.get("status") or "").lower()
                            if status in {"done", "completed", "paid", "fixed", "closed"}:
                                req.nudge5_sent_at = now
                                req.nudge5_answer = "skip_terminal"
                                await session.commit()
                                log.info("n5 debug: skipped by terminal status req_id=%s", req_id)
                                continue

                    try:
                        direction = req.direction.value
                    except Exception:
                        direction = str(req.direction)

                    if direction == "USDT_TO_CASH":
                        give_currency = "USDT"
                        receive_currency = "наличные"
                    else:
                        give_currency = "наличные"
                        receive_currency = "USDT"

                    request_block = (
                        f"➔ Вы отдаёте: {req.give_amount} {give_currency}\n"
                        f"➔ Офис: {req.office_id}\n"
                        f"➔ Дата получения: {req.desired_date.strftime('%d.%m.%Y')}\n"
                        f"➔ Текущий курс: {req.rate}\n"
                        f"➔ Вы получаете: {req.receive_amount} {receive_currency}"
                    )

                    text = (
                        "Недавно вы оставляли заявку на обмен:\n\n"
                        f"{request_block}\n\n"
                        "Мы готовы помочь вам, если задача актуальна.\n"
                        "Хотите, чтобы наш менеджер связался с вами напрямую и обсудил условия?"
                    )

                    log.info("n5 debug: before bot.send_message req_id=%s uid=%s", req_id, uid)

                    await asyncio.wait_for(
                        self.bot.send_message(
                            chat_id=uid,
                            text=text,
                            reply_markup=kb_nudge5(req_id),
                        ),
                        timeout=15,
                    )

                    log.info("n5 debug: after bot.send_message req_id=%s uid=%s", req_id, uid)

                    if req.nudge5_sent_at is None:
                        req.nudge5_sent_at = datetime.utcnow()
                        await session.commit()

                    log.info("n5 sent: uid=%s req_id=%s", uid, req_id)

                except Exception as e:
                    await session.rollback()
                    log.exception("n5 send failed: uid=%s req_id=%s err=%r", uid, req_id, e)

    async def _check_nudge6(self) -> None:
        now = datetime.utcnow()
        today = now.date()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(
                    Request.id,
                    Request.telegram_user_id,
                    Request.crm_request_id,
                )
                .where(Request.nudge6_planned_at.is_not(None))
                .where(Request.nudge6_planned_at <= now)
                .where(Request.nudge6_sent_at.is_(None))
                .where(Request.nudge6_answer.is_(None))
                .where(Request.nudge5_sent_at.is_not(None))
                .where(Request.nudge5_answer.is_(None))
                .order_by(Request.id.asc())
                .limit(50)
            )

            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            log.info("n6 candidates=%d", len(rows))

            crm = get_crm_client()

            for req_id, uid, crm_request_id in rows:
                uid = int(uid)

                try:
                    req = await session.get(Request, req_id)
                    if req is None:
                        continue

                    if req.desired_date is None or req.desired_date == today:
                        req.nudge6_sent_at = now
                        req.nudge6_answer = "skip_date"
                        await session.commit()
                        continue

                    if crm_request_id:
                        st = await crm.check_status(str(crm_request_id))
                        if isinstance(st, dict):
                            status = str(st.get("status") or "").strip().lower()
                            if status in _TERMINAL_STATUSES:
                                req.nudge6_sent_at = now
                                req.nudge6_answer = "skip_terminal"
                                await session.commit()
                                continue

                    await self.bot.send_message(
                        chat_id=uid,
                        text=NUDGE6_TEXT,
                        reply_markup=kb_nudge6(req.id),
                    )

                    if req.nudge6_sent_at is None:
                        req.nudge6_sent_at = datetime.utcnow()
                        await session.commit()

                    log.info("n6 sent: uid=%s req_id=%s", uid, req_id)

                except Exception:
                    await session.rollback()
                    log.exception("n6 send failed: uid=%s req_id=%s", uid, req_id)


    async def _check_nudge7(self) -> None:
        now = datetime.utcnow()
        today_ist = _today_istanbul()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Request.id, Request.telegram_user_id, Request.crm_request_id)
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

            for req_id, uid, crm_request_id in rows:
                uid = int(uid)

                try:
                    req = await session.get(Request, req_id)
                    if req is None:
                        continue

                    if req.desired_date != today_ist:
                        req.nudge7_sent_at = now
                        req.nudge7_answer = "skip_not_today"
                        await session.commit()
                        continue

                    if crm_request_id:
                        st = await crm.check_status(str(crm_request_id))
                        if isinstance(st, dict) and _crm_terminal(st):
                            req.nudge7_sent_at = now
                            req.nudge7_answer = "skip_terminal"
                            await session.commit()
                            continue

                    text = (
                        "Доброе утро! Сегодня у вас запланирован обмен:\n\n"
                        f"{_format_request_block(req)}\n\n"
                        "Хотите, чтобы менеджер с вами?"
                    )

                    await self.bot.send_message(
                        chat_id=uid,
                        text=text,
                        reply_markup=kb_nudge7(req.id),
                    )

                    req.nudge7_sent_at = datetime.utcnow()
                    await session.commit()

                except Exception:
                    await session.rollback()
                    log.exception("n7 send failed: uid=%s req_id=%s", uid, req_id)
