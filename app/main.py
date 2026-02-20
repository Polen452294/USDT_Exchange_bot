from __future__ import annotations

import asyncio
from sqlalchemy import text

from app.bootstrap import build_bot, build_dispatcher, setup_logging
from app.config import settings
from app.db import engine
from app.models import Base
from app.handlers import start, amount, office, date, username, summary, nudge2, nudge3
from aiogram.types import BotCommand
from aiogram.enums import BotCommandScopeType
from aiogram.methods import SetMyCommands
from aiogram.types import BotCommandScopeAllPrivateChats, BotCommandScopeChat

async def setup_bot_commands(bot) -> None:
    user_cmds = [
        BotCommand(command="start", description="Начать заново"),
    ]

    admin_cmds = user_cmds + [
        BotCommand(command="admin_requests", description="Последние 10 заявок"),
        BotCommand(command="admin_request", description="Детали заявки по id"),
        BotCommand(command="admin_crm_get", description="CRM статус по заявке"),
        BotCommand(command="admin_crm_set", description="Установить CRM статус (mock)"),
        BotCommand(command="admin_crm_events", description="События в CRM (mock)"),
    ]

    await bot(SetMyCommands(commands=user_cmds, scope=BotCommandScopeAllPrivateChats()))

    for admin_id in settings.admin_ids:
        await bot(SetMyCommands(commands=admin_cmds, scope=BotCommandScopeChat(chat_id=admin_id)))

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
        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge2_answered_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge4_planned_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge5_planned_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge5_sent_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge5_answer VARCHAR(32) NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge5_answered_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge6_planned_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge6_sent_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge6_answer VARCHAR(32) NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge6_answered_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge7_planned_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge7_sent_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge7_answer VARCHAR(32) NULL
        """))
        await conn.execute(text("""
            ALTER TABLE requests
            ADD COLUMN IF NOT EXISTS nudge7_answered_at TIMESTAMP NULL
        """))
        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge2_sent_at TIMESTAMP NULL
        """))

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge2_answer VARCHAR(32) NULL
        """))

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge3_sent_at TIMESTAMP NULL
        """))

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge3_answer VARCHAR(32) NULL
        """))

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge3_answered_at TIMESTAMP NULL
        """))

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge4_sent_at TIMESTAMP NULL
        """))

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge4_answer VARCHAR(32) NULL
        """))

        await conn.execute(text("""
            ALTER TABLE drafts
            ADD COLUMN IF NOT EXISTS nudge4_answered_at TIMESTAMP NULL
        """))



async def main() -> None:
    setup_logging()
    await on_startup()

    bot = build_bot()
    await setup_bot_commands(bot)

    dp = build_dispatcher()
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())