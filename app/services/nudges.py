from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import Draft
from app.keyboards import kb_nudge2

log = logging.getLogger("nudges")

NUDGE2_TEXT = (
    "Похоже, вы отвлеклись.\n"
    "Если хотите, я могу продолжить с того места, где вы остановились. "
    "Нажмите «Продолжить», и я покажу сводку и текущий курс."
)

STEPS_FOR_NUDGE2 = [
    "amount_wait",
    "amount",
    "office",
    "date",
    "date_default",
    "username_auto",
    "username_manual",
    "summary",
]


class NudgeService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def tick(self) -> None:
        await self._check_nudge2()

    async def _check_nudge2(self) -> None:
        now = datetime.utcnow()

        async with AsyncSessionLocal() as session:
            stmt = (
                select(
                    Draft.id,
                    Draft.telegram_user_id,
                    Draft.last_step,
                )
                .where(Draft.last_step.in_(STEPS_FOR_NUDGE2))
                .where(Draft.give_amount.is_not(None))
                .where(Draft.nudge2_answer.is_(None))
                .where(Draft.nudge2_sent_at.is_(None))
                .where(Draft.nudge2_planned_at.is_not(None))
                .where(Draft.nudge2_planned_at <= now)
            )

            rows = (await session.execute(stmt)).all()

            if not rows:
                return

            log.info("n2 candidates=%d", len(rows))

            for draft_id, uid, last_step in rows:
                uid = int(uid)

                try:
                    await self.bot.send_message(
                        chat_id=uid,
                        text=NUDGE2_TEXT,
                        reply_markup=kb_nudge2(),
                    )

                    # обновляем через id, чтобы избежать lazy ORM
                    await session.execute(
                        select(Draft).where(Draft.id == draft_id)
                    )
                    draft = await session.get(Draft, draft_id)
                    if draft:
                        draft.nudge2_sent_at = datetime.utcnow()
                        await session.commit()

                    log.info("n2 sent: uid=%s step=%s", uid, last_step)

                except Exception:
                    await session.rollback()
                    log.exception("n2 send failed: uid=%s", uid)