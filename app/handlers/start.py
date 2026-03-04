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

START_TEXT = (
    "Привет!\n"
    "Я помогу быстро оформить заявку на обмен за несколько шагов:\n"
    "➔ выберите направление обмена\n"
    "➔ укажите сумму, которую отдаете\n"
    "➔ выберите офис в Анталье или Стамбуле\n"
    "➔ выберите желаемую дату сделки\n"
    "Потом я покажу вам условия обмена и, если вы согласны, попрошу подтвердить их.\n"
    "После наш менеджер свяжется с вами в Telegram для обсуждения деталей. "
    "Если нужно быстро задать вопрос — пишите менеджеру напрямую @coinpointlara.\n\n"
    "Нажмите кнопку ниже, чтобы начать 👇"
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

    give_cur = direction_from_currency(direction) or "сумму"
    await edit_or_send(
        cb.message,
        f"Введите, пожалуйста, сумму, которую вы отдаёте ({give_cur}).",
        reply_markup=None,
    )
    await state.set_state(ExchangeFlow.entering_amount)