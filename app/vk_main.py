import os
import asyncio
import logging

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from app.config import settings
from app.vk.router import VKRouter

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vk")


def main():
    token = settings.VK_GROUP_TOKEN
    group_id = settings.VK_GROUP_ID

    if not token or not group_id:
        raise RuntimeError("VK_GROUP_TOKEN and VK_GROUP_ID are required")

    vk_session = vk_api.VkApi(token=token)
    api = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id)

    router = VKRouter()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    log.info("VK bot started, group_id=%s", group_id)

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        msg = event.object.message

        peer_id = int(msg["peer_id"])
        from_id = int(msg["from_id"])
        text = msg.get("text", "")

        log.info("VK message: peer_id=%s from_id=%s text=%r", peer_id, from_id, text)

        if peer_id != from_id:
            continue

        async def process():
            response = await router.handle(peer_id, from_id, text)
            if response:
                await asyncio.to_thread(
                    api.messages.send,
                    peer_id=peer_id,
                    random_id=0,
                    message=response,
                )

        loop.run_until_complete(process())


if __name__ == "__main__":
    main()