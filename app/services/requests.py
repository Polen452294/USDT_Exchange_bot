from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from app.config import settings
from sqlalchemy.exc import IntegrityError

from app.models import Draft, Request, Direction
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

    async def ensure_client_request_id(self, draft: Draft) -> str:
        if draft.client_request_id:
            return draft.client_request_id
        draft.client_request_id = _new_client_request_id()
        draft.updated_at = datetime.utcnow()
        await self._drafts.save()
        return draft.client_request_id

    async def build_summary(self, telegram_user_id: int) -> SummaryResult:
        draft = await self._drafts.get_by_user_id(telegram_user_id)
        if draft is None:
            raise ValueError("draft_not_found")

        if not draft.direction or not draft.give_amount or not draft.office_id or not draft.desired_date:
            raise ValueError("draft_not_ready")

        direction = draft.direction.value if isinstance(draft.direction, Direction) else str(draft.direction)
        if direction not in ("USDT_TO_CASH", "CASH_TO_USDT"):
            raise ValueError("bad_direction")

        await self.ensure_client_request_id(draft)

        crm = get_crm_client()
        try:
            rate = await crm.get_rate(str(draft.office_id), direction)  # type: ignore[arg-type]
            office_label = await crm.get_office_label(str(draft.office_id))
        except (CRMTemporaryError, CRMPermanentError):
            log.exception("CRM error on summary (office_id=%s, direction=%s)", draft.office_id, direction)
            raise
        except Exception:
            log.exception("Unexpected CRM error on summary (office_id=%s, direction=%s)", draft.office_id, direction)
            raise CRMTemporaryError("unexpected_crm_error")

        receive_amount = float(draft.give_amount) * float(rate)

        if direction == "USDT_TO_CASH":
            give_currency = "USDT"
            recv_currency = "наличные"
        else:
            give_currency = "наличные"
            recv_currency = "USDT"

        summary_text = (
            "Почти готово. Проверьте, пожалуйста, данные заявки – покажу всё одним блоком.\n"
            f"➔ Вы отдаёте: {_money(float(draft.give_amount))} {give_currency}\n"
            f"➔ Офис: {office_label}\n"
            f"➔ Дата получения: {draft.desired_date.strftime('%d.%m.%Y')}\n"
            f"➔ Текущий курс: {rate}\n"
            f"➔ Вы получаете: {_money(receive_amount)} {recv_currency}\n\n"
            f"{DISCLAIMER}\n\n"
            "Всё верно?"
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
        draft = await self._drafts.get_by_user_id(telegram_user_id)
        if draft is None:
            raise ValueError("draft_not_found")

        if not draft.direction or not draft.give_amount or not draft.office_id or not draft.desired_date or not draft.username:
            raise ValueError("draft_not_ready")

        client_request_id = await self.ensure_client_request_id(draft)

        existing = await self._requests.get_by_client_request_id(client_request_id)
        if existing is not None:
            return ConfirmResult(created=False, already_exists=True, crm_request_id=existing.crm_request_id)

        if not rate or not receive_amount or not summary_text:
            summary = await self.build_summary(telegram_user_id)
            rate = summary.rate
            receive_amount = summary.receive_amount
            summary_text = summary.summary_text

        req = Request(
            telegram_user_id=telegram_user_id,
            client_request_id=client_request_id,
            crm_request_id=None,
            direction=draft.direction if isinstance(draft.direction, Direction) else Direction(str(draft.direction)),
            give_amount=float(draft.give_amount),
            office_id=str(draft.office_id),
            desired_date=draft.desired_date,
            rate=float(rate),
            receive_amount=float(receive_amount),
            username=str(draft.username),
            summary_text=str(summary_text),
        )
        
        req.nudge1_planned_at = datetime.utcnow() + timedelta(
        seconds=settings.nudge1_delay_seconds
            )
        
        req.nudge1_planned_at = datetime.utcnow() + timedelta(seconds=settings.nudge1_delay_seconds)

        try:
            await self._requests.create(req)
        except IntegrityError:
            await self._requests.rollback()
            existing2 = await self._requests.get_by_client_request_id(client_request_id)
            return ConfirmResult(created=False, already_exists=True, crm_request_id=(existing2.crm_request_id if existing2 else None))

        crm = get_crm_client()
        try:
            crm_resp = await crm.create_request(
                {
                    "client_request_id": client_request_id,
                    "telegram_user_id": telegram_user_id,
                    "direction": req.direction.value,
                    "give_amount": req.give_amount,
                    "office_id": req.office_id,
                    "desired_date": req.desired_date.isoformat(),
                    "username": req.username,
                    "rate": req.rate,
                    "receive_amount": req.receive_amount,
                },
                idempotency_key=client_request_id,
            )
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