from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.config import settings
from app.services.nudges import NudgeService


log = logging.getLogger("nudges")


async def run_nudge_worker(bot: Bot) -> None:
    interval = int(getattr(settings, "nudge_worker_interval_seconds", 60))
    service = NudgeService(bot)

    while True:
        try:
            await service.tick()
        except Exception:
            log.exception("nudge loop failed")
        await asyncio.sleep(interval)