from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.services.nudges import NudgeService

log = logging.getLogger("nudges")

# Фиксированный ключ advisory lock.
# Важно: одинаковый ключ = один воркер на одну БД.
WORKER_LOCK_KEY = 91234567


async def _acquire_worker_lock() -> bool:
    """
    Пытаемся захватить pg advisory lock.
    Если уже захвачен другим процессом — второй воркер не стартует.
    """
    async with engine.begin() as conn:
        locked = await conn.scalar(
            text("SELECT pg_try_advisory_lock(:k)"),
            {"k": WORKER_LOCK_KEY},
        )
        return bool(locked)


async def _release_worker_lock() -> None:
    """
    Освобождаем advisory lock при завершении.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT pg_advisory_unlock(:k)"),
            {"k": WORKER_LOCK_KEY},
        )


async def _db_ping() -> None:
    """
    Проверка соединения с БД перед запуском цикла.
    """
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def run_nudge_worker(
    bot: Bot,
    *,
    vk_sender=None,
    transport_filter: str | None = None,
) -> None:
    """
    Основной цикл воркера дожимов.
    transport_filter:
        None — обрабатываем все транспорты
        "tg" — только Telegram
        "vk" — только VK
    """

    interval = int(settings.nudge_worker_interval_seconds)

    # Захват advisory lock
    ok = await _acquire_worker_lock()
    if not ok:
        log.critical(
            "nudge worker already running: advisory lock busy (key=%s)",
            WORKER_LOCK_KEY,
        )
        return

    try:
        # Проверка БД
        await _db_ping()

        log.info(
            "nudge worker started | interval=%s | transport_filter=%s",
            interval,
            transport_filter,
        )

        service = NudgeService(bot, vk_sender=vk_sender)

        while True:
            try:
                await service.tick(transport_filter=transport_filter)
            except Exception:
                log.exception("nudge loop failed")

            await asyncio.sleep(interval)

    finally:
        with suppress(Exception):
            await _release_worker_lock()