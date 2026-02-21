from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.drafts import DraftRepository
from app.repositories.requests import RequestRepository
from app.services.drafts import DraftService
from app.services.requests import RequestService


def build_services(session: AsyncSession):
    draft_repo = DraftRepository(session)
    request_repo = RequestRepository(session)

    draft_service = DraftService(draft_repo)
    request_service = RequestService(draft_repo, request_repo)

    return draft_service, request_service