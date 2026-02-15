from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Office:
    id: str
    title: str


@dataclass(frozen=True)
class Rate:
    value: float


@dataclass(frozen=True)
class CreateRequestResult:
    crm_request_id: str | None
    raw: dict[str, Any]