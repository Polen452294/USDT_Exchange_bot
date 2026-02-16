from __future__ import annotations

import asyncio

from app.bootstrap import build_bot, setup_logging
from app.infrastructure.worker import run_nudge_worker


async def main() -> None:
    setup_logging()
    bot = build_bot()
    await run_nudge_worker(bot)


if __name__ == "__main__":
    asyncio.run(main())