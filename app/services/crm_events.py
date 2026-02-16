import uuid
from app.infrastructure.crm_client import get_crm_client


async def send_nudge_event(draft, nudge_type: str, action: str):
    crm = get_crm_client()

    event_id = uuid.uuid4().hex

    payload = {
        "event_id": event_id,
        "event_type": nudge_type,
        "action": action,
        "telegram_user_id": draft.telegram_user_id,
        "client_request_id": draft.client_request_id,
    }

    await crm.send_event(payload, idempotency_key=event_id)