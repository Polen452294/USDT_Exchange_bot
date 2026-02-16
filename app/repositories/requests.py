from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Request


class RequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_client_request_id(self, client_request_id: str) -> Request | None:
        return await self._session.scalar(
            select(Request).where(Request.client_request_id == client_request_id)
        )

    async def create(self, request: Request) -> None:
        self._session.add(request)
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()