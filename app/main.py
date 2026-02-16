from __future__ import annotations

import asyncio
from sqlalchemy import text

from app.bootstrap import build_bot, build_dispatcher, setup_logging
from app.config import settings
from app.db import engine
from app.models import Base
from app.handlers import start, amount, office, date, username, summary, nudge2, nudge3


async def on_startup() -> None:
    async with engine.begin() as conn:
        if settings.DB_AUTO_CREATE:
            await conn.run_sync(Base.metadata.create_all)

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge2_planned_at TIMESTAMP NULL
        """))

        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge1_planned_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge1_sent_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge1_answer VARCHAR(32) NULL
        """))

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS step6_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge3_planned_at TIMESTAMP NULL
        """))


async def main() -> None:
    setup_logging()
    await on_startup()

    bot = build_bot()
    dp = build_dispatcher()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())