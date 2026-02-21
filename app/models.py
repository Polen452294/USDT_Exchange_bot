from __future__ import annotations

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Direction(str, enum.Enum):
    USDT_TO_CASH = "USDT_TO_CASH"
    CASH_TO_USDT = "CASH_TO_USDT"


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    transport: Mapped[str] = mapped_column(String(16), default="tg", index=True)
    peer_id: Mapped[int] = mapped_column(BigInteger, index=True)

    telegram_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    direction: Mapped[Optional[Direction]] = mapped_column(Enum(Direction), nullable=True)
    give_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    office_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    desired_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    nudge2_planned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge2_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge2_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    step6_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge3_planned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    nudge3_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge3_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    nudge4_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge4_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    nudge5_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge5_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    nudge6_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge6_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    nudge7_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge7_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    nudge2_answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge4_planned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    client_request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    last_step: Mapped[str] = mapped_column(String(64), default="start")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("transport", "peer_id", name="uq_drafts_transport_peer_id"),
    )


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    transport: Mapped[str] = mapped_column(String(16), default="tg", index=True)
    peer_id: Mapped[int] = mapped_column(BigInteger, index=True)

    telegram_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    client_request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    crm_request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    direction: Mapped[Direction] = mapped_column(Enum(Direction))
    give_amount: Mapped[float] = mapped_column(Float)

    office_id: Mapped[str] = mapped_column(String(64))
    desired_date: Mapped[date] = mapped_column(Date)

    rate: Mapped[float] = mapped_column(Float)
    receive_amount: Mapped[float] = mapped_column(Float)

    username: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), default="created")

    summary_text: Mapped[str] = mapped_column(Text)

    nudge1_planned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge1_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge1_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    nudge5_planned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge5_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge5_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    nudge5_answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    nudge6_planned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge6_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge6_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    nudge6_answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    nudge7_planned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge7_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    nudge7_answer: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    nudge7_answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)