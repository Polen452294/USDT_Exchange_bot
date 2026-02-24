from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.services.nudges import NudgeService
from app.vk.sender import send_vk_message

log = logging.getLogger("nudges")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    service = NudgeService(bot=None, vk_sender=send_vk_message)

    interval = int(getattr(Settings, "nudge_worker_interval_seconds", 60))
    log.info("vk nudge worker started, interval=%s", interval)

    while True:
        try:
            await service.tick(transport_filter="vk")
        except Exception:
            log.exception("vk nudge loop failed")
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())