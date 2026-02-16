from __future__ import annotations

from datetime import datetime
from app.models import Direction
from app.repositories.drafts import DraftRepository


class DraftService:
    def __init__(self, repo: DraftRepository) -> None:
        self._repo = repo

    async def set_direction(self, telegram_user_id: int, direction: Direction) -> None:
        draft = await self._repo.get_or_create(telegram_user_id)
        draft.direction = direction
        draft.last_step = "amount_wait"
        draft.updated_at = datetime.utcnow()
        await self._repo.save()

    async def set_amount(self, telegram_user_id: int, amount: float) -> None:
        draft = await self._repo.get_or_create(telegram_user_id)
        draft.give_amount = float(amount)
        draft.last_step = "amount"
        draft.updated_at = datetime.utcnow()
        await self._repo.save()