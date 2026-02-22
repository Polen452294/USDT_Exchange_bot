import asyncio
import logging

from app.config import settings
from app.db import engine
from app.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vk")


async def ensure_db_schema() -> None:
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def process() -> None:
    if getattr(settings, "DB_AUTO_CREATE", False):
        await ensure_db_schema()

    from app.vk.bot import run_vk_bot

    await run_vk_bot()


def main() -> None:
    asyncio.run(process())


if __name__ == "__main__":
    main()