from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.crm_client import get_crm_client
from app.models import Draft, Request


def _parse_cmd(text: str) -> tuple[str, list[str]]:
    parts = (text or "").strip().split()
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]


def _vk_admin_peer_ids() -> set[int]:
    ids = getattr(settings, "vk_admin_peer_ids", None)
    if ids:
        return set(int(x) for x in ids)
    return set(int(x) for x in getattr(settings, "admin_ids", []) or [])


def _is_admin(peer_id: int) -> bool:
    admin_ids = _vk_admin_peer_ids()
    if not admin_ids:
        return False
    return int(peer_id) in admin_ids


def _deny() -> dict:
    return {"text": "Команда доступна только администратору.", "keyboard": None}


def _help_text() -> str:
    return (
        "VK admin команды:\n"
        "• /vk_admin_help\n"
        "• /vk_admin_last_requests [limit]\n"
        "• /vk_admin_request <request_id>\n"
        "• /vk_admin_last_drafts [limit]\n"
        "• /vk_admin_draft <draft_id>\n"
        "• /vk_admin_peer\n"
        "• /vk_admin_reset_peer\n"
        "• /vk_admin_nudge_plan <nudge> [seconds]\n"
        "• /vk_admin_nudge_reset <nudge>\n"
        "• /vk_admin_crm_get <request_id>\n"
        "• /vk_admin_crm_set <request_id> <status>   (только mock)\n"
        "• /vk_admin_crm_events [limit]             (только mock)\n"
    )


def _fmt_dt(v) -> str:
    return "-" if not v else v.isoformat(sep=" ", timespec="seconds")


def _fmt_dir(v) -> str:
    return getattr(v, "value", str(v)) if v is not None else "-"


