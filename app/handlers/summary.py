from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.states import ExchangeFlow
from app.keyboards import kb_confirm, kb_start
from app.repositories.drafts import DraftRepository
from app.repositories.requests import RequestRepository
from app.services.requests import RequestService
from app.infrastructure.crm_client import CRMTemporaryError, CRMPermanentError

router = Router()
log = logging.getLogger("summary")


async def send_summary(message: Message, state: FSMContext, session: AsyncSession, *, user_id: int) -> None:
    draft_repo = DraftRepository(session)
    request_repo = RequestRepository(session)
    service = RequestService(draft_repo, request_repo)

    try:
        summary = await service.build_summary(user_id)
    except ValueError as e:
        log.warning("send_summary rejected: user_id=%s err=%s", user_id, str(e))
        await message.answer("Не получилось собрать сводку. Начните заново через /start.")
        await state.clear()
        return
    except CRMTemporaryError:
        await message.answer(
            "Сейчас не могу получить курс (временная ошибка). "
            "Пожалуйста, попробуйте ещё раз через минуту."
        )
        return
    except CRMPermanentError:
        await message.answer(
            "Сейчас не могу получить курс. "
            "Пожалуйста, напишите менеджеру @coinpointlara — он поможет вручную."
        )
        return
    except Exception:
        log.exception("send_summary failed: user_id=%s", user_id)
        await message.answer("Не удалось сформировать сводку. Попробуйте снова.")
        return

    await message.answer(summary.summary_text, reply_markup=kb_confirm())
    await state.set_state(ExchangeFlow.confirming)

    try:
        draft = await draft_repo.get_by_user_id(user_id)
        if draft:
            now = datetime.utcnow()
            draft.step6_at = now

            if draft.nudge3_sent_at is None and draft.nudge3_answer is None:
                delay = int(getattr(settings, "nudge3_delay_seconds", 6000))
                draft.nudge3_planned_at = now + timedelta(seconds=delay)

            await draft_repo.save()
    except Exception:
        log.exception("send_summary post-save failed: user_id=%s", user_id)


@router.callback_query(F.data == "confirm:no")
async def confirm_no(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    try:
        draft_repo = DraftRepository(session)
        draft = await draft_repo.get_by_user_id(cb.from_user.id)

        if draft:
            draft.direction = None
            draft.give_amount = None
            draft.office_id = None
            draft.desired_date = None
            draft.username = None
            draft.client_request_id = None
            draft.last_step = "start"

            draft.step6_at = None
            draft.nudge3_planned_at = None
            draft.nudge3_sent_at = None
            draft.nudge3_answer = None

            await draft_repo.save()

        await state.clear()
        await cb.message.answer(
            "Хорошо, давайте поправим. Выберите направление перевода",
            reply_markup=kb_start(),
        )
        await state.set_state(ExchangeFlow.choosing_direction)

    except Exception:
        log.exception("confirm_no failed: user_id=%s", cb.from_user.id)
        await cb.message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()


@router.callback_query(F.data == "confirm:yes")
async def confirm_yes(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

    draft_repo = DraftRepository(session)
    request_repo = RequestRepository(session)
    service = RequestService(draft_repo, request_repo)

    try:
        result = await service.confirm_request(cb.from_user.id)

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

    except ValueError as e:
        # это полезно видеть отдельно (часто draft_not_ready / draft_not_found)
        log.warning("confirm_yes rejected: user_id=%s err=%s", cb.from_user.id, str(e))
        await cb.message.answer("Не получилось подтвердить заявку. Попробуйте пройти шаги заново через /start.")
        await state.clear()
        return

    except Exception:
        log.exception("confirm_yes failed: user_id=%s", cb.from_user.id)
        await cb.message.answer("Произошла ошибка. Попробуйте снова.")
        return

    await state.clear()

    if result.already_exists:
        await cb.message.answer(
            "Заявка уже создана ✅ Менеджер свяжется с вами, как только возьмёт её в работу."
        )
        return

    await cb.message.answer(
        "Готово ✅ Заявка создана. Менеджер свяжется с вами в Telegram, как только возьмёт её в работу."
    )