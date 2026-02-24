from __future__ import annotations

import asyncio

from app.bootstrap import build_bot, setup_logging
from app.infrastructure.worker import run_nudge_worker
from app.vk.sender import send_vk_message


async def main() -> None:
    setup_logging()
    bot = build_bot()
    await run_nudge_worker(bot, vk_sender=send_vk_message)


if __name__ == "__main__":
    asyncio.run(main())