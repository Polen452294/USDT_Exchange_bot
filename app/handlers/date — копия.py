from datetime import date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, User
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards import kb_next
from app.models import Draft
from app.states import ExchangeFlow
from app.utils import parse_date_ddmmyyyy

router = Router()


@router.message(ExchangeFlow.entering_date)
async def enter_date_manual(message: Message, state: FSMContext, session: AsyncSession):
    try:
        d = parse_date_ddmmyyyy(message.text)
    except Exception:
        today_example = date.today().strftime("%d.%m.%Y")
        await message.answer(
            "Некорректная дата.\n"
            "Введите в формате: дд.мм.гггг\n"
            f"Пример: {today_example}"
        )
        return

    if d < date.today():
        await message.answer("Дата не может быть в прошлом. Введите другую дату.")
        return

    tg_id = message.from_user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        draft = Draft(telegram_user_id=tg_id, last_step="start")
        session.add(draft)

    draft.desired_date = d
    draft.last_step = "date"
    await session.commit()

    await go_username_step(message=message, user=message.from_user, state=state, session=session)


@router.callback_query(ExchangeFlow.entering_date, F.data == "next")
async def enter_date_default(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    tg_id = cb.from_user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        draft = Draft(telegram_user_id=tg_id, last_step="start")
        session.add(draft)

    draft.desired_date = date.today()
    draft.last_step = "date_default"
    await session.commit()

    await go_username_step(message=cb.message, user=cb.from_user, state=state, session=session)


async def go_username_step(message: Message, user: User, state: FSMContext, session: AsyncSession):
    tg_id = user.id
    draft = await session.scalar(select(Draft).where(Draft.telegram_user_id == tg_id))
    if draft is None:
        draft = Draft(telegram_user_id=tg_id, last_step="start")
        session.add(draft)
        await session.commit()

    username = (user.username or "").strip()
    if username:
        draft.username = username
        draft.last_step = "username_auto"
        await session.commit()

        await message.answer("Ок, контакт в Telegram найден. Готовлю сводку…")
        await state.set_state(ExchangeFlow.confirming)

        from app.handlers.summary import send_summary
        await send_summary(message, state, session, user_id=tg_id)
        return

    await message.answer(
        "Похоже, у вас в Telegram не указан username – а он нужен, чтобы продолжить наше общение. "
        "Введите, пожалуйста, ваш username"
    )
    await state.set_state(ExchangeFlow.entering_username)