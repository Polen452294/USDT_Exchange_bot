from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards import kb_dates_7
from app.repositories.drafts import DraftRepository
from app.states import ExchangeFlow
from app.utils.messages import edit_or_send

router = Router()

SEP = "━━━━━━━━━━━━━━"


@router.callback_query(ExchangeFlow.choosing_office, F.data.startswith("office:"))
async def choose_office(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    current_state = await state.get_state()
    if current_state != ExchangeFlow.choosing_office.state:
        await cb.answer("Заявка уже изменена. Начните новую.", show_alert=True)
        return

    office_id = cb.data.split(":", 1)[1]
    tg_id = cb.from_user.id

    drafts = DraftRepository(session)
    draft = await drafts.get_or_create(transport="tg", peer_id=tg_id, telegram_user_id=tg_id)

    draft.office_id = office_id
    draft.last_step = "office"
    draft.updated_at = datetime.utcnow()
    await drafts.save()

    text = (
        "📅 Выберите дату сделки (из ближайших 7 дней)\n\n"
    )
    await edit_or_send(cb.message, text, reply_markup=kb_dates_7())
    await state.set_state(ExchangeFlow.entering_date)