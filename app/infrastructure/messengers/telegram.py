from aiogram import Bot
from app.infrastructure.messenger import Messenger


class TelegramMessenger(Messenger):
    def __init__(self, bot: Bot):
        self._bot = bot

    async def send_text(self, peer_id: int, text: str) -> None:
        await self._bot.send_message(chat_id=peer_id, text=text)