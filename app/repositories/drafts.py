from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Draft


class DraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_transport_peer_id(self, transport: str, peer_id: int) -> Draft | None:
        return await self._session.scalar(
            select(Draft).where(Draft.transport == transport, Draft.peer_id == peer_id)
        )

    async def get_or_create(
        self,
        transport: str,
        peer_id: int,
        *,
        telegram_user_id: int | None = None,
    ) -> Draft:
        draft = await self.get_by_transport_peer_id(transport, peer_id)
        if draft:
            if telegram_user_id is not None and draft.telegram_user_id is None:
                draft.telegram_user_id = telegram_user_id
                await self._session.commit()
            return draft

        draft = Draft(
            transport=transport,
            peer_id=peer_id,
            telegram_user_id=telegram_user_id,
            last_step="start",
        )
        self._session.add(draft)
        await self._session.commit()
        return draft

    async def save(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()