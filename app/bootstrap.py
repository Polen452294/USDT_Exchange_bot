from __future__ import annotations

import logging
from typing import Any, Dict

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import TelegramObject

from app.repositories.drafts import DraftRepository
from app.repositories.requests import RequestRepository
from app.services.drafts import DraftService
from app.services.requests import RequestService
from app.db import AsyncSessionLocal
from app.handlers import admin, nudge3, nudge4, nudge5, nudge6, nudge7, start, amount, office, date, username, summary, nudge2, nudge1
from app.config import settings
from app.db import AsyncSessionLocal


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)


def build_bot() -> Bot:
    return Bot(token=settings.BOT_TOKEN)


def build_dispatcher() -> Dispatcher:
    from app.handlers import start, amount, office, date, username, summary

    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware())

    dp.include_router(start.router)
    dp.include_router(amount.router)
    dp.include_router(office.router)
    dp.include_router(date.router)
    dp.include_router(username.router)
    dp.include_router(summary.router)
    dp.include_router(nudge1.router)
    dp.include_router(nudge2.router)
    dp.include_router(nudge3.router)
    dp.include_router(nudge4.router)
    dp.include_router(nudge5.router)
    dp.include_router(nudge6.router)
    dp.include_router(nudge7.router)
    dp.include_router(admin.router)

    return dp

def build_services(session):
    draft_repo = DraftRepository(session)
    request_repo = RequestRepository(session)

    draft_service = DraftService(draft_repo)
    request_service = RequestService(draft_repo, request_repo)

    return draft_service, request_service