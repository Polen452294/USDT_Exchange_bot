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
from app.utils.messages import edit_or_send

router = Router()
log = logging.getLogger("summary")

SEP = "━━━━━━━━━━━━━━"


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
        text = (
            "⚠️ Не получилось собрать сводку заявки.\n\n"
            "Пожалуйста, начните заново через /start."
        )
        if edit_message is not None:
            await edit_or_send(edit_message, text, None)
        else:
            await message.answer(text)
        await state.clear()
        return
    except CRMTemporaryError:
        text = (
            "⚠️ Сейчас не могу получить курс (временная ошибка).\n\n"
            "🔄 Попробуйте ещё раз через минуту."
        )
        if edit_message is not None:
            await edit_or_send(edit_message, text, None)
        else:
            await message.answer(text)
        return
    except CRMPermanentError:
        text = (
            "⚠️ Сейчас не могу получить курс.\n\n"
            "👤 Напишите менеджеру @coinpointlara — он поможет вручную."
        )
        if edit_message is not None:
            await edit_or_send(edit_message, text, None)
        else:
            await message.answer(text)
        return
    except Exception:
        log.exception("send_summary failed: user_id=%s", user_id)
        text = (
            "⚠️ Не удалось сформировать сводку.\n\n"
            "🔄 Попробуйте снова."
        )
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
            "✍️ Давайте исправим заявку\n\n"
            "🧭 Выберите направление обмена:",
            reply_markup=kb_start(),
        )
        await state.set_state(ExchangeFlow.choosing_direction)

    except Exception:
        log.exception("confirm_no failed: user_id=%s", cb.from_user.id)
        await cb.message.answer("⚠️ Произошла ошибка. Попробуйте снова.")
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
        await edit_or_send(
            cb.message,
            "⚠️ Заявку в CRM сейчас создать не удалось (временная ошибка).\n\n"
            "🔄 Нажмите «✅ Да» ещё раз через минуту.",
            reply_markup=kb_confirm(),
        )
        return

    except CRMPermanentError:
        await edit_or_send(
            cb.message,
            "⚠️ Заявку в CRM сейчас создать не удалось.\n\n"
            "👤 Напишите менеджеру @coinpointlara — он поможет вручную.",
            reply_markup=None,
        )
        return

    except ValueError as e:
        log.warning("confirm_yes rejected: user_id=%s err=%s", cb.from_user.id, str(e))
        await edit_or_send(
            cb.message,
            "⚠️ Не получилось подтвердить заявку.\n\n"
            "Пожалуйста, пройдите шаги заново через /start.",
            reply_markup=None,
        )
        await state.clear()
        return

    except Exception:
        log.exception("confirm_yes failed: user_id=%s", cb.from_user.id)
        await cb.message.answer("⚠️ Произошла ошибка. Попробуйте снова.")
        return

    await state.clear()

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if result.already_exists:
        await cb.message.answer(
            "✅ Заявка уже создана\n\n"
            "👤 Менеджер свяжется с вами, как только возьмёт её в работу."
        )
        return

    await cb.message.answer(
        "✅ Заявка создана!\n\n"
        "👤 Менеджер свяжется с вами в Telegram, как только возьмёт заявку в работу."
    )