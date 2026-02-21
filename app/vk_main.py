import os
import asyncio
import logging

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

from app.vk.router import VKRouter

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vk")


def main():
    token = os.getenv("VK_GROUP_TOKEN")
    group_id = int(os.getenv("VK_GROUP_ID"))

    vk_session = vk_api.VkApi(token=token)
    api = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id)

    router = VKRouter()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue

        msg = event.object.message

        peer_id = int(msg["peer_id"])
        from_id = int(msg["from_id"])
        text = msg.get("text", "")

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