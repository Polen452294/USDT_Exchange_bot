from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import TelegramObject

from app.config import settings
from app.db import AsyncSessionLocal, engine
from app.models import Base

# handlers
from app.handlers import start, amount, office, date, username, summary


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def on_startup() -> None:
    # MVP: создаём таблицы автоматически (позже заменим на Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: Dict[str, Any]):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)


async def main() -> None:
    setup_logging()
    await on_startup()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # middleware (сессия БД в data["session"])
    dp.update.middleware(DbSessionMiddleware())

    # роутеры
    dp.include_router(start.router)
    dp.include_router(amount.router)
    dp.include_router(office.router)
    dp.include_router(date.router)
    dp.include_router(username.router)
    dp.include_router(summary.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())