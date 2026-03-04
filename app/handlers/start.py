from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.utils.messages import edit_or_send
from app.config import settings
from app.models import Direction, direction_from_currency
from app.keyboards import kb_start
from app.repositories.drafts import DraftRepository
from app.states import ExchangeFlow

router = Router()

SEP = "━━━━━━━━━━━━━━"

START_TEXT = (
    "👋 Привет! Я помогу оформить заявку на обмен.\n\n"
    "🧭 Выберите направление обмена ниже.\n\n"
    f"{SEP}\n"
    "ℹ️ После подтверждения менеджер свяжется с вами в Telegram.\n"
    "Если нужно быстро задать вопрос — пишите @coinpointlara."
)


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()

    tg_id = message.from_user.id
    drafts = DraftRepository(session)
    draft = await drafts.get_or_create(transport="tg", peer_id=tg_id, telegram_user_id=tg_id)

    draft.direction = None
    draft.give_amount = None
    draft.office_id = None
    draft.desired_date = None
    draft.username = None
    draft.client_request_id = None

    draft.nudge2_planned_at = None
    draft.nudge2_sent_at = None
    draft.nudge2_answer = None
    draft.nudge2_answered_at = None

    draft.step6_at = None
    draft.nudge3_planned_at = None
    draft.nudge3_sent_at = None
    draft.nudge3_answer = None

    draft.nudge4_planned_at = None
    draft.nudge4_sent_at = None
    draft.nudge4_answer = None

    draft.last_step = "start"
    draft.updated_at = datetime.utcnow()
    await drafts.save()

    await message.answer(START_TEXT, reply_markup=kb_start())
    await state.set_state(ExchangeFlow.choosing_direction)


@router.callback_query(F.data.startswith("dir:"))
async def choose_dir(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    direction_value = cb.data.split(":", 1)[1]
    direction = Direction(direction_value)

    tg_id = cb.from_user.id
    drafts = DraftRepository(session)
    draft = await drafts.get_or_create(transport="tg", peer_id=tg_id, telegram_user_id=tg_id)

    draft.direction = direction
    draft.last_step = "amount_wait"
    draft.updated_at = datetime.utcnow()

    delay = int(getattr(settings, "nudge2_delay_seconds", 900))
    draft.nudge2_planned_at = datetime.utcnow() + timedelta(seconds=delay)
    draft.nudge2_sent_at = None
    draft.nudge2_answer = None
    draft.nudge2_answered_at = None

    await drafts.save()

    give_cur = direction_from_currency(direction) or "—"
    text = (
        "💰 Укажите сумму, которую вы отдаёте\n\n"
        f"✍️ Отправьте число сообщением\n"
        f"Валюта: {give_cur}"
    )
    await edit_or_send(cb.message, text, reply_markup=None)
    await state.set_state(ExchangeFlow.entering_amount)