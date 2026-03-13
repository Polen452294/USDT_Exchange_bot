from __future__ import annotations

from datetime import datetime, date
from typing import Tuple

from sqlalchemy import select, desc

from app.models import Draft, Request, Direction
from app.vk.keyboards import (
    main_menu_keyboard,
    direction_keyboard,
    offices_keyboard,
    confirm_keyboard,
    hide_keyboard,
    dates_keyboard,
)

SEP = "━━━━━━━━━━━━━━"


def _today() -> date:
    return datetime.utcnow().date()


def _parse_amount(text: str) -> float | None:
    t = (text or "").strip().replace(",", ".")
    try:
        value = float(t)
    except Exception:
        return None
    if value <= 0:
        return None
    return value


def _parse_date_button(text: str) -> date | None:
    t = (text or "").strip()
    if "·" not in t:
        return None

    parts = [p.strip() for p in t.split("·")]
    if not parts:
        return None

    raw = parts[-1]
    try:
        parsed = datetime.strptime(raw, "%d.%m").date()
    except Exception:
        return None

    today = _today()
    d = parsed.replace(year=today.year)

    if d < today:
        return None

    return d


def _parse_date_manual(text: str) -> date | None:
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
        ("antalya_1", "🏢 Анталия Центр"),
        ("antalya_2", "🏢 Анталия Лара"),
        ("istanbul", "🏢 Стамбул"),
    ]


def _office_text() -> str:
    return (
        "🏢 Выберите офис, где вам удобнее провести обмен:\n\n"
        "📍 Анталия Центр\n"
        "Kestane İş Merkezi\n"
        "Muratpaşa, 07040 Muratpaşa/Antalya, Турция\n\n"
        "📍 Анталия Лара\n"
        "Çağlayan, Barınaklar Blv.\n"
        "Köken Apartman No: 27/A, Zemin Kat\n"
        "07010 Muratpaşa/Antalya, Турция\n\n"
        "📍 Стамбул\n"
        "Vilayethan binasında bulunan - IB nolu dükkanlar, Alemdar, Ankara Cd. No:8\n"
        "34110 Fatih/İstanbul, Турция\n"
        f"{SEP}\n"
        "👇 Нажмите кнопку с нужным офисом."
    )


def _date_text() -> str:
    return "📅 Выберите дату сделки (из ближайших 7 дней)\n\n"


def _start_text() -> str:
    return (
        "👋 Привет! Я помогу оформить заявку на обмен.\n\n"
        "🧭 Выберите направление обмена ниже.\n\n"
        f"{SEP}\n"
        "ℹ️ После подтверждения менеджер свяжется с вами.\n"
        "Если нужно быстро задать вопрос — пишите @coinpointlara."
    )


