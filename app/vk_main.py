import asyncio
import logging

from app.config import settings
from app.startup import on_startup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vk")


async def process() -> None:
    if getattr(settings, "DB_AUTO_CREATE", False):
        await on_startup()

    from app.vk.bot import run_vk_bot
    await run_vk_bot()


def main() -> None:
    asyncio.run(process())


if __name__ == "__main__":
    main()