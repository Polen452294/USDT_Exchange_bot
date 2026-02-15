from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select

from app.config import settings
from app.db import AsyncSessionLocal
from app.models import Draft

log = logging.getLogger("nudges")

NUDGE2_TEXT = (
    "Похоже, вы отвлеклись.\n"
    "Если хотите, я могу продолжить с того места, где вы остановились. "
    "Нажмите «Продолжить», и я покажу сводку и текущий курс."
)

STEPS_FOR_NUDGE2 = [
    "amount_wait",
    "amount",
    "office",
    "date",
    "date_default",
    "username_auto",
    "username_manual",
    "summary",
]


async def run_nudge_worker(bot: Bot):
    interval = int(getattr(settings, "nudge_worker_interval_seconds", 60))

    while True:
        try:
            await check_nudge2(bot)
        except Exception:
            log.exception("n2 loop failed")
        await asyncio.sleep(interval)


async def check_nudge2(bot: Bot):
    delay = int(getattr(settings, "nudge2_delay_seconds", 900))
    now = datetime.utcnow()
    deadline = now - timedelta(seconds=delay)

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Draft)
            .where(Draft.last_step.in_(STEPS_FOR_NUDGE2))
            .where(Draft.nudge2_answer.is_(None))
            .where(Draft.nudge2_sent_at.is_(None))
            .where(Draft.updated_at <= deadline)
        )
        drafts = list(res.scalars().all())

        if drafts:
            log.info("n2 candidates=%d", len(drafts))

        for d in drafts:
            try:
                await bot.send_message(d.telegram_user_id, NUDGE2_TEXT)
                d.nudge2_sent_at = datetime.utcnow()
                await session.commit()
                log.info("n2 sent: uid=%s last_step=%s", d.telegram_user_id, d.last_step)
            except Exception:
                await session.rollback()
                log.exception("n2 send failed: uid=%s", d.telegram_user_id)