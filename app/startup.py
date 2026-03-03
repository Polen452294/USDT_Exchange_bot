from __future__ import annotations

from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.models import Base


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