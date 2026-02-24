# app/services/drafts.py

from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Optional

from app.config import settings
from app.models import Direction, Draft
from app.repositories.drafts import DraftRepository


class DraftService:
    def __init__(self, repo: DraftRepository) -> None:
        self._repo = repo

    async def get(self, transport: str, peer_id: int) -> Optional[Draft]:
        return await self._repo.get_by_transport_peer_id(transport, peer_id)

    async def reset(self, transport: str, peer_id: int) -> None:
        draft = await self._repo.get_by_transport_peer_id(transport, peer_id)
        if not draft:
            return

        draft.direction = None
        draft.give_amount = None
        draft.office_id = None
        draft.desired_date = None
        draft.username = None
        draft.client_request_id = None
        draft.last_step = "start"
        draft.updated_at = datetime.utcnow()
        await self._repo.save()

    async def reset_for_new_request(
        self,
        transport: str,
        peer_id: int,
        *,
        telegram_user_id: int | None = None,
    ) -> None:
        draft = await self._repo.get_or_create(
            transport=transport,
            peer_id=peer_id,
            telegram_user_id=telegram_user_id,
        )

        draft.direction = None
        draft.give_amount = None
        draft.office_id = None
        draft.desired_date = None
        draft.username = None
        draft.client_request_id = None

        draft.nudge2_planned_at = None
        draft.nudge2_sent_at = None
        draft.nudge2_answer = None
        draft.nudge2_answered_at = None

        draft.step6_at = None
        draft.nudge3_planned_at = None
        draft.nudge3_sent_at = None
        draft.nudge3_answer = None

        draft.nudge4_planned_at = None
        draft.nudge4_sent_at = None
        draft.nudge4_answer = None

        draft.last_step = "start"
        draft.updated_at = datetime.utcnow()

        await self._repo.save()

    async def set_direction(
        self,
        transport: str,
        peer_id: int,
        direction: Direction,
        *,
        telegram_user_id: int | None = None,
    ) -> None:
        draft = await self._repo.get_or_create(
            transport=transport,
            peer_id=peer_id,
            telegram_user_id=telegram_user_id,
        )
        draft.direction = direction
        draft.last_step = "amount_wait"
        draft.updated_at = datetime.utcnow()
        await self._repo.save()

    async def set_amount(
        self,
        transport: str,
        peer_id: int,
        amount: float,
        *,
        telegram_user_id: int | None = None,
    ) -> None:
        draft = await self._repo.get_or_create(
            transport=transport,
            peer_id=peer_id,
            telegram_user_id=telegram_user_id,
        )

        draft.give_amount = float(amount)
        draft.last_step = "amount_wait"
        draft.updated_at = datetime.utcnow()

        if settings.nudge2_test_mode:
            delay = timedelta(seconds=settings.nudge2_test_delay_seconds)
        else:
            delay = timedelta(minutes=settings.nudge2_delay_minutes)

        draft.nudge2_planned_at = datetime.utcnow() + delay
        draft.nudge2_sent_at = None
        draft.nudge2_answer = None

        await self._repo.save()

    async def set_office(self, transport: str, peer_id: int, office_id: str) -> None:
        draft = await self._repo.get_or_create(transport=transport, peer_id=peer_id)
        draft.office_id = office_id
        draft.last_step = "date_wait"
        draft.updated_at = datetime.utcnow()

        draft.nudge2_planned_at = None
        draft.nudge2_sent_at = None
        draft.nudge2_answer = "continued"

        await self._repo.save()

    async def set_date(self, transport: str, peer_id: int, desired_date: date) -> None:
        draft = await self._repo.get_or_create(transport=transport, peer_id=peer_id)
        draft.desired_date = desired_date
        draft.last_step = "summary_wait"
        draft.updated_at = datetime.utcnow()
        await self._repo.save()

    async def set_username(self, transport: str, peer_id: int, username: str) -> None:
        draft = await self._repo.get_or_create(transport=transport, peer_id=peer_id)
        draft.username = username
        draft.last_step = "summary"
        draft.updated_at = datetime.utcnow()
        await self._repo.save()