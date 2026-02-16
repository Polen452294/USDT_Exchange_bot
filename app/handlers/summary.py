from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import ExchangeFlow
from app.keyboards import kb_confirm, kb_start
from app.repositories.drafts import DraftRepository
from app.repositories.requests import RequestRepository
from app.services.requests import RequestService
from app.infrastructure.crm_client import CRMTemporaryError, CRMPermanentError

router = Router()


async def send_summary(message: Message, state: FSMContext, session: AsyncSession, *, user_id: int) -> None:
    draft_repo = DraftRepository(session)
    request_repo = RequestRepository(session)
    service = RequestService(draft_repo, request_repo)

    try:
        summary = await service.build_summary(user_id)
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
        await message.answer("Не удалось сформировать сводку. Попробуйте снова.")
        return

    await message.answer(summary.summary_text, reply_markup=kb_confirm())
    await state.set_state(ExchangeFlow.confirming)


@router.callback_query(F.data == "confirm:no")
async def confirm_no(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await cb.answer()

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
        await draft_repo.save()

    await state.clear()
    await cb.message.answer(
        "Хорошо, давайте поправим. Выберите направление перевода",
        reply_markup=kb_start(),
    )
    await state.set_state(ExchangeFlow.choosing_direction)


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
    except Exception:
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