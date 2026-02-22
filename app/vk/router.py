from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Iterable, Tuple

from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import build_services
from app.db import AsyncSessionLocal
from app.models import Direction, Draft
from app.vk.keyboards import (
    main_menu_keyboard,
    direction_keyboard,
    next_keyboard,
    offices_keyboard,
    confirm_keyboard,
)


@dataclass(frozen=True)
class VkReply:
    text: str
    keyboard: str | None = None


def _today_str() -> str:
    return datetime.utcnow().date().strftime("%d.%m.%Y")


def _parse_amount(text: str) -> float | None:
    t = (text or "").strip().replace(",", ".")
    try:
        v = float(t)
    except Exception:
        return None
    if v <= 0:
        return None
    return v


def _parse_date_ddmmyyyy(text: str) -> date | None:
    t = (text or "").strip()
    try:
        day = datetime.strptime(t, "%d.%m.%Y").date()
    except Exception:
        return None
    if day < datetime.utcnow().date():
        return None
    return day


def _normalize_username(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    if " " in t:
        return None
    if t.startswith("@"):
        t = t[1:]
    if not t:
        return None
    return t


async def _get_draft(session: AsyncSession, transport: str, peer_id: int) -> Draft | None:
    return await session.scalar(
        select(Draft).where(Draft.transport == transport, Draft.peer_id == peer_id)
    )


async def _reset_draft(session: AsyncSession, transport: str, peer_id: int) -> None:
    await session.execute(
        update(Draft)
        .where(Draft.transport == transport, Draft.peer_id == peer_id)
        .values(
            direction=None,
            give_amount=None,
            office_id=None,
            desired_date=None,
            username=None,
            client_request_id=None,
            last_step="start",
            updated_at=datetime.utcnow(),
        )
    )


def _default_offices() -> list[Tuple[str, str]]:
    return [
        ("antalya_1", "Анталья 1 (адрес)"),
        ("antalya_2", "Анталья 2 (адрес)"),
        ("istanbul", "Стамбул"),
    ]


class VKRouter:
    async def handle(self, peer_id: int, user_id: int, text: str):
        t_raw = (text or "").strip()
        t = t_raw.lower()

        async with AsyncSessionLocal() as session:
            draft_service, request_service = build_services(session)

            if t in ("/start", "start", "меню", "начать", "старт"):
                return VkReply(
                    text=(
                        "Привет!\n"
                        "Я помогу быстро оформить заявку на обмен USDT ↔ наличные в Турции за несколько шагов:\n"
                        "➔ выберите направление обмена\n"
                        "➔ укажите сумму, которую отдаете\n"
                        "➔ выберите офис в Анталье или Стамбуле\n"
                        "➔ выберите желаемую дату сделки\n"
                        "Потом я покажу вам условия обмена и, если вы согласны, попрошу подтвердить их.\n"
                        "После наш менеджер свяжется с вами в Telegram для обсуждения деталей. Если "
                        "нужно быстро задать вопрос — пишите менеджеру напрямую @coinpointlara.\n"
                        "Нажмите кнопку ниже, чтобы начать 👇"
                    ),
                    keyboard=direction_keyboard(),
                )

            if t_raw == "Информация":
                return VkReply(
                    text=(
                        "Я помогу оформить заявку на обмен USDT ↔ наличные.\n"
                        "Если нужно быстро задать вопрос — пишите менеджеру @coinpointlara.\n\n"
                        "Нажмите «Создать заявку», чтобы начать."
                    ),
                    keyboard=main_menu_keyboard(),
                )

            if t_raw == "Создать заявку":
                return VkReply(
                    text=(
                        "Привет!\n"
                        "Я помогу быстро оформить заявку на обмен USDT ↔ наличные в Турции за несколько шагов:\n"
                        "➔ выберите направление обмена\n"
                        "➔ укажите сумму, которую отдаете\n"
                        "➔ выберите офис в Анталье или Стамбуле\n"
                        "➔ выберите желаемую дату сделки\n"
                        "Потом я покажу вам условия обмена и, если вы согласны, попрошу подтвердить их.\n"
                        "После наш менеджер свяжется с вами в Telegram для обсуждения деталей. Если "
                        "нужно быстро задать вопрос — пишите менеджеру напрямую @coinpointlara.\n"
                        "Нажмите кнопку ниже, чтобы начать 👇"
                    ),
                    keyboard=direction_keyboard(),
                )

            if t_raw == "USDT в наличные":
                await draft_service.set_direction("vk", peer_id, Direction.USDT_TO_CASH)
                return VkReply(
                    text="Введите, пожалуйста, сумму, которую вы отдаёте.",
                    keyboard=next_keyboard(),
                )

            if t_raw == "Наличные в USDT":
                await draft_service.set_direction("vk", peer_id, Direction.CASH_TO_USDT)
                return VkReply(
                    text="Введите, пожалуйста, сумму, которую вы отдаёте.",
                    keyboard=next_keyboard(),
                )

            draft = await _get_draft(session, "vk", peer_id)

            if t_raw == "Далее" and (draft is None or draft.last_step in ("start", "direction")):
                return VkReply(
                    text="Введите, пожалуйста, сумму, которую вы отдаёте.",
                    keyboard=next_keyboard(),
                )

            amount = _parse_amount(t_raw)
            if amount is not None:
                await draft_service.set_amount("vk", peer_id, float(amount))
                offices = _default_offices()
                return VkReply(
                    text="Выберите, пожалуйста, где вам удобнее провести обмен",
                    keyboard=offices_keyboard(offices),
                )

            offices = _default_offices()
            office_label_to_id = {label: oid for oid, label in offices}

            if t_raw in office_label_to_id:
                await draft_service.set_office("vk", peer_id, office_label_to_id[t_raw])
                return VkReply(
                    text=(
                        "Когда вам удобно получить наличные? По умолчанию стоит сегодняшняя дата — "
                        f"{_today_str()} — можете оставить её и нажать «Далее». Или нажмите на поле и "
                        "введите желаемую дату"
                    ),
                    keyboard=next_keyboard(),
                )

            if t_raw == "Далее" and draft is not None and draft.office_id and not draft.desired_date:
                await draft_service.set_date("vk", peer_id, datetime.utcnow().date())
                return VkReply(
                    text=(
                        "Похоже, у вас в Telegram не указан username – а он нужен, чтобы продолжить наше "
                        "общение. Введите, пожалуйста, ваш username"
                    ),
                    keyboard=next_keyboard(),
                )

            parsed_day = _parse_date_ddmmyyyy(t_raw)
            if parsed_day is not None:
                await draft_service.set_date("vk", peer_id, parsed_day)
                return VkReply(
                    text=(
                        "Похоже, у вас в Telegram не указан username – а он нужен, чтобы продолжить наше "
                        "общение. Введите, пожалуйста, ваш username"
                    ),
                    keyboard=next_keyboard(),
                )

            if t_raw == "Далее" and draft is not None and draft.desired_date and not draft.username:
                return VkReply(
                    text=(
                        "Похоже, у вас в Telegram не указан username – а он нужен, чтобы продолжить наше "
                        "общение. Введите, пожалуйста, ваш username"
                    ),
                    keyboard=next_keyboard(),
                )

            username = _normalize_username(t_raw)
            if username is not None:
                await draft_service.set_username("vk", peer_id, username)

                summary = await request_service.build_summary_ctx("vk", peer_id)
                return VkReply(text=summary.summary_text, keyboard=confirm_keyboard())

            if t_raw == "Да, все отлично":
                res = await request_service.confirm_request_ctx("vk", peer_id)
                if res.already_exists:
                    return VkReply(
                        text="Готово ✅ Заявка уже была создана. Менеджер свяжется с вами в Telegram, как только возьмёт её в работу.",
                        keyboard=main_menu_keyboard(),
                    )
                return VkReply(
                    text="Готово ✅ Заявка создана. Менеджер свяжется с вами в Telegram, как только возьмёт её в работу.",
                    keyboard=main_menu_keyboard(),
                )

            if t_raw == "Нет, хочу внести изменения":
                await _reset_draft(session, "vk", peer_id)
                await session.commit()
                return VkReply(
                    text=(
                        "Хорошо, давайте поправим. Выберите направление перевода"
                    ),
                    keyboard=direction_keyboard(),
                )

            return VkReply(
                text="Нажмите «Создать заявку», чтобы начать, или отправьте /start.",
                keyboard=main_menu_keyboard(),
            )