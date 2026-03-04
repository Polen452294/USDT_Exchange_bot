from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.drafts import DraftRepository
from app.states import ExchangeFlow
from app.utils import normalize_username

router = Router()

SEP = "━━━━━━━━━━━━━━"


@router.message(ExchangeFlow.entering_username)
async def enter_username(message: Message, state: FSMContext, session: AsyncSession):
    try:
        username = normalize_username(message.text)
    except Exception:
        await message.answer(
            "⚠️ Некорректный username.\n\n"
            "✍️ Введите латиницей/цифры/_, без пробелов.\n"
            "Пример: @yourname"
        )
        return

    tg_id = message.from_user.id
    drafts = DraftRepository(session)
    draft = await drafts.get_or_create(transport="tg", peer_id=tg_id, telegram_user_id=tg_id)

    draft.username = username
    draft.last_step = "username_manual"
    await drafts.save()

    await message.answer(
        "✅ Принято!\n\n"
        f"{SEP}\n"
        "🧾 Готовлю сводку заявки…"
    )
    await state.set_state(ExchangeFlow.confirming)

    from app.handlers.summary import send_summary
    await send_summary(message, state, session, user_id=tg_id)