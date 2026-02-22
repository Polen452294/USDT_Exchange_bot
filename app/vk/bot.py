import asyncio
import logging
from typing import Optional

import vk_api
from vk_api.longpoll import VkEventType, VkLongPoll

from app.config import settings
from app.db import AsyncSessionLocal

logger = logging.getLogger("vk")


def _send(api, peer_id: int, text: str, keyboard: Optional[dict] = None) -> None:
    params = {"peer_id": peer_id, "message": text, "random_id": 0}
    if keyboard is not None:
        params["keyboard"] = keyboard

    try:
        api.messages.send(**params)
    except vk_api.exceptions.ApiError as e:
        code = getattr(e, "code", None)
        if code == 912:
            params.pop("keyboard", None)
            api.messages.send(**params)
            return
        raise


def _vk_profile_url(api, user_id: int) -> str:
    try:
        info = api.users.get(user_ids=user_id, fields="domain")[0]
        domain = (info.get("domain") or "").strip()
        if domain:
            return f"https://vk.com/{domain}"
    except Exception:
        pass
    return f"https://vk.com/id{user_id}"


async def run_vk_bot() -> None:
    vk_session = vk_api.VkApi(token=settings.VK_TOKEN)
    api = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    loop = asyncio.get_running_loop()

    logger.info("VK bot started, group_id=%s", getattr(settings, "VK_GROUP_ID", None))

    from app.container import build_services
    from app.vk.handlers import handle_vk_message

    while True:
        events = await loop.run_in_executor(None, longpoll.check)
        for ev in events:
            if ev.type != VkEventType.MESSAGE_NEW:
                continue
            if not getattr(ev, "to_me", False):
                continue

            peer_id = int(getattr(ev, "peer_id", 0) or 0)
            user_id = int(getattr(ev, "user_id", 0) or 0)
            text = str(getattr(ev, "text", "") or "")

            logger.info("VK message: peer_id=%s user_id=%s text=%r", peer_id, user_id, text)

            try:
                vk_profile_url = await loop.run_in_executor(None, _vk_profile_url, api, user_id)

                async with AsyncSessionLocal() as session:
                    draft_service, request_service = build_services(session)

                    class _Container:
                        pass

                    container = _Container()
                    container.drafts_service = draft_service
                    container.requests_service = request_service

                    result = await handle_vk_message(
                        container,
                        peer_id=peer_id,
                        user_id=user_id,
                        text=text,
                        vk_profile_url=vk_profile_url,
                    )

                if not result:
                    continue

                out_text = str(result.get("text", "") or "")
                out_kb = result.get("keyboard")

                if out_text:
                    try:
                        await loop.run_in_executor(None, _send, api, peer_id, out_text, out_kb)
                    except Exception:
                        logger.exception("VK send failed: peer_id=%s", peer_id)

            except Exception:
                logger.exception("vk handler failed: peer_id=%s user_id=%s text=%r", peer_id, user_id, text)
                try:
                    await loop.run_in_executor(None, _send, api, peer_id, "Произошла ошибка. Попробуйте ещё раз.", None)
                except Exception:
                    logger.exception("VK error message send failed: peer_id=%s", peer_id)