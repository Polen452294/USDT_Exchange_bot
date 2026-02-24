from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Tuple
from sqlalchemy import select, desc
from app.models import Draft, Request
from app.infrastructure.crm_client import get_crm_client
from app.models import Direction
from app.vk.keyboards import (
    main_menu_keyboard,
    direction_keyboard,
    next_keyboard,
    offices_keyboard,
    confirm_keyboard,
    hide_keyboard
)


def _today() -> date:
    return datetime.utcnow().date()


def _today_str() -> str:
    return _today().strftime("%d.%m.%Y")


def _parse_amount(text: str) -> float | None:
    t = (text or "").strip().replace(",", ".")
    try:
        v = float(t)
    except Exception:
        return None
    if v <= 0:
        return None
    return v


def _parse_date(text: str) -> date | None:
    t = (text or "").strip()
    try:
        d = datetime.strptime(t, "%d.%m.%Y").date()
    except Exception:
        return None
    if d < _today():
        return None
    return d


def _offices() -> list[Tuple[str, str]]:
    return [
        ("antalya_1", "Анталья 1 (адрес)"),
        ("antalya_2", "Анталья 2 (адрес)"),
        ("istanbul", "Стамбул"),
    ]


async def handle_vk_message(container, peer_id: int, user_id: int, text: str, vk_profile_url: str):
    t_raw = (text or "").strip()
    t = t_raw.lower()

    draft_service = container.drafts_service
    request_service = container.requests_service
    session = container.session
    now = datetime.utcnow()

    async def _crm_event(nudge_type: str, answer: str, *, client_request_id: str | None) -> None:
        try:
            crm = get_crm_client()
            fn = getattr(crm, "send_nudge_event", None) or getattr(crm, "push_nudge_event", None)
            if fn:
                await fn(
                    nudge_type=nudge_type,
                    answer=answer,
                    client_request_id=client_request_id,
                    timestamp=now,
                    transport="vk",
                    peer_id=int(peer_id),
                )
        except Exception:
            pass

    async def _get_draft() -> Draft | None:
        stmt = select(Draft).where(Draft.transport == "vk", Draft.peer_id == int(peer_id)).limit(1)
        return await session.scalar(stmt)

    async def _get_last_request() -> Request | None:
        stmt = (
            select(Request)
            .where(Request.transport == "vk", Request.peer_id == int(peer_id))
            .order_by(desc(Request.id))
            .limit(1)
        )
        return await session.scalar(stmt)

    # -----------------------
    # NUDGE 1 (Request)
    # -----------------------
    if t_raw in ("Да, актуально", "Нет, не актуально", "Написать менеджеру самому: @coinpointlara"):
        req = await _get_last_request()
        if not req:
            return {"text": "Ок.", "keyboard": hide_keyboard()}

        if req.nudge1_answer is not None:
            return {"text": "Ответ уже принят ✅", "keyboard": hide_keyboard()}

        if t_raw == "Да, актуально":
            req.nudge1_answer = "yes_actual"
            await session.commit()
            await _crm_event("nudge1", "yes_actual", client_request_id=req.client_request_id)
            return {
                "text": (
                    "Отлично 👍\n\n"
                    "Менеджер свяжется с вами в Telegram в ближайшее время.\n"
                    "Если нужно быстрее — напишите @coinpointlara"
                ),
                "keyboard": hide_keyboard(),
            }

        if t_raw == "Нет, не актуально":
            req.nudge1_answer = "no_not_actual"
            await session.commit()
            await _crm_event("nudge1", "no_not_actual", client_request_id=req.client_request_id)
            return {
                "text": "Понял вас. Если обмен снова станет актуальным — нажмите «Создать заявку».",
                "keyboard": hide_keyboard(),
            }

        req.nudge1_answer = "ask_manager_self"
        await session.commit()
        await _crm_event("nudge1", "ask_manager_self", client_request_id=req.client_request_id)
        return {
            "text": "Напишите менеджеру напрямую: @coinpointlara",
            "keyboard": hide_keyboard(),
        }

    # -----------------------
    # NUDGE 2 (Draft)
    # -----------------------
    if t_raw in ("Продолжить", "Задать вопрос менеджеру", "Я еще подумаю"):
        draft = await _get_draft()
        if not draft:
            return {"text": "Нажмите «Создать заявку», чтобы начать.", "keyboard": main_menu_keyboard()}

        if draft.nudge2_answer is not None:
            return {"text": "Ответ уже принят ✅", "keyboard": hide_keyboard()}

        if t_raw == "Продолжить":
            draft.nudge2_answer = "continue"
            draft.nudge2_answered_at = now
            draft.nudge2_planned_at = None
            await session.commit()
            await _crm_event("nudge2", "continue", client_request_id=draft.client_request_id)

            # Возвращаем в актуальный шаг (по ТЗ: обычно шаг 6, если данных хватает)
            if draft.direction and draft.give_amount and draft.office_id:
                if not draft.desired_date:
                    return {
                        "text": (
                            "Когда вам удобно получить наличные? По умолчанию стоит сегодняшняя дата — "
                            f"{_today_str()} — можете оставить её и нажать «Далее». Или нажмите на поле и введите желаемую дату"
                        ),
                        "keyboard": next_keyboard(),
                    }

                summary = await request_service.build_summary_ctx("vk", peer_id)
                return {"text": summary.summary_text, "keyboard": confirm_keyboard()}

            return {"text": "Давайте продолжим. Выберите направление обмена:", "keyboard": direction_keyboard()}

        if t_raw == "Задать вопрос менеджеру":
            draft.nudge2_answer = "ask_manager"
            draft.nudge2_answered_at = now
            await session.commit()
            await _crm_event("nudge2", "ask_manager", client_request_id=draft.client_request_id)
            return {
                "text": "Передал запрос менеджеру. Он свяжется с вами.\nЕсли нужно быстрее — @coinpointlara",
                "keyboard": hide_keyboard(),
            }

        # "Я еще подумаю" → фиксируем отказ (для Дожима 4) и планируем nudge4 через 24 часа
        draft.nudge2_answer = "think"
        draft.nudge2_answered_at = now
        draft.nudge4_planned_at = now + timedelta(hours=24)
        await session.commit()
        await _crm_event("nudge2", "think", client_request_id=draft.client_request_id)
        return {
            "text": "Хорошо 🙂\nЕсли решите продолжить — нажмите «Создать заявку».",
            "keyboard": hide_keyboard(),
        }

    # -----------------------
    # NUDGE 3 (Draft)
    # -----------------------
    if t_raw in ("Да, зафиксировать", "Не сейчас"):
        draft = await _get_draft()
        if not draft:
            return {"text": "Ок.", "keyboard": hide_keyboard()}

        if draft.nudge3_answer is not None:
            return {"text": "Ответ уже принят ✅", "keyboard": hide_keyboard()}

        if t_raw == "Да, зафиксировать":
            draft.nudge3_answer = "yes_fix"
            await session.commit()
            await _crm_event("nudge3", "yes_fix", client_request_id=draft.client_request_id)
            return {
                "text": (
                    "Отлично 👍\n"
                    "Менеджер поможет зафиксировать курс.\n"
                    "Для связи: @coinpointlara"
                ),
                "keyboard": hide_keyboard(),
            }

        draft.nudge3_answer = "not_now"
        await session.commit()
        await _crm_event("nudge3", "not_now", client_request_id=draft.client_request_id)
        return {
            "text": "Понял вас. Если курс снова станет интересен — оформите новую заявку.",
            "keyboard": hide_keyboard(),
        }

    # -----------------------
    # NUDGE 4 (Draft)
    # -----------------------
    if t_raw == "Да":
        draft = await _get_draft()
        if draft and draft.nudge4_sent_at is not None and draft.nudge4_answer is None:
            draft.nudge4_answer = "yes"
            await session.commit()
            await _crm_event("nudge4", "yes", client_request_id=draft.client_request_id)
            return {
                "text": "Принято ✅ Менеджер свяжется с вами и предложит условия.",
                "keyboard": hide_keyboard(),
            }

    # -----------------------
    # NUDGE 5/6/7 (Request)
    # -----------------------
    if t_raw in ("Да", "Нет"):
        req = await _get_last_request()
        if req:
            # n5
            if req.nudge5_sent_at is not None and req.nudge5_answer is None:
                req.nudge5_answer = "yes" if t_raw == "Да" else "no"
                req.nudge5_answered_at = now
                await session.commit()
                await _crm_event("nudge5", req.nudge5_answer, client_request_id=req.client_request_id)
                return {
                    "text": "Спасибо за ответ 🙌",
                    "keyboard": hide_keyboard(),
                }

            # n6
            if req.nudge6_sent_at is not None and req.nudge6_answer is None:
                req.nudge6_answer = "yes" if t_raw == "Да" else "no"
                req.nudge6_answered_at = now
                await session.commit()
                await _crm_event("nudge6", req.nudge6_answer, client_request_id=req.client_request_id)
                return {
                    "text": "Спасибо за ответ 🙌",
                    "keyboard": hide_keyboard(),
                }

            # n7
            if req.nudge7_sent_at is not None and req.nudge7_answer is None:
                req.nudge7_answer = "yes" if t_raw == "Да" else "no"
                req.nudge7_answered_at = now
                await session.commit()
                await _crm_event("nudge7", req.nudge7_answer, client_request_id=req.client_request_id)
                return {
                    "text": "Спасибо за ответ 🙌",
                    "keyboard": hide_keyboard(),
                }

    if t in ("/start", "начать", "старт", "меню"):
        if t in ("/start", "начать", "старт", "меню"):
            await draft_service.reset("vk", peer_id)
            return {
                "text": (
                    "Привет!\n"
                    "Я помогу быстро оформить заявку на обмен USDT ↔ наличные в Турции за несколько шагов:\n"
                    "➔ выберите направление обмена\n"
                    "➔ укажите сумму, которую отдаете\n"
                    "➔ выберите офис в Анталье или Стамбуле\n"
                    "➔ выберите желаемую дату сделки\n"
                    "Потом я покажу вам условия обмена и, если вы согласны, попрошу подтвердить их.\n"
                    "После наш менеджер свяжется с вами в Telegram для обсуждения деталей. Если "
                    "нужно быстро задать вопрос — пишите менеджеру напрямую @coinpointlara.\n"
                    "Нажмите кнопку ниже, чтобы начать 👇"
                ),
                "keyboard": direction_keyboard(),
            }

    if t_raw == "Информация":
        return {
            "text": "Нажмите «Создать заявку», чтобы начать оформление.",
            "keyboard": main_menu_keyboard(),
        }

    if t_raw == "Создать заявку":
        await draft_service.reset("vk", peer_id)
        return {
            "text": "Выберите направление обмена:",
            "keyboard": direction_keyboard(),
        }

    if t_raw == "USDT в наличные":
        await draft_service.set_direction("vk", peer_id, Direction.USDT_TO_CASH)
        return {"text": "Введите, пожалуйста, сумму, которую вы отдаёте.", "keyboard": hide_keyboard()}

    if t_raw == "Наличные в USDT":
        await draft_service.set_direction("vk", peer_id, Direction.CASH_TO_USDT)
        return {"text": "Введите, пожалуйста, сумму, которую вы отдаёте.", "keyboard": hide_keyboard()}

    amount = _parse_amount(t_raw)
    if amount is not None:
        await draft_service.set_amount("vk", peer_id, amount)
        return {
            "text": "Выберите, пожалуйста, где вам удобнее провести обмен",
            "keyboard": offices_keyboard(_offices()),
        }

    office_map = {label: oid for oid, label in _offices()}
    if t_raw in office_map:
        await draft_service.set_office("vk", peer_id, office_map[t_raw])
        return {
            "text": (
                "Когда вам удобно получить наличные? По умолчанию стоит сегодняшняя дата — "
                f"{_today_str()} — можете оставить её и нажать «Далее». "
                "Или нажмите на поле и введите желаемую дату"
            ),
            "keyboard": next_keyboard(),
        }

    draft = await draft_service.get("vk", peer_id)
    if t_raw == "Далее" and draft and draft.last_step == "amount_wait":
        return {"text": "Введите сумму числом (например: 1500).", "keyboard": None}

    if t_raw == "Далее":
        if not draft or not draft.office_id:
            return {"text": "Давайте начнём сначала. Выберите направление обмена:", "keyboard": direction_keyboard()}

        if not draft.desired_date:
            await draft_service.set_date("vk", peer_id, _today())
            await draft_service.set_username("vk", peer_id, vk_profile_url)
            summary = await request_service.build_summary_ctx("vk", peer_id)
            return {"text": summary.summary_text, "keyboard": confirm_keyboard()}

        await draft_service.set_username("vk", peer_id, vk_profile_url)
        summary = await request_service.build_summary_ctx("vk", peer_id)
        return {"text": summary.summary_text, "keyboard": confirm_keyboard()}

    parsed_d = _parse_date(t_raw)
    if parsed_d is not None:
        await draft_service.set_date("vk", peer_id, parsed_d)
        await draft_service.set_username("vk", peer_id, vk_profile_url)
        summary = await request_service.build_summary_ctx("vk", peer_id)
        return {"text": summary.summary_text, "keyboard": confirm_keyboard()}

    if t_raw == "Да, все отлично":
        draft = await draft_service.get("vk", peer_id)
        if not draft or draft.last_step != "summary":
            return {"text": "Заявка уже обработана. Нажмите «Создать заявку».", "keyboard": hide_keyboard()}

        await request_service.confirm_request_ctx("vk", peer_id)
        return {"text": "Готово ✅ Заявка создана. Менеджер свяжется с вами в Telegram.", "keyboard": hide_keyboard()}

    if t_raw == "Нет, хочу внести изменения":
        draft = await draft_service.get("vk", peer_id)

        if not draft or draft.last_step != "summary":
            return {
                "text": "Сценарий уже завершён. Чтобы начать заново — нажмите «Создать заявку».",
                "keyboard": hide_keyboard(),
            }

        await draft_service.reset("vk", peer_id)
        return {
            "text": "Хорошо, давайте поправим. Выберите направление перевода",
            "keyboard": direction_keyboard(),
        }
    
    return {"text": "Ок.", "keyboard": hide_keyboard()}