from __future__ import annotations

import uuid
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.services.crm_client import get_crm_client, CRMTemporaryError, CRMPermanentError
from app.states import ExchangeFlow
from app.keyboards import kb_confirm, kb_start
from app.models import Draft, Request, Direction

router = Router()
log = logging.getLogger("crm")

DISCLAIMER = (
    "Этот курс действителен в течение 2 часов. Зафиксировать его я смогу только после "
    "получения от вас предоплаты. Для связи с менеджером используйте @coinpointlara."
)


def _money(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _new_client_request_id() -> str:
    return uuid.uuid4().hex[:16] + "-" + str(int(datetime.utcnow().timestamp()))


async def send_summary(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user_id: int | None = None,
    **_: object,
) -> None:
    tg_id = user_id if user_id is not None else message.from_user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        await message.answer("Черновик не найден. Нажмите /start чтобы начать заново.")
        return

    if not draft.direction or not draft.give_amount or not draft.office_id or not draft.desired_date:
        await message.answer("Не хватает данных для сводки. Нажмите /start чтобы начать заново.")
        return

    direction = draft.direction.value if isinstance(draft.direction, Direction) else str(draft.direction)
    if direction not in ("USDT_TO_CASH", "CASH_TO_USDT"):
        await message.answer("Некорректное направление обмена. Нажмите /start чтобы начать заново.")
        return

    if not draft.client_request_id:
        draft.client_request_id = _new_client_request_id()
        draft.updated_at = datetime.utcnow()
        await session.commit()

    crm = get_crm_client()
    try:
        rate = await crm.get_rate(str(draft.office_id), direction)
        office_label = await crm.get_office_label(str(draft.office_id))
    except (CRMTemporaryError, CRMPermanentError):
        log.exception("CRM error on summary (office_id=%s, direction=%s)", draft.office_id, direction)
        await message.answer(
            "Не получилось получить курс/офис из CRM. Попробуйте чуть позже или напишите менеджеру @coinpointlara."
        )
        return
    except Exception:
        log.exception("Unexpected CRM error on summary (office_id=%s, direction=%s)", draft.office_id, direction)
        await message.answer(
            "Не получилось получить курс/офис из CRM. Попробуйте чуть позже или напишите менеджеру @coinpointlara."
        )
        return

    receive_amount = float(draft.give_amount) * float(rate)

    if direction == "USDT_TO_CASH":
        give_currency = "USDT"
        recv_currency = "наличные"
    else:
        give_currency = "наличные"
        recv_currency = "USDT"

    summary = (
        "Почти готово. Проверьте, пожалуйста, данные заявки – покажу всё одним блоком.\n"
        f"➔ Вы отдаёте: {_money(float(draft.give_amount))} {give_currency}\n"
        f"➔ Офис: {office_label}\n"
        f"➔ Дата получения: {draft.desired_date.strftime('%d.%m.%Y')}\n"
        f"➔ Текущий курс: {rate}\n"
        f"➔ Вы получаете: {_money(receive_amount)} {recv_currency}\n\n"
        f"{DISCLAIMER}\n\n"
        "Всё верно?"
    )

    draft.last_step = "summary"
    draft.updated_at = datetime.utcnow()
    await session.commit()

    await message.answer(summary, reply_markup=kb_confirm())
    await state.update_data(_calculated_rate=rate, _calculated_receive=receive_amount, _summary_text=summary)


@router.callback_query(F.data.startswith("confirm:"))
async def confirm(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()
    action = cb.data.split(":", 1)[1]

    tg_id = cb.from_user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        await cb.message.answer("Черновик не найден. Нажмите /start чтобы начать заново.")
        return

    if action == "no":
        draft.direction = None
        draft.give_amount = None
        draft.office_id = None
        draft.desired_date = None
        draft.username = None
        draft.client_request_id = None
        draft.last_step = "start"
        draft.updated_at = datetime.utcnow()
        await session.commit()

        await state.clear()
        await cb.message.answer(
            "Хорошо, давайте поправим. Выберите направление перевода",
            reply_markup=kb_start(),
        )
        await state.set_state(ExchangeFlow.choosing_direction)
        return

    if not draft.client_request_id:
        draft.client_request_id = _new_client_request_id()
        draft.updated_at = datetime.utcnow()
        await session.commit()

    existing = await session.scalar(select(Request).where(Request.client_request_id == draft.client_request_id))
    if existing is not None:
        await state.clear()
        await cb.message.answer("Заявка уже создана ✅ Менеджер свяжется с вами, как только возьмёт её в работу.")
        return

    fsm_data = await state.get_data()
    rate = float(fsm_data.get("_calculated_rate", 0))
    receive_amount = float(fsm_data.get("_calculated_receive", 0))
    summary_text = str(fsm_data.get("_summary_text", ""))

    if not rate or not receive_amount or not summary_text:
        await send_summary(cb.message, state, session, user_id=cb.from_user.id)
        await cb.message.answer("Я обновил сводку. Подтвердите ещё раз, пожалуйста.")
        return

    req = Request(
        telegram_user_id=tg_id,
        client_request_id=draft.client_request_id,
        direction=draft.direction if isinstance(draft.direction, Direction) else Direction(str(draft.direction)),
        give_amount=float(draft.give_amount),
        office_id=str(draft.office_id),
        desired_date=draft.desired_date,
        rate=rate,
        receive_amount=receive_amount,
        username=str(draft.username),
        summary_text=summary_text,
    )
    session.add(req)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await state.clear()
        await cb.message.answer("Заявка уже создавалась ✅ Менеджер свяжется с вами, как только возьмёт её в работу.")
        return

    crm = get_crm_client()
    try:
        crm_resp = await crm.create_request(
            {
                "client_request_id": draft.client_request_id,
                "telegram_user_id": tg_id,
                "direction": req.direction.value,
                "give_amount": req.give_amount,
                "office_id": req.office_id,
                "desired_date": req.desired_date.isoformat(),
                "username": req.username,
                "rate": req.rate,
                "receive_amount": req.receive_amount,
            },
            idempotency_key=draft.client_request_id,
        )
    except CRMTemporaryError:
        await cb.message.answer(
            "Заявку в CRM сейчас создать не удалось (временная ошибка). "
            "Пожалуйста, нажмите «Да» ещё раз через минуту."
        )
        return
    except CRMPermanentError:
        await cb.message.answer(
            "Заявку в CRM сейчас создать не удалось. "
            "Пожалуйста, напишите менеджеру @coinpointlara — он поможет вручную."
        )
        return

    req.crm_request_id = crm_resp.get("crm_request_id")
    await session.commit()

    draft.last_step = "done"
    draft.updated_at = datetime.utcnow()
    await session.commit()
    await state.clear()

    await cb.message.answer(
        "Готово ✅ Заявка создана. Менеджер свяжется с вами в Telegram, как только возьмёт её в работу."
    )