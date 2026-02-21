from sqlalchemy.ext.asyncio import AsyncSession

from app.container import build_services
from app.db import AsyncSessionLocal
from app.models import Direction


class VKRouter:
    async def handle(self, peer_id: int, user_id: int, text: str):
        async with AsyncSessionLocal() as session:  # type: AsyncSession
            draft_service, request_service = build_services(session)

            t = (text or "").strip().lower()

            if t in ("/start", "start", "меню"):
                return "Привет! Напишите «обмен», чтобы создать заявку."

            if t == "обмен":
                return "Выберите направление:\n1) USDT → Наличные\n2) Наличные → USDT"

            if t == "1":
                await draft_service.set_direction("vk", peer_id, Direction.USDT_TO_CASH)
                return "Введите сумму, которую вы отдаёте."

            if t == "2":
                await draft_service.set_direction("vk", peer_id, Direction.CASH_TO_USDT)
                return "Введите сумму, которую вы отдаёте."

            if t.replace(".", "", 1).isdigit():
                await draft_service.set_amount("vk", peer_id, float(t))
                return "Сумму записал. Дальше подключим офис и дату."

            return "Не понял сообщение. Напишите «обмен»."