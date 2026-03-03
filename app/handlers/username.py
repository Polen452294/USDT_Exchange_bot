from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.drafts import DraftRepository
from app.states import ExchangeFlow
from app.utils import normalize_username

router = Router()


@router.message(ExchangeFlow.entering_username)
async def enter_username(message: Message, state: FSMContext, session: AsyncSession):
    try:
        username = normalize_username(message.text)
    except Exception:
        await message.answer("Введите корректный username (латиница/цифры/_, без пробелов), можно с @")
        return

    tg_id = message.from_user.id
    drafts = DraftRepository(session)
    draft = await drafts.get_or_create(transport="tg", peer_id=tg_id, telegram_user_id=tg_id)

    draft.username = username
    draft.last_step = "username_manual"
    await drafts.save()

    await message.answer("Спасибо! Готовлю сводку…")
    await state.set_state(ExchangeFlow.confirming)

    from app.handlers.summary import send_summary
    await send_summary(message, state, session, user_id=tg_id)