async def try_handle_vk_admin_command(
    *, text: str, peer_id: int, session: AsyncSession
) -> Optional[dict]:
    cmd, args = _parse_cmd(text)
    if not cmd.startswith("/vk_admin"):
        return None

    if not _is_admin(peer_id):
        return _deny()

    now = datetime.utcnow()

    if cmd in ("/vk_admin_help", "/vk_admin"):
        return {"text": _help_text(), "keyboard": None}

    if cmd == "/vk_admin_peer":
        return {"text": f"peer_id={int(peer_id)}", "keyboard": None}

    if cmd == "/vk_admin_last_requests":
        limit = 10
        if args:
            try:
                limit = max(1, min(50, int(args[0])))
            except Exception:
                limit = 10

        rows = (
            await session.execute(
                select(Request)
                .where(Request.transport == "vk")
                .order_by(desc(Request.id))
                .limit(limit)
            )
        ).scalars().all()

        if not rows:
            return {"text": "Заявок (vk) пока нет.", "keyboard": None}

        lines = [f"Последние заявки (vk), limit={limit}:"]
        for r in rows:
            lines.append(
                f"• #{r.id} | peer={r.peer_id} | dir={_fmt_dir(r.direction)} | give={r.give_amount} | "
                f"office={r.office_id} | date={r.desired_date} | crm={r.crm_request_id or '-'}"
            )
        return {"text": "\n".join(lines), "keyboard": None}

    if cmd == "/vk_admin_request":
        if not args:
            return {"text": "Использование: /vk_admin_request <request_id>", "keyboard": None}
        try:
            req_id = int(args[0])
        except Exception:
            return {"text": "request_id должен быть числом.", "keyboard": None}

        req = await session.get(Request, req_id)
        if not req or req.transport != "vk":
            return {"text": "Заявка не найдена (vk).", "keyboard": None}

        text_out = (
            f"Заявка #{req.id}\n"
            f"peer_id: {req.peer_id}\n"
            f"client_request_id: {req.client_request_id}\n"
            f"crm_request_id: {req.crm_request_id or '-'}\n"
            f"status: {req.status}\n"
            f"direction: {_fmt_dir(req.direction)}\n"
            f"give_amount: {req.give_amount}\n"
            f"office_id: {req.office_id}\n"
            f"desired_date: {req.desired_date}\n"
            f"rate: {req.rate}\n"
            f"receive_amount: {req.receive_amount}\n"
            f"username: {req.username}\n\n"
            f"n1: planned={_fmt_dt(req.nudge1_planned_at)} sent={_fmt_dt(req.nudge1_sent_at)} answer={req.nudge1_answer or '-'}\n"
            f"n5: planned={_fmt_dt(req.nudge5_planned_at)} sent={_fmt_dt(req.nudge5_sent_at)} answer={req.nudge5_answer or '-'} answered={_fmt_dt(req.nudge5_answered_at)}\n"
            f"n6: planned={_fmt_dt(req.nudge6_planned_at)} sent={_fmt_dt(req.nudge6_sent_at)} answer={req.nudge6_answer or '-'} answered={_fmt_dt(req.nudge6_answered_at)}\n"
            f"n7: planned={_fmt_dt(req.nudge7_planned_at)} sent={_fmt_dt(req.nudge7_sent_at)} answer={req.nudge7_answer or '-'} answered={_fmt_dt(req.nudge7_answered_at)}\n"
        )
        return {"text": text_out, "keyboard": None}

    if cmd == "/vk_admin_last_drafts":
        limit = 10
        if args:
            try:
                limit = max(1, min(50, int(args[0])))
            except Exception:
                limit = 10

        rows = (
            await session.execute(
                select(Draft)
                .where(Draft.transport == "vk")
                .order_by(desc(Draft.id))
                .limit(limit)
            )
        ).scalars().all()

        if not rows:
            return {"text": "Черновиков (vk) пока нет.", "keyboard": None}

        lines = [f"Последние черновики (vk), limit={limit}:"]
        for d in rows:
            lines.append(
                f"• draft#{d.id} | peer={d.peer_id} | step={d.last_step} | dir={_fmt_dir(d.direction)} | "
                f"give={d.give_amount or '-'} | office={d.office_id or '-'} | date={d.desired_date or '-'} | "
                f"client_req={d.client_request_id or '-'}"
            )
        return {"text": "\n".join(lines), "keyboard": None}

    if cmd == "/vk_admin_draft":
        if not args:
            return {"text": "Использование: /vk_admin_draft <draft_id>", "keyboard": None}
        try:
            draft_id = int(args[0])
        except Exception:
            return {"text": "draft_id должен быть числом.", "keyboard": None}

        d = await session.get(Draft, draft_id)
        if not d or d.transport != "vk":
            return {"text": "Черновик не найден (vk).", "keyboard": None}

        text_out = (
            f"Draft #{d.id}\n"
            f"peer_id: {d.peer_id}\n"
            f"last_step: {d.last_step}\n"
            f"client_request_id: {d.client_request_id or '-'}\n"
            f"direction: {_fmt_dir(d.direction)}\n"
            f"give_amount: {d.give_amount or '-'}\n"
            f"office_id: {d.office_id or '-'}\n"
            f"desired_date: {d.desired_date or '-'}\n"
            f"username: {d.username or '-'}\n\n"
            f"n2: planned={_fmt_dt(d.nudge2_planned_at)} sent={_fmt_dt(d.nudge2_sent_at)} answer={d.nudge2_answer or '-'} answered={_fmt_dt(d.nudge2_answered_at)}\n"
            f"n3: planned={_fmt_dt(d.nudge3_planned_at)} sent={_fmt_dt(d.nudge3_sent_at)} answer={d.nudge3_answer or '-'}\n"
            f"n4: planned={_fmt_dt(d.nudge4_planned_at)} sent={_fmt_dt(d.nudge4_sent_at)} answer={d.nudge4_answer or '-'}\n"
        )
        return {"text": text_out, "keyboard": None}

    if cmd == "/vk_admin_reset_peer":
        d = (
            await session.execute(
                select(Draft).where(Draft.transport == "vk", Draft.peer_id == int(peer_id)).limit(1)
            )
        ).scalar_one_or_none()

        if not d:
            return {"text": "Draft (vk) для этого peer_id не найден.", "keyboard": None}

        d.direction = None
        d.give_amount = None
        d.office_id = None
        d.desired_date = None
        d.username = None
        d.client_request_id = None
        d.last_step = "start"
        d.updated_at = now

        d.nudge2_planned_at = None
        d.nudge2_sent_at = None
        d.nudge2_answer = None
        d.nudge2_answered_at = None

        d.step6_at = None
        d.nudge3_planned_at = None
        d.nudge3_sent_at = None
        d.nudge3_answer = None

        d.nudge4_planned_at = None
        d.nudge4_sent_at = None
        d.nudge4_answer = None

        await session.commit()
        return {"text": "Ок. Draft сброшен. Можно тестировать сценарий заново.", "keyboard": None}

    if cmd == "/vk_admin_nudge_plan":
        if not args:
            return {"text": "Использование: /vk_admin_nudge_plan <nudge> [seconds]", "keyboard": None}

        nudge = args[0].strip().lower().lstrip("n")
        sec = 10
        if len(args) > 1:
            try:
                sec = max(1, min(3600, int(args[1])))
            except Exception:
                sec = 10

        when = now + timedelta(seconds=sec)

        if nudge in ("1",):
            req = (
                await session.execute(
                    select(Request)
                    .where(Request.transport == "vk", Request.peer_id == int(peer_id))
                    .order_by(desc(Request.id))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not req:
                return {"text": "Нет request (vk) для этого peer_id.", "keyboard": None}

            req.nudge1_planned_at = when
            req.nudge1_sent_at = None
            req.nudge1_answer = None
            await session.commit()
            return {"text": f"Ок. Запланирован nudge1 через {sec}s для request#{req.id}", "keyboard": None}

        if nudge in ("2", "3", "4"):
            d = (
                await session.execute(
                    select(Draft).where(Draft.transport == "vk", Draft.peer_id == int(peer_id)).limit(1)
                )
            ).scalar_one_or_none()
            if not d:
                return {"text": "Нет draft (vk) для этого peer_id.", "keyboard": None}

            if nudge == "2":
                d.nudge2_planned_at = when
                d.nudge2_sent_at = None
                d.nudge2_answer = None
                d.nudge2_answered_at = None
            elif nudge == "3":
                d.nudge3_planned_at = when
                d.nudge3_sent_at = None
                d.nudge3_answer = None
            else:
                d.nudge4_planned_at = when
                d.nudge4_sent_at = None
                d.nudge4_answer = None

            await session.commit()
            return {"text": f"Ок. Запланирован nudge{nudge} через {sec}s для draft#{d.id}", "keyboard": None}

        if nudge in ("5", "6", "7"):
            req = (
                await session.execute(
                    select(Request)
                    .where(Request.transport == "vk", Request.peer_id == int(peer_id))
                    .order_by(desc(Request.id))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not req:
                return {"text": "Нет request (vk) для этого peer_id.", "keyboard": None}

            if nudge == "5":
                req.nudge5_planned_at = when
                req.nudge5_sent_at = None
                req.nudge5_answer = None
                req.nudge5_answered_at = None
            elif nudge == "6":
                req.nudge6_planned_at = when
                req.nudge6_sent_at = None
                req.nudge6_answer = None
                req.nudge6_answered_at = None
            else:
                req.nudge7_planned_at = when
                req.nudge7_sent_at = None
                req.nudge7_answer = None
                req.nudge7_answered_at = None

            await session.commit()
            return {"text": f"Ок. Запланирован nudge{nudge} через {sec}s для request#{req.id}", "keyboard": None}

        return {"text": "nudge должен быть 1..7", "keyboard": None}

    if cmd == "/vk_admin_nudge_reset":
        if not args:
            return {"text": "Использование: /vk_admin_nudge_reset <nudge>", "keyboard": None}
        nudge = args[0].strip().lower().lstrip("n")

        if nudge == "1":
            req = (
                await session.execute(
                    select(Request)
                    .where(Request.transport == "vk", Request.peer_id == int(peer_id))
                    .order_by(desc(Request.id))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not req:
                return {"text": "Нет request (vk) для этого peer_id.", "keyboard": None}
            req.nudge1_planned_at = None
            req.nudge1_sent_at = None
            req.nudge1_answer = None
            await session.commit()
            return {"text": "Ок. nudge1 сброшен.", "keyboard": None}

        if nudge in ("2", "3", "4"):
            d = (
                await session.execute(
                    select(Draft).where(Draft.transport == "vk", Draft.peer_id == int(peer_id)).limit(1)
                )
            ).scalar_one_or_none()
            if not d:
                return {"text": "Нет draft (vk) для этого peer_id.", "keyboard": None}

            if nudge == "2":
                d.nudge2_planned_at = None
                d.nudge2_sent_at = None
                d.nudge2_answer = None
                d.nudge2_answered_at = None
            elif nudge == "3":
                d.nudge3_planned_at = None
                d.nudge3_sent_at = None
                d.nudge3_answer = None
            else:
                d.nudge4_planned_at = None
                d.nudge4_sent_at = None
                d.nudge4_answer = None

            await session.commit()
            return {"text": f"Ок. nudge{nudge} сброшен.", "keyboard": None}

        if nudge in ("5", "6", "7"):
            req = (
                await session.execute(
                    select(Request)
                    .where(Request.transport == "vk", Request.peer_id == int(peer_id))
                    .order_by(desc(Request.id))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not req:
                return {"text": "Нет request (vk) для этого peer_id.", "keyboard": None}

            if nudge == "5":
                req.nudge5_planned_at = None
                req.nudge5_sent_at = None
                req.nudge5_answer = None
                req.nudge5_answered_at = None
            elif nudge == "6":
                req.nudge6_planned_at = None
                req.nudge6_sent_at = None
                req.nudge6_answer = None
                req.nudge6_answered_at = None
            else:
                req.nudge7_planned_at = None
                req.nudge7_sent_at = None
                req.nudge7_answer = None
                req.nudge7_answered_at = None

            await session.commit()
            return {"text": f"Ок. nudge{nudge} сброшен.", "keyboard": None}

        return {"text": "nudge должен быть 1..7", "keyboard": None}

    if cmd == "/vk_admin_crm_get":
        if not args:
            return {"text": "Использование: /vk_admin_crm_get <request_id>", "keyboard": None}
        try:
            req_id = int(args[0])
        except Exception:
            return {"text": "request_id должен быть числом.", "keyboard": None}

        req = await session.get(Request, req_id)
        if not req or req.transport != "vk" or not req.crm_request_id:
            return {"text": "Заявка не найдена (vk) или у неё нет crm_request_id.", "keyboard": None}

        crm = get_crm_client()
        st = await crm.check_status(str(req.crm_request_id))
        status = str((st or {}).get("status") or "")
        return {"text": f"CRM status для заявки #{req.id}: {status or '-'}", "keyboard": None}

    if cmd == "/vk_admin_crm_set":
        if (settings.crm_mode or "mock").strip().lower() != "mock":
            return {"text": "Команда доступна только в crm_mode=mock.", "keyboard": None}
        if len(args) < 2:
            return {"text": "Использование: /vk_admin_crm_set <request_id> <status>", "keyboard": None}

        try:
            req_id = int(args[0])
        except Exception:
            return {"text": "request_id должен быть числом.", "keyboard": None}

        status = " ".join(args[1:]).strip()
        if not status:
            return {"text": "status не может быть пустым.", "keyboard": None}

        req = await session.get(Request, req_id)
        if not req or req.transport != "vk" or not req.crm_request_id:
            return {"text": "Заявка не найдена (vk) или у неё нет crm_request_id.", "keyboard": None}

        crm = get_crm_client()
        if not hasattr(crm, "mock_set_status"):
            return {"text": "Текущий CRM клиент не поддерживает mock_set_status.", "keyboard": None}

        await crm.mock_set_status(str(req.crm_request_id), status)
        return {"text": f"Установлен CRM status для заявки #{req.id}: {status}", "keyboard": None}

    if cmd == "/vk_admin_crm_events":
        if (settings.crm_mode or "mock").strip().lower() != "mock":
            return {"text": "Команда доступна только в crm_mode=mock.", "keyboard": None}

        limit = 20
        if args:
            try:
                limit = max(1, min(100, int(args[0])))
            except Exception:
                limit = 20

        crm = get_crm_client()
        if not hasattr(crm, "mock_get_events"):
            return {"text": "Текущий CRM клиент не поддерживает mock_get_events.", "keyboard": None}

        events = await crm.mock_get_events(limit=limit)
        if not events:
            return {"text": "Событий пока нет.", "keyboard": None}

        lines = [f"Последние события (mock CRM), limit={limit}:"]
        for e in events[-min(10, len(events)) :]:
            payload = e.get("payload") or {}
            lines.append(
                f"• {payload.get('type') or payload.get('nudge_type') or '-'} | "
                f"{payload.get('action') or payload.get('answer') or '-'}"
            )
        return {"text": "\n".join(lines), "keyboard": None}

    return {"text": "Неизвестная команда. /vk_admin_help", "keyboard": None}