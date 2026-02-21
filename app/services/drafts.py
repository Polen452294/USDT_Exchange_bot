from __future__ import annotations

from datetime import datetime

from app.models import Direction
from app.repositories.drafts import DraftRepository


class DraftService:
    def __init__(self, repo: DraftRepository) -> None:
        self._repo = repo

    async def set_direction(self, transport: str, peer_id: int, direction: Direction, *, telegram_user_id: int | None = None) -> None:
        draft = await self._repo.get_or_create(transport=transport, peer_id=peer_id, telegram_user_id=telegram_user_id)
        draft.direction = direction
        draft.last_step = "amount_wait"
        draft.updated_at = datetime.utcnow()
        await self._repo.save()

    async def set_amount(self, transport: str, peer_id: int, amount: float, *, telegram_user_id: int | None = None) -> None:
        draft = await self._repo.get_or_create(transport=transport, peer_id=peer_id, telegram_user_id=telegram_user_id)
        draft.give_amount = float(amount)
        draft.last_step = "amount"
        draft.updated_at = datetime.utcnow()
        await self._repo.save()