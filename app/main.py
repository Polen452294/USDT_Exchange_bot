from __future__ import annotations

import asyncio

from app.bootstrap import build_bot, build_dispatcher, setup_logging
from app.db import engine
from app.models import Base
from app.config import settings


async def on_startup() -> None:
    if getattr(settings, "DB_AUTO_CREATE", True):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def main() -> None:
    setup_logging()
    await on_startup()

    bot = build_bot()
    dp = build_dispatcher()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())