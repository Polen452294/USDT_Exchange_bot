from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Draft


class DraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, telegram_user_id: int) -> Draft | None:
        return await self._session.scalar(
            select(Draft).where(Draft.telegram_user_id == telegram_user_id)
        )

    async def get_or_create(self, telegram_user_id: int) -> Draft:
        draft = await self.get_by_user_id(telegram_user_id)
        if draft:
            return draft

        draft = Draft(telegram_user_id=telegram_user_id, last_step="start")
        self._session.add(draft)
        await self._session.commit()
        return draft

    async def save(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()