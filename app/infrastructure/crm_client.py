from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal, Optional

import httpx

from app.config import settings

DirectionLiteral = Literal["USDT_TO_CASH", "CASH_TO_USDT"]

log = logging.getLogger("crm")


@dataclass(frozen=True)
class Office:
    id: str
    button_text: str
    city: str


class CRMError(RuntimeError):
    pass


class CRMTemporaryError(CRMError):
    pass


class CRMPermanentError(CRMError):
    pass


def _join_url(base: str, path: str) -> str:
    base = (base or "").rstrip("/")
    path = (path or "").strip()
    if not path.startswith("/"):
        path = "/" + path
    return base + path


class CRMClientMock:
    def __init__(self) -> None:
        self._offices = [
            {"id": "antalya_1", "button_text": "Анталья 1 (адрес)", "city": "Antalya"},
            {"id": "antalya_2", "button_text": "Анталья 2 (адрес)", "city": "Antalya"},
            {"id": "istanbul", "button_text": "Стамбул", "city": "Istanbul"},
        ]

    async def get_offices(self) -> list[dict]:
        return list(self._offices)

    async def get_office_label(self, office_id: str) -> str:
        for o in self._offices:
            if o["id"] == office_id:
                return o["button_text"]
        return office_id

    async def get_rate(self, office_id: str, direction: DirectionLiteral) -> float:
        base = {"antalya_1": 1.00, "antalya_2": 1.01, "istanbul": 0.99}[office_id]
        if direction == "USDT_TO_CASH":
            return base
        return base * 0.995

    async def create_request(self, payload: dict, *, idempotency_key: str) -> dict:
        return {"crm_request_id": f"CRM-{idempotency_key}"}

    async def send_event(self, payload: dict, *, idempotency_key: Optional[str] = None) -> None:
        return None

    async def check_status(self, crm_request_id: str) -> dict:
        return {"status": "new"}


class CRMClientHTTP:
    def __init__(self) -> None:
        if not settings.crm_base_url:
            raise ValueError("crm_base_url is empty")
        self._base_url = settings.crm_base_url.rstrip("/")
        self._timeout = float(settings.crm_timeout)

    def _headers(self, *, idempotency_key: Optional[str] = None) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if settings.crm_token:
            headers[settings.crm_auth_header] = (
                f"{settings.crm_auth_prefix} {settings.crm_token}".strip()
            )
        if idempotency_key:
            headers[settings.crm_idempotency_header] = idempotency_key
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        max_attempts: int = 3,
    ) -> Any:
        url = _join_url(self._base_url, path)
        last_err: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.request(
                        method=method,
                        url=url,
                        headers=self._headers(idempotency_key=idempotency_key),
                        json=json,
                    )

                if 200 <= resp.status_code < 300:
                    if resp.content:
                        return resp.json()
                    return None

                if resp.status_code in (408, 429, 500, 502, 503, 504):
                    raise CRMTemporaryError(
                        f"{method} {path} temporary error {resp.status_code}"
                    )

                raise CRMPermanentError(
                    f"{method} {path} permanent error {resp.status_code}: {resp.text[:300]}"
                )

            except (httpx.TimeoutException, httpx.NetworkError, CRMTemporaryError) as e:
                last_err = e
                if attempt >= max_attempts:
                    break
                await asyncio.sleep(0.3 * (2 ** (attempt - 1)))
            except CRMPermanentError:
                raise
            except Exception as e:
                last_err = e
                break

        raise CRMTemporaryError(str(last_err) if last_err else "crm request failed")

    async def get_offices(self) -> list[dict]:
        data = await self._request("GET", settings.crm_offices_path)
        if isinstance(data, dict) and "offices" in data and isinstance(data["offices"], list):
            return list(data["offices"])
        if isinstance(data, list):
            return list(data)
        raise CRMPermanentError("unexpected offices format")

    async def get_office_label(self, office_id: str) -> str:
        offices = await self.get_offices()
        for o in offices:
            if str(o.get("id")) == str(office_id):
                return str(
                    o.get("button_text")
                    or o.get("title")
                    or o.get("name")
                    or office_id
                )
        return office_id

    async def get_rate(self, office_id: str, direction: DirectionLiteral) -> float:
        payload = {"office_id": office_id, "direction": direction}
        data = await self._request("POST", settings.crm_rates_path, json=payload)
        if isinstance(data, dict) and "rate" in data:
            return float(data["rate"])
        raise CRMPermanentError("unexpected rate format")

    async def create_request(self, payload: dict, *, idempotency_key: str) -> dict:
        data = await self._request(
            "POST",
            settings.crm_create_request_path,
            json=payload,
            idempotency_key=idempotency_key,
            max_attempts=3,
        )
        if isinstance(data, dict) and ("crm_request_id" in data or "id" in data):
            crm_id = data.get("crm_request_id") or data.get("id")
            return {"crm_request_id": str(crm_id)}
        raise CRMPermanentError("unexpected create_request format")

    async def send_event(self, payload: dict, *, idempotency_key: Optional[str] = None) -> None:
        await self._request(
            "POST",
            settings.crm_event_path,
            json=payload,
            idempotency_key=idempotency_key,
            max_attempts=3,
        )

    async def check_status(self, crm_request_id: str) -> dict:
        payload = {"crm_request_id": crm_request_id}
        data = await self._request(
            "POST",
            settings.crm_status_path,
            json=payload,
            max_attempts=3,
        )
        if isinstance(data, dict):
            return data
        raise CRMPermanentError("unexpected status format")


def get_crm_client():
    mode = (settings.crm_mode or "mock").strip().lower()
    if mode == "mock":
        return CRMClientMock()
    return CRMClientHTTP()