from __future__ import annotations

from datetime import datetime, date
from typing import Optional

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
        draft.last_step = "office_wait"
        draft.updated_at = datetime.utcnow()
        await self._repo.save()

    async def set_office(self, transport: str, peer_id: int, office_id: str) -> None:
        draft = await self._repo.get_or_create(transport=transport, peer_id=peer_id)
        draft.office_id = office_id
        draft.last_step = "date_wait"
        draft.updated_at = datetime.utcnow()
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