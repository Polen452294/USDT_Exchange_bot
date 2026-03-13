from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Optional, Any

import vk_api

from app.config import settings


_STATE_PATH = Path(".vk_message_state.json")


def _load_state() -> dict[str, Any]:
    if not _STATE_PATH.exists():
        return {}
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    _STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _state_key(peer_id: int, edit_key: str) -> str:
    return f"{int(peer_id)}:{edit_key}"


def _normalize_slot(value: Any) -> dict[str, int] | None:
    if value is None:
        return None

    if isinstance(value, int):
        return {"conversation_message_id": int(value)}

    if isinstance(value, dict):
        slot: dict[str, int] = {}
        if value.get("conversation_message_id") is not None:
            slot["conversation_message_id"] = int(value["conversation_message_id"])
        if value.get("message_id") is not None:
            slot["message_id"] = int(value["message_id"])
        return slot or None

    return None


def _extract_conversation_message_id(api, message_id: int) -> int | None:
    try:
        resp = api.messages.getById(message_ids=message_id)
        items = (resp or {}).get("items") or []
        if not items:
            return None
        cmid = items[0].get("conversation_message_id")
        if cmid is None:
            return None
        return int(cmid)
    except Exception:
        return None


def _delete_previous_message(api, peer_id: int, slot: dict[str, int] | None) -> None:
    if not slot:
        return

    message_id = slot.get("message_id")
    conversation_message_id = slot.get("conversation_message_id")

    if message_id is not None:
        try:
            api.messages.delete(
                message_ids=message_id,
                delete_for_all=1,
                peer_id=int(peer_id),
            )
            return
        except Exception:
            pass

    if conversation_message_id is not None:
        try:
            api.messages.delete(
                peer_id=int(peer_id),
                conversation_message_ids=conversation_message_id,
                delete_for_all=1,
            )
        except Exception:
            pass


def _send_sync(
    peer_id: int,
    text: str,
    keyboard: Optional[str] = None,
    *,
    edit: bool = True,
    edit_key: str = "nudge",
) -> None:
    vk_session = vk_api.VkApi(token=settings.VK_TOKEN)
    api = vk_session.get_api()

    state = _load_state()
    skey = _state_key(peer_id, edit_key)
    slot = _normalize_slot(state.get(skey))

    if edit:
        _delete_previous_message(api, int(peer_id), slot)

    params = {
        "peer_id": int(peer_id),
        "message": str(text),
        "random_id": random.randint(1, 2_000_000_000),
    }
    if keyboard is not None:
        params["keyboard"] = keyboard

    message_id = int(api.messages.send(**params))
    conversation_message_id = _extract_conversation_message_id(api, message_id)

    state[skey] = {
        "message_id": message_id,
        "conversation_message_id": conversation_message_id,
    }
    _save_state(state)


async def send_vk_message(
    peer_id: int,
    text: str,
    *,
    keyboard: str | None = None,
    edit: bool = True,
    edit_key: str = "nudge",
) -> None:
    await asyncio.to_thread(
        _send_sync,
        peer_id,
        text,
        keyboard,
        edit=edit,
        edit_key=edit_key,
    )


async def clear_vk_message_slot(peer_id: int, edit_key: str) -> None:
    def _clear() -> None:
        state = _load_state()
        state.pop(_state_key(peer_id, edit_key), None)
        _save_state(state)

    await asyncio.to_thread(_clear)