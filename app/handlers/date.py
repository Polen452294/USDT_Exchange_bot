from __future__ import annotations

from datetime import date, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, User
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.messages import edit_or_send
from app.repositories.drafts import DraftRepository
from app.states import ExchangeFlow
from app.utils import parse_date_ddmmyyyy

router = Router()

MAX_DAYS_AHEAD = 7
SEP = "━━━━━━━━━━━━━━"


def _validate_date_window(d: date) -> None:
    today = date.today()
    if d < today:
        raise ValueError("past")
    if d > today + timedelta(days=MAX_DAYS_AHEAD - 1):
        raise ValueError("too_far")


@router.callback_query(ExchangeFlow.entering_date, F.data.startswith("date:"))
async def pick_date(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    iso = cb.data.split(":", 1)[1]
    try:
        d = date.fromisoformat(iso)
        _validate_date_window(d)
    except Exception:
        today = date.today()
        max_day = today + timedelta(days=MAX_DAYS_AHEAD - 1)
        await cb.answer(
            f"Некорректная дата. Можно выбрать от сегодня до {max_day.strftime('%d.%m')}.",
            show_alert=True,
        )
        return

    tg_id = cb.from_user.id
    drafts = DraftRepository(session)
    draft = await drafts.get_or_create(transport="tg", peer_id=tg_id, telegram_user_id=tg_id)

    draft.desired_date = d
    draft.last_step = "date_pick"
    await drafts.save()

    await go_username_step(message=cb.message, user=cb.from_user, state=state, session=session)


@router.message(ExchangeFlow.entering_date)
async def enter_date_manual(message: Message, state: FSMContext, session: AsyncSession):
    try:
        d = parse_date_ddmmyyyy(message.text)
        _validate_date_window(d)
    except Exception:
        today = date.today()
        max_day = today + timedelta(days=MAX_DAYS_AHEAD - 1)
        await message.answer(
            "⚠️ Некорректная дата.\n\n"
            "✍️ Введите в формате: дд.мм.гггг\n"
            f"Можно выбрать дату от сегодня до {max_day.strftime('%d.%m')}."
        )
        return

    tg_id = message.from_user.id
    drafts = DraftRepository(session)
    draft = await drafts.get_or_create(transport="tg", peer_id=tg_id, telegram_user_id=tg_id)

    draft.desired_date = d
    draft.last_step = "date_manual"
    await drafts.save()

    await go_username_step(message=message, user=message.from_user, state=state, session=session)


async def go_username_step(message: Message, user: User, state: FSMContext, session: AsyncSession):
    tg_id = user.id
    drafts = DraftRepository(session)
    draft = await drafts.get_or_create(transport="tg", peer_id=tg_id, telegram_user_id=tg_id)

    username = (user.username or "").strip()
    if username:
        draft.username = username
        draft.last_step = "username_auto"
        await drafts.save()

        await edit_or_send(
            message,
            "👤 Контакт найден ✅\n\n"
            f"{SEP}\n"
            "🧾 Готовлю сводку заявки…",
            reply_markup=None,
        )
        await state.set_state(ExchangeFlow.confirming)

        from app.handlers.summary import send_summary
        await send_summary(message, state, session, user_id=tg_id, edit_message=message)
        return

    await message.answer(
        "👤 Укажите ваш Telegram для связи\n\n"
        "✍️ Отправьте @username (можно без @)\n"
        "Пример: @yourname"
    )
    await state.set_state(ExchangeFlow.entering_username)