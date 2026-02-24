from __future__ import annotations

import asyncio
import json
import random
from typing import Any, Optional

import vk_api

from app.config import settings


def _send_sync(peer_id: int, text: str, keyboard: Optional[str] = None) -> None:
    vk_session = vk_api.VkApi(token=settings.VK_TOKEN)
    api = vk_session.get_api()

    params = {
        "peer_id": int(peer_id),
        "message": str(text),
        "random_id": random.randint(1, 2_000_000_000),
    }
    if keyboard is not None:
        params["keyboard"] = keyboard

    api.messages.send(**params)


async def send_vk_message(peer_id: int, text: str, *, keyboard: str | None = None) -> None:
    await asyncio.to_thread(_send_sync, peer_id, text, keyboard)