import asyncio
import vk_api
from app.infrastructure.messenger import Messenger


class VKMessenger(Messenger):
    def __init__(self, token: str):
        self._session = vk_api.VkApi(token=token)
        self._api = self._session.get_api()

    async def send_text(self, peer_id: int, text: str) -> None:
        await asyncio.to_thread(
            self._api.messages.send,
            peer_id=peer_id,
            random_id=0,
            message=text,
        )