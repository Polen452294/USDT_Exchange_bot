from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import ExchangeFlow
from app.utils import parse_amount
from app.keyboards import kb_offices
from app.infrastructure.crm_client import get_crm_client, CRMTemporaryError, CRMPermanentError
from app.repositories.drafts import DraftRepository

router = Router()

SEP = "━━━━━━━━━━━━━━"

OFFICE_ADDRESS_BY_ID: dict[str, str] = {
    "antalya_center": (
        "📍 <b>Анталия Центр</b>\n"
        "Kestane İş Merkezi\n"
        "Muratpaşa, 07040 Muratpaşa/Antalya, Турция"
    ),
    "antalya_lara": (
        "📍 <b>Анталия Лара</b>\n"
        "Çağlayan, Barınaklar Blv.\n"
        "Köken Apartman No: 27/A, Zemin Kat\n"
        "07010 Muratpaşa/Antalya, Турция"
    ),
    "istanbul": ( 
        "📍 <b>Стамбул</b>\n"
        "Vilayethan binasında bulunan - IB nolu dükkanlar, Alemdar, Ankara Cd. No:8\n"
        "34110 Fatih/İstanbul, Турция"
    ),
}


def _extract_office_id(o: object) -> str:
    if isinstance(o, dict):
        for k in ("id", "office_id", "code", "slug"):
            v = o.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
    return str(o).strip()


@router.message(ExchangeFlow.entering_amount)
async def enter_amount(message: Message, state: FSMContext, session: AsyncSession):
    try:
        amount = parse_amount(message.text)
    except Exception:
        await message.answer(
            "⚠️ Не получилось распознать сумму.\n\n"
            f"{SEP}\n"
            "✍️ Отправьте число больше 0.\n"
            "Пример: 2000 или 1500.50"
        )
        return

    tg_id = message.from_user.id
    drafts = DraftRepository(session)
    draft = await drafts.get_or_create(transport="tg", peer_id=tg_id, telegram_user_id=tg_id)

    draft.give_amount = float(amount)
    draft.last_step = "amount"
    draft.updated_at = datetime.utcnow()
    await drafts.save()

    crm = get_crm_client()
    try:
        offices = await crm.get_offices()
    except (CRMTemporaryError, CRMPermanentError):
        await message.answer(
            "⚠️ Сейчас не могу получить список офисов.\n\n"
            f"{SEP}\n"
            "👤 Попробуйте чуть позже или напишите менеджеру @coinpointlara."
        )
        return
    except Exception:
        await message.answer(
            "⚠️ Произошла ошибка при получении офисов.\n\n"
            f"{SEP}\n"
            "🔄 Попробуйте чуть позже."
        )
        return

    addresses = [
        OFFICE_ADDRESS_BY_ID["antalya_center"],
        OFFICE_ADDRESS_BY_ID["antalya_lara"],
        OFFICE_ADDRESS_BY_ID["istanbul"],
    ]

    text = (
        "🏢 Выберите офис, где вам удобнее провести обмен:\n\n"
        + "\n\n".join(addresses)
        + f"\n\n{SEP}\n"
        "👇 Нажмите кнопку с нужным офисом."
    )

    await message.answer(text, reply_markup=kb_offices(offices))
    await state.set_state(ExchangeFlow.choosing_office)