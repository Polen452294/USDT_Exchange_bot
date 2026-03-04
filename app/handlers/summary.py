from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.requests import RequestService
from app.config import settings
from app.states import ExchangeFlow
from app.keyboards import kb_confirm, kb_start
from app.repositories.drafts import DraftRepository
from app.repositories.requests import RequestRepository
from app.services.requests import RequestService
from app.infrastructure.crm_client import CRMTemporaryError, CRMPermanentError
from app.utils.messages import edit_or_send

router = Router()
log = logging.getLogger("summary")


async def send_summary(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    *,
    user_id: int,
    edit_message: Message | None = None,
) -> None:
    draft_repo = DraftRepository(session)
    request_repo = RequestRepository(session)
    service = RequestService(draft_repo, request_repo)

    try:
        summary = await service.build_summary_ctx("tg", user_id)
    except ValueError as e:
        log.warning("send_summary rejected: user_id=%s err=%s", user_id, str(e))
        if edit_message is not None:
            await edit_or_send(edit_message, "Не получилось собрать сводку. Начните заново через /start.", None)
        else:
            await message.answer("Не получилось собрать сводку. Начните заново через /start.")
        await state.clear()
        return
    except CRMTemporaryError:
        text = (
            "Сейчас не могу получить курс (временная ошибка). "
            "Пожалуйста, попробуйте ещё раз через минуту."
        )
        if edit_message is not None:
            await edit_or_send(edit_message, text, None)
        else:
            await message.answer(text)
        return
    except CRMPermanentError:
        text = (
            "Сейчас не могу получить курс. "
            "Пожалуйста, напишите менеджеру @coinpointlara — он поможет вручную."
        )
        if edit_message is not None:
            await edit_or_send(edit_message, text, None)
        else:
            await message.answer(text)
        return
    except Exception:
        log.exception("send_summary failed: user_id=%s", user_id)
        text = "Не удалось сформировать сводку. Попробуйте снова."
        if edit_message is not None:
            await edit_or_send(edit_message, text, None)
        else:
            await message.answer(text)
        return

    if edit_message is not None:
        await edit_or_send(edit_message, summary.summary_text, kb_confirm())
    else:
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
        await edit_or_send(
            cb.message,
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
        result = await service.confirm_request_ctx("tg", cb.from_user.id)

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
        await edit_or_send(
            cb.message,
            "Заявка уже создана ✅ Менеджер свяжется с вами, как только возьмёт её в работу.",
            reply_markup=None,
        )
        return

    await edit_or_send(
        cb.message,
        "Готово ✅ Заявка создана. Менеджер свяжется с вами в Telegram, как только возьмёт её в работу.",
        reply_markup=None,
    )