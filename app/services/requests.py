from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models import Draft, Request, Direction, direction_from_currency, direction_to_currency
from app.repositories.drafts import DraftRepository
from app.repositories.requests import RequestRepository
from app.infrastructure.crm_client import get_crm_client, CRMTemporaryError, CRMPermanentError

log = logging.getLogger("crm")


DISCLAIMER = (
    "Этот курс действителен в течение 2 часов. Зафиксировать его я смогу только после "
    "получения от вас предоплаты. Для связи с менеджером используйте @coinpointlara."
)


def _money(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _new_client_request_id() -> str:
    return uuid.uuid4().hex[:16] + "-" + str(int(datetime.utcnow().timestamp()))


def _istanbul_10_to_utc_naive(day) -> datetime:
    istanbul = ZoneInfo("Europe/Istanbul")
    local_dt = datetime.combine(day, time(hour=10, minute=0), tzinfo=istanbul)
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class SummaryResult:
    rate: float
    receive_amount: float
    summary_text: str
    office_label: str


@dataclass(frozen=True)
class ConfirmResult:
    created: bool
    already_exists: bool
    crm_request_id: str | None


class RequestService:
    def __init__(self, draft_repo: DraftRepository, request_repo: RequestRepository) -> None:
        self._drafts = draft_repo
        self._requests = request_repo

    def _reset_nudges_for_request(self, req: Request) -> None:
        req.nudge1_sent_at = None
        req.nudge1_answer = None

        req.nudge5_sent_at = None
        req.nudge5_answer = None
        req.nudge5_answered_at = None

        req.nudge6_sent_at = None
        req.nudge6_answer = None
        req.nudge6_answered_at = None

        req.nudge7_sent_at = None
        req.nudge7_answer = None
        req.nudge7_answered_at = None

    async def ensure_client_request_id(self, draft: Draft) -> str:
        if draft.client_request_id:
            return draft.client_request_id
        draft.client_request_id = _new_client_request_id()
        draft.updated_at = datetime.utcnow()
        await self._drafts.save()
        return draft.client_request_id
    
    nudge5_lead_days = int(getattr(settings, "nudge5_lead_days", 1))
    nudge6_lead_days = int(getattr(settings, "nudge6_lead_days", 2))

    async def build_summary_ctx(self, transport: str, peer_id: int) -> SummaryResult:
        draft = await self._drafts.get_by_transport_peer_id(transport, peer_id)
        if draft is None:
            raise ValueError("draft_not_found")

        if (
            draft.direction is None
            or draft.give_amount is None
            or draft.office_id is None
            or draft.desired_date is None
        ):
            log.warning(
                "draft_not_ready: transport=%s peer_id=%s direction=%r give_amount=%r office_id=%r desired_date=%r last_step=%r",
                transport,
                peer_id,
                getattr(draft, "direction", None),
                getattr(draft, "give_amount", None),
                getattr(draft, "office_id", None),
                getattr(draft, "desired_date", None),
                getattr(draft, "last_step", None),
            )
            raise ValueError("draft_not_ready")

        direction = draft.direction if isinstance(draft.direction, Direction) else Direction(str(draft.direction))

        # принимаем только новые направления (старые оставлены для совместимости БД)
        if direction not in (Direction.USDT_TO_TRY_CASH, Direction.TRY_CASH_TO_USDT):
            raise ValueError("bad_direction")

        await self.ensure_client_request_id(draft)

        crm = get_crm_client()
        try:
            rate = await crm.get_rate(str(draft.office_id), direction.value)  # CRM ожидает строку
            office_label = await crm.get_office_label(str(draft.office_id))
        except (CRMTemporaryError, CRMPermanentError):
            log.exception("CRM error on summary (office_id=%s, direction=%s)", draft.office_id, direction.value)
            raise
        except Exception:
            log.exception(
                "Unexpected CRM error on summary (office_id=%s, direction=%s)", draft.office_id, direction.value
            )
            raise CRMTemporaryError("unexpected_crm_error")

        if direction == Direction.TRY_CASH_TO_USDT and settings.rate_calc_mode == "divide_cash_to_usdt":
            receive_amount = draft.give_amount / rate if rate else 0
        else:
            receive_amount = draft.give_amount * rate

        give_currency = direction_from_currency(direction) or "—"
        recv_currency = direction_to_currency(direction) or "—"

        sep = "────────────────"

        give_currency = direction_from_currency(direction)
        recv_currency = direction_to_currency(direction)

        rate_str = _money(float(rate))

        rate_text = f"1 {give_currency} = {rate_str} {recv_currency}"
        give_amount_str = _money(float(draft.give_amount))
        receive_amount_str = _money(float(receive_amount))

        summary_text = (
            "🧾 Сводка заявки\n"
            f"{sep}\n"
            f"➡️ Отправляете: {give_amount_str} {give_currency}\n"
            f"⬅️ Получаете: {receive_amount_str} {recv_currency}\n\n"
            f"🏢 Офис: {office_label}\n"
            f"📅 Дата сделки: {draft.desired_date.strftime('%d.%m.%Y')}\n\n"
            f"📈 Курс: {rate_text}\n"
            f"{sep}\n"
            f"ℹ️ {DISCLAIMER}\n\n"
            "✅ Всё верно?\n"
            "Нажмите «✅ Да, всё отлично» — и я создам заявку.\n"
            "Если нужно изменить данные — нажмите «✍️ Хочу внести изменения»."
        )

        draft.last_step = "summary"
        draft.updated_at = datetime.utcnow()
        await self._drafts.save()

        return SummaryResult(
            rate=float(rate),
            receive_amount=float(receive_amount),
            summary_text=summary_text,
            office_label=office_label,
        )

    async def confirm_request(
        self,
        telegram_user_id: int,
        *,
        rate: float | None = None,
        receive_amount: float | None = None,
        summary_text: str | None = None,
    ) -> ConfirmResult:
        return await self.confirm_request_ctx(
            "tg",
            telegram_user_id,
            rate=rate,
            receive_amount=receive_amount,
            summary_text=summary_text,
        )

    async def confirm_request_ctx(
        self,
        transport: str,
        peer_id: int,
        *,
        rate: float | None = None,
        receive_amount: float | None = None,
        summary_text: str | None = None,
    ) -> ConfirmResult:
        draft = await self._drafts.get_by_transport_peer_id(transport, peer_id)
        if draft is None:
            raise ValueError("draft_not_found")

        if (
            draft.direction is None
            or draft.give_amount is None
            or draft.office_id is None
            or draft.desired_date is None
        ):
            log.warning(
                "draft_not_ready: transport=%s peer_id=%s direction=%r give_amount=%r office_id=%r desired_date=%r last_step=%r",
                transport,
                peer_id,
                getattr(draft, "direction", None),
                getattr(draft, "give_amount", None),
                getattr(draft, "office_id", None),
                getattr(draft, "desired_date", None),
                getattr(draft, "last_step", None),
            )
            raise ValueError("draft_not_ready")

        direction = draft.direction if isinstance(draft.direction, Direction) else Direction(str(draft.direction))
        if direction not in (Direction.USDT_TO_TRY_CASH, Direction.TRY_CASH_TO_USDT):
            raise ValueError("bad_direction")

        client_request_id = await self.ensure_client_request_id(draft)

        nudge5_lead_days = int(getattr(settings, "nudge5_lead_days", 1))
        nudge6_lead_days = int(getattr(settings, "nudge6_lead_days", 2))

        existing = await self._requests.get_by_client_request_id(client_request_id)
        if existing is not None:
            if not rate or not receive_amount or not summary_text:
                summary = await self.build_summary_ctx(transport, peer_id)
                rate = summary.rate
                receive_amount = summary.receive_amount
                summary_text = summary.summary_text

            existing.transport = transport
            existing.peer_id = peer_id
            existing.telegram_user_id = (peer_id if transport == "tg" else None)

            existing.direction = direction
            existing.give_amount = float(draft.give_amount)
            existing.office_id = str(draft.office_id)
            existing.desired_date = draft.desired_date
            existing.rate = float(rate)
            existing.receive_amount = float(receive_amount)
            existing.username = str(draft.username)
            existing.summary_text = str(summary_text)

            self._reset_nudges_for_request(existing)

            existing.nudge1_planned_at = datetime.utcnow() + timedelta(seconds=settings.nudge1_delay_seconds)

            today = datetime.utcnow().date()

            if settings.nudge5_test_mode:
                existing.nudge5_planned_at = datetime.utcnow() + timedelta(seconds=settings.nudge5_test_delay_seconds)
            else:
                existing.nudge5_planned_at = None
                if existing.desired_date and existing.desired_date != today:
                    if existing.desired_date >= (today + timedelta(days=nudge5_lead_days)):
                        planned_day_5 = existing.desired_date - timedelta(days=nudge5_lead_days)
                        existing.nudge5_planned_at = _istanbul_10_to_utc_naive(planned_day_5)

            if settings.nudge6_test_mode:
                existing.nudge6_planned_at = datetime.utcnow() + timedelta(seconds=settings.nudge6_test_delay_seconds)
            else:
                existing.nudge6_planned_at = None
                if existing.desired_date and existing.desired_date != today:
                    if existing.desired_date >= (today + timedelta(days=nudge6_lead_days)):
                        planned_day_6 = existing.desired_date - timedelta(days=nudge6_lead_days)
                        existing.nudge6_planned_at = _istanbul_10_to_utc_naive(planned_day_6)

            if settings.nudge7_test_mode:
                existing.nudge7_planned_at = datetime.utcnow() + timedelta(seconds=settings.nudge7_test_delay_seconds)
            else:
                existing.nudge7_planned_at = None
                if existing.desired_date:
                    existing.nudge7_planned_at = _istanbul_10_to_utc_naive(existing.desired_date)

            await self._requests.save()

            draft.last_step = "done"
            draft.updated_at = datetime.utcnow()
            await self._drafts.save()

            return ConfirmResult(created=False, already_exists=True, crm_request_id=existing.crm_request_id)

        if not rate or not receive_amount or not summary_text:
            summary = await self.build_summary_ctx(transport, peer_id)
            rate = summary.rate
            receive_amount = summary.receive_amount
            summary_text = summary.summary_text

        req = Request(
            transport=transport,
            peer_id=peer_id,
            telegram_user_id=(peer_id if transport == "tg" else None),
            client_request_id=client_request_id,
            crm_request_id=None,
            direction=direction,
            give_amount=float(draft.give_amount),
            office_id=str(draft.office_id),
            desired_date=draft.desired_date,
            rate=float(rate),
            receive_amount=float(receive_amount),
            username=str(draft.username),
            summary_text=str(summary_text),
        )

        req.nudge1_planned_at = datetime.utcnow() + timedelta(seconds=settings.nudge1_delay_seconds)

        today = datetime.utcnow().date()

        if settings.nudge5_test_mode:
            req.nudge5_planned_at = datetime.utcnow() + timedelta(seconds=settings.nudge5_test_delay_seconds)
        else:
            if req.desired_date and req.desired_date != today:
                if req.desired_date >= (today + timedelta(days=nudge5_lead_days)):
                    planned_day_5 = req.desired_date - timedelta(days=nudge5_lead_days)
                    req.nudge5_planned_at = _istanbul_10_to_utc_naive(planned_day_5)

        if settings.nudge6_test_mode:
            req.nudge6_planned_at = datetime.utcnow() + timedelta(seconds=settings.nudge6_test_delay_seconds)
        else:
            if req.desired_date and req.desired_date != today:
                if req.desired_date >= (today + timedelta(days=nudge6_lead_days)):
                    planned_day_6 = req.desired_date - timedelta(days=nudge6_lead_days)
                    req.nudge6_planned_at = _istanbul_10_to_utc_naive(planned_day_6)

        if settings.nudge7_test_mode:
            req.nudge7_planned_at = datetime.utcnow() + timedelta(seconds=settings.nudge7_test_delay_seconds)
        else:
            if req.desired_date:
                req.nudge7_planned_at = _istanbul_10_to_utc_naive(req.desired_date)

        try:
            await self._requests.create(req)
        except IntegrityError:
            await self._requests.rollback()
            existing2 = await self._requests.get_by_client_request_id(client_request_id)
            return ConfirmResult(
                created=False,
                already_exists=True,
                crm_request_id=(existing2.crm_request_id if existing2 else None),
            )

        crm = get_crm_client()
        payload = {
            "client_request_id": client_request_id,
            "transport": transport,
            "peer_id": peer_id,
            "telegram_user_id": (peer_id if transport == "tg" else None),
            "direction": req.direction.value,
            "give_amount": req.give_amount,
            "office_id": req.office_id,
            "desired_date": req.desired_date.isoformat(),
            "username": req.username,
            "rate": req.rate,
            "receive_amount": req.receive_amount,
        }

        try:
            crm_resp = await crm.create_request(payload, idempotency_key=client_request_id)
        except CRMTemporaryError:
            raise
        except CRMPermanentError:
            raise

        req.crm_request_id = str(crm_resp.get("crm_request_id") or "")
        await self._requests.save()

        draft.last_step = "done"
        draft.updated_at = datetime.utcnow()
        await self._drafts.save()

        return ConfirmResult(created=True, already_exists=False, crm_request_id=req.crm_request_id)