async def handle_vk_message(container, peer_id: int, user_id: int, text: str, vk_profile_url: str):
    t_raw = (text or "").strip()
    t = t_raw.lower()

    draft_service = container.drafts_service
    request_service = container.requests_service
    session = container.session
    now = datetime.utcnow()

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

    if t_raw in {
        "✅ Да, актуально",
        "Да, актуально",
        "❌ Нет, не актуально",
        "Нет, не актуально",
    }:
        req = await _get_last_request()
        if req is None:
            return {
                "text": "Заявка не найдена. Нажмите «📝 Создать заявку».",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "nudge",
            }

        if req.nudge1_answer is not None:
            return {
                "text": "Ответ уже принят ✅",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "nudge",
            }

        if t_raw in {"✅ Да, актуально", "Да, актуально"}:
            req.nudge1_answer = "actual"
            req.nudge1_sent_at = req.nudge1_sent_at or now
            await session.commit()
            return {
                "text": "Отлично ✅ Передал менеджеру, он свяжется с вами.",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "nudge",
            }

        req.nudge1_answer = "not_actual"
        req.nudge1_sent_at = req.nudge1_sent_at or now
        await session.commit()
        return {
            "text": "Понял ✅ Если понадобится обмен — можете начать заново через «📝 Создать заявку».",
            "keyboard": main_menu_keyboard(),
            "edit": True,
            "edit_key": "nudge",
        }

    if t_raw in {
        "➡️ Продолжить",
        "Продолжить",
        "⏳ Я ещё подумаю",
        "Я ещё подумаю",
    }:
        draft = await _get_draft()
        if draft is None:
            return {
                "text": "Нажмите «📝 Создать заявку», чтобы начать.",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "nudge",
            }

        if draft.nudge2_answer is not None:
            return {
                "text": "Ответ уже принят ✅",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "nudge",
            }

        if t_raw in {"➡️ Продолжить", "Продолжить"}:
            draft.nudge2_answer = "continue"
            draft.nudge2_answered_at = now
            draft.nudge2_planned_at = None
            await session.commit()

            if draft.direction and draft.give_amount and draft.office_id and draft.desired_date:
                summary = await request_service.build_summary_ctx("vk", peer_id)
                return {
                    "text": summary.summary_text,
                    "keyboard": confirm_keyboard(),
                    "edit": True,
                    "edit_key": "flow",
                }

            if draft.direction and draft.give_amount and draft.office_id:
                return {
                    "text": _date_text(),
                    "keyboard": dates_keyboard(),
                    "edit": True,
                    "edit_key": "flow",
                }

            if draft.direction and draft.give_amount:
                return {
                    "text": _office_text(),
                    "keyboard": offices_keyboard(_offices()),
                    "edit": True,
                    "edit_key": "flow",
                }

            return {
                "text": "🧭 Выберите направление обмена:",
                "keyboard": direction_keyboard(),
                "edit": True,
                "edit_key": "flow",
            }

        draft.nudge2_answer = "later"
        draft.nudge2_answered_at = now
        await session.commit()
        return {
            "text": "Хорошо, понял. Если решите продолжить — нажмите «📝 Создать заявку».",
            "keyboard": main_menu_keyboard(),
            "edit": True,
            "edit_key": "nudge",
        }

    if t_raw in {
        "✅ Да, зафиксировать",
        "Да, зафиксировать",
        "⏳ Не сейчас",
        "Не сейчас",
    }:
        draft = await _get_draft()
        if draft is None:
            return {
                "text": "Ок.",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "nudge",
            }

        if draft.nudge3_answer is not None:
            return {
                "text": "Ответ уже принят ✅",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "nudge",
            }

        if t_raw in {"✅ Да, зафиксировать", "Да, зафиксировать"}:
            draft.nudge3_answer = "yes"
            await session.commit()
            return {
                "text": "Отлично ✅ Передал менеджеру, он поможет зафиксировать условия.",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "nudge",
            }

        draft.nudge3_answer = "no"
        await session.commit()
        return {
            "text": "Хорошо 👍 Если решите продолжить — нажмите «📝 Создать заявку».",
            "keyboard": main_menu_keyboard(),
            "edit": True,
            "edit_key": "nudge",
        }

    if t_raw in {"✅ Да", "Да"}:
        draft = await _get_draft()
        if draft and draft.nudge4_sent_at is not None and draft.nudge4_answer is None:
            draft.nudge4_answer = "yes"
            draft.updated_at = now
            await session.commit()
            return {
                "text": "Отлично ✅ Передал менеджеру, он свяжется с вами.",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "nudge",
            }

    if t_raw in {"✅ Да", "Да", "❌ Нет", "Нет"}:
        req = await _get_last_request()
        if req:
            if req.nudge5_sent_at is not None and req.nudge5_answer is None:
                req.nudge5_answer = "YES" if t_raw in {"✅ Да", "Да"} else "NO"
                req.nudge5_answered_at = now
                await session.commit()
                if req.nudge5_answer == "YES":
                    return {
                        "text": "Отлично. Передал менеджеру, он свяжется с вами.",
                        "keyboard": main_menu_keyboard(),
                        "edit": True,
                        "edit_key": "nudge",
                    }
                return {
                    "text": "Хорошо, понял. Если понадобится помощь — пишите @coinpointlara.",
                    "keyboard": main_menu_keyboard(),
                    "edit": True,
                    "edit_key": "nudge",
                }

            if req.nudge6_sent_at is not None and req.nudge6_answer is None:
                req.nudge6_answer = "YES" if t_raw in {"✅ Да", "Да"} else "NO"
                req.nudge6_answered_at = now
                await session.commit()
                if req.nudge6_answer == "YES":
                    return {
                        "text": "Отлично. Передал менеджеру, он свяжется с вами.",
                        "keyboard": main_menu_keyboard(),
                        "edit": True,
                        "edit_key": "nudge",
                    }
                return {
                    "text": "Хорошо, понял. Если понадобится помощь — пишите @coinpointlara.",
                    "keyboard": main_menu_keyboard(),
                    "edit": True,
                    "edit_key": "nudge",
                }

            if req.nudge7_sent_at is not None and req.nudge7_answer is None:
                req.nudge7_answer = "YES" if t_raw in {"✅ Да", "Да"} else "NO"
                req.nudge7_answered_at = now
                await session.commit()
                if req.nudge7_answer == "YES":
                    return {
                        "text": "Отлично. Передал менеджеру, он свяжется с вами.",
                        "keyboard": main_menu_keyboard(),
                        "edit": True,
                        "edit_key": "nudge",
                    }
                return {
                    "text": "Хорошо. Если понадобится помощь — пишите @coinpointlara.",
                    "keyboard": main_menu_keyboard(),
                    "edit": True,
                    "edit_key": "nudge",
                }

    if t in {"/start", "начать", "старт", "меню"}:
        await draft_service.reset("vk", peer_id)
        return {
            "text": _start_text(),
            "keyboard": direction_keyboard(),
            "edit": True,
            "edit_key": "flow",
        }

    if t_raw in {"Информация", "📝 Создать заявку", "Создать заявку"}:
        await draft_service.reset("vk", peer_id)
        return {
            "text": _start_text(),
            "keyboard": direction_keyboard(),
            "edit": True,
            "edit_key": "flow",
        }

    if t_raw == "USDT в наличные":
        await draft_service.set_direction("vk", peer_id, Direction.USDT_TO_TRY_CASH)
        return {
            "text": (
                "💰 Укажите сумму, которую вы отдаёте\n\n"
                f"{SEP}\n"
                "✍️ Отправьте число сообщением\n"
                "Валюта: USDT"
            ),
            "keyboard": hide_keyboard(),
            "edit": True,
            "edit_key": "flow",
        }

    if t_raw == "Наличные в USDT":
        await draft_service.set_direction("vk", peer_id, Direction.TRY_CASH_TO_USDT)
        return {
            "text": (
                "💰 Укажите сумму, которую вы отдаёте\n\n"
                f"{SEP}\n"
                "✍️ Отправьте число сообщением\n"
                "Валюта: TRY"
            ),
            "keyboard": hide_keyboard(),
            "edit": True,
            "edit_key": "flow",
        }

    amount = _parse_amount(t_raw)
    if amount is not None:
        await draft_service.set_amount("vk", peer_id, amount)
        return {
            "text": _office_text(),
            "keyboard": offices_keyboard(_offices()),
            "edit": True,
            "edit_key": "flow",
        }

    office_map = {label: oid for oid, label in _offices()}
    if t_raw in office_map:
        await draft_service.set_office("vk", peer_id, office_map[t_raw])
        return {
            "text": _date_text(),
            "keyboard": dates_keyboard(),
            "edit": True,
            "edit_key": "flow",
        }

    parsed_button_date = _parse_date_button(t_raw)
    if parsed_button_date is not None:
        await draft_service.set_date("vk", peer_id, parsed_button_date)
        await draft_service.set_username("vk", peer_id, vk_profile_url)
        summary = await request_service.build_summary_ctx("vk", peer_id)
        return {
            "text": summary.summary_text,
            "keyboard": confirm_keyboard(),
            "edit": True,
            "edit_key": "flow",
        }

    parsed_manual_date = _parse_date_manual(t_raw)
    if parsed_manual_date is not None:
        await draft_service.set_date("vk", peer_id, parsed_manual_date)
        await draft_service.set_username("vk", peer_id, vk_profile_url)
        summary = await request_service.build_summary_ctx("vk", peer_id)
        return {
            "text": summary.summary_text,
            "keyboard": confirm_keyboard(),
            "edit": True,
            "edit_key": "flow",
        }

    if t_raw == "✅ Да, всё отлично":
        draft = await draft_service.get("vk", peer_id)
        if not draft or draft.last_step != "summary":
            return {
                "text": "Заявка уже обработана. Нажмите «📝 Создать заявку».",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "flow",
            }

        result = await request_service.confirm_request_ctx("vk", peer_id)

        if result.already_exists:
            return {
                "text": (
                    "✅ Заявка уже создана\n\n"
                    "👤 Менеджер свяжется с вами, как только возьмёт её в работу."
                ),
                "keyboard": main_menu_keyboard(),
                "edit": False,
                "edit_key": "flow",
            }

        return {
            "text": (
                "✅ Заявка создана!\n\n"
                "👤 Менеджер свяжется с вами, как только возьмёт заявку в работу."
            ),
            "keyboard": main_menu_keyboard(),
            "edit": False,
            "edit_key": "flow",
        }

    if t_raw == "✍️ Хочу внести изменения":
        draft = await draft_service.get("vk", peer_id)
        if not draft or draft.last_step != "summary":
            return {
                "text": "Сценарий завершён. Чтобы начать заново — нажмите «📝 Создать заявку».",
                "keyboard": main_menu_keyboard(),
                "edit": True,
                "edit_key": "flow",
            }

        await draft_service.reset("vk", peer_id)
        return {
            "text": (
                "✍️ Давайте исправим заявку\n\n"
                "🧭 Выберите направление обмена:"
            ),
            "keyboard": direction_keyboard(),
            "edit": True,
            "edit_key": "flow",
        }

    if t_raw in {"💳 Купить USDT с карты СБП", "Купить USDT с карты СБП"}:
        return {
            "text": "Для покупки USDT с карты СБП перейдите в бот: https://t.me/CoinPlata_bot",
            "keyboard": main_menu_keyboard(),
            "edit": False,
            "edit_key": "flow",
        }

    return {
        "text": "Ок.",
        "keyboard": main_menu_keyboard(),
        "edit": False,
        "edit_key": "flow",
    }