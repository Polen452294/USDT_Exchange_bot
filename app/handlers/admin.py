from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.crm_client import get_crm_client
from app.models import Request

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


def _deny_text() -> str:
    return "Команда доступна только администратору."


@router.message(Command("admin_requests"))
async def admin_requests(message: Message, session: AsyncSession):
    if not _is_admin(message.from_user.id):
        await message.answer(_deny_text())
        return

    rows = (
        await session.execute(
            select(Request)
            .order_by(Request.id.desc())
            .limit(10)
        )
    ).scalars().all()

    if not rows:
        await message.answer("Заявок пока нет.")
        return

    lines = ["Последние заявки:"]
    for r in rows:
        lines.append(
            f"• #{r.id} | uid={r.telegram_user_id} | office={r.office_id} | date={r.desired_date} | crm={r.crm_request_id or '-'}"
        )

    await message.answer("\n".join(lines))


@router.message(Command("admin_request"))
async def admin_request(message: Message, session: AsyncSession):
    if not _is_admin(message.from_user.id):
        await message.answer(_deny_text())
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /admin_request <request_id>")
        return

    try:
        req_id = int(parts[1])
    except Exception:
        await message.answer("request_id должен быть числом.")
        return

    req = await session.get(Request, req_id)
    if not req:
        await message.answer("Заявка не найдена.")
        return

    text = (
        f"Заявка #{req.id}\n"
        f"uid: {req.telegram_user_id}\n"
        f"crm_request_id: {req.crm_request_id or '-'}\n"
        f"direction: {getattr(req.direction, 'value', req.direction)}\n"
        f"give_amount: {req.give_amount}\n"
        f"office_id: {req.office_id}\n"
        f"desired_date: {req.desired_date}\n"
        f"rate: {req.rate}\n"
        f"receive_amount: {req.receive_amount}\n"
        f"username: {req.username}\n\n"
        f"n5: planned={req.nudge5_planned_at} sent={req.nudge5_sent_at} answer={req.nudge5_answer}\n"
        f"n6: planned={req.nudge6_planned_at} sent={req.nudge6_sent_at} answer={req.nudge6_answer}\n"
        f"n7: planned={req.nudge7_planned_at} sent={req.nudge7_sent_at} answer={req.nudge7_answer}\n"
    )

    await message.answer(text)


@router.message(Command("admin_crm_get"))
async def admin_crm_get(message: Message, session: AsyncSession):
    if not _is_admin(message.from_user.id):
        await message.answer(_deny_text())
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /admin_crm_get <request_id>")
        return

    try:
        req_id = int(parts[1])
    except Exception:
        await message.answer("request_id должен быть числом.")
        return

    req = await session.get(Request, req_id)
    if not req or not req.crm_request_id:
        await message.answer("Заявка не найдена или у неё нет crm_request_id.")
        return

    crm = get_crm_client()
    st = await crm.check_status(str(req.crm_request_id))
    status = str(st.get("status") or "")
    await message.answer(f"CRM status для заявки #{req.id}: {status or '-'}")


@router.message(Command("admin_crm_set"))
async def admin_crm_set(message: Message, session: AsyncSession):
    if not _is_admin(message.from_user.id):
        await message.answer(_deny_text())
        return

    if (settings.crm_mode or "mock").strip().lower() != "mock":
        await message.answer("Команда доступна только в crm_mode=mock.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /admin_crm_set <request_id> <status>")
        return

    try:
        req_id = int(parts[1])
    except Exception:
        await message.answer("request_id должен быть числом.")
        return

    status = parts[2].strip()
    if not status:
        await message.answer("status не может быть пустым.")
        return

    req = await session.get(Request, req_id)
    if not req or not req.crm_request_id:
        await message.answer("Заявка не найдена или у неё нет crm_request_id.")
        return

    crm = get_crm_client()
    if not hasattr(crm, "mock_set_status"):
        await message.answer("Текущий CRM клиент не поддерживает mock_set_status.")
        return

    await crm.mock_set_status(str(req.crm_request_id), status)
    await message.answer(f"Установлен CRM status для заявки #{req.id}: {status}")


@router.message(Command("admin_crm_events"))
async def admin_crm_events(message: Message, session: AsyncSession):
    if not _is_admin(message.from_user.id):
        await message.answer(_deny_text())
        return

    if (settings.crm_mode or "mock").strip().lower() != "mock":
        await message.answer("Команда доступна только в crm_mode=mock.")
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /admin_crm_events <request_id>")
        return

    try:
        req_id = int(parts[1])
    except Exception:
        await message.answer("request_id должен быть числом.")
        return

    req = await session.get(Request, req_id)
    if not req or not req.crm_request_id:
        await message.answer("Заявка не найдена или у неё нет crm_request_id.")
        return

    crm = get_crm_client()
    if not hasattr(crm, "mock_get_events"):
        await message.answer("Текущий CRM клиент не поддерживает mock_get_events.")
        return

    events = await crm.mock_get_events(limit=30)
    if not events:
        await message.answer("Событий пока нет.")
        return

    lines = ["Последние события (mock CRM):"]
    for e in events[-10:]:
        payload = e.get("payload") or {}
        lines.append(f"• {payload.get('type') or payload.get('nudge_type') or '-'} | {payload.get('action') or payload.get('answer') or '-'}")

    await message.answer("\n".join(lines))