from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DirectionLiteral = Literal["USDT_TO_CASH", "CASH_TO_USDT"]


@dataclass(frozen=True)
class Office:
    id: str
    button_text: str
    city: str


class CRMClientMock:
    def __init__(self) -> None:
        self._offices = [
            {"id": "antalya_1", "button_text": "Анталья 1 (адрес)", "city": "Antalya"},
            {"id": "antalya_2", "button_text": "Анталья 2 (адрес)", "city": "Antalya"},
            {"id": "istanbul", "button_text": "Стамбул", "city": "Istanbul"},
        ]

    def get_offices(self) -> list[dict]:
        return list(self._offices)

    def get_office_label(self, office_id: str) -> str:
        for o in self._offices:
            if o["id"] == office_id:
                return o["button_text"]
        return office_id  # fallback

    def get_rate(self, office_id: str, direction: DirectionLiteral) -> float:
        base = {"antalya_1": 1.00, "antalya_2": 1.01, "istanbul": 0.99}[office_id]
        if direction == "USDT_TO_CASH":
            return base
        return base * 0.995

    def create_request(self, payload: dict) -> dict:
        return {"crm_request_id": f"CRM-{payload['client_request_id']}"}

    def send_event(self, payload: dict) -> None:
        return None

    def check_status(self, crm_request_id: str) -> dict:
        return {"status": "new"}