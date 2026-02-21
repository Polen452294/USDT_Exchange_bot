from __future__ import annotations

from typing import Protocol


class Messenger(Protocol):
    async def send_text(self, peer_id: int, text: str) -> None:
        ...