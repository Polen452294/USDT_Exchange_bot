from __future__ import annotations

from datetime import datetime, date
from typing import Tuple

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

    if t in ("/start", "начать", "старт", "меню"):
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
        res = await request_service.confirm_request_ctx("vk", peer_id)
        if res.already_exists:
            return {
                "text": "Готово ✅ Заявка уже была создана. Менеджер свяжется с вами в Telegram, как только возьмёт её в работу.",
                "keyboard": main_menu_keyboard(),
            }
        return {
            "text": "Готово ✅ Заявка создана. Менеджер свяжется с вами, как только возьмёт её в работу.",
            "keyboard": main_menu_keyboard(),
        }

    if t_raw == "Нет, хочу внести изменения":
        await draft_service.reset("vk", peer_id)
        return {"text": "Хорошо, давайте поправим. Выберите направление перевода", "keyboard": direction_keyboard()}

    return None