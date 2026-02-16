from __future__ import annotations
import asyncio
from sqlalchemy import text

from app.handlers import start, amount, office, date, username, summary, nudge2
from app.bootstrap import build_bot, build_dispatcher, setup_logging
from app.db import engine
from app.models import Base
from app.config import settings


async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge2_planned_at TIMESTAMP NULL
        """))


async def main() -> None:
    setup_logging()
    await on_startup()

    bot = build_bot()
    dp = build_dispatcher()

    dp.include_router(nudge2.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())