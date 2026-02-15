from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

import httpx

from app.crm.exceptions import CRMAuthError, CRMInvalidResponse, CRMTemporaryError
from app.crm.schemas import CreateRequestResult, Office, Rate


class CRMClientProtocol:
    async def get_offices(self) -> list[Office]:
        raise NotImplementedError

    async def get_rate(self, office_id: str, direction: str) -> Rate:
        raise NotImplementedError

    async def create_request(self, payload: dict[str, Any]) -> CreateRequestResult:
        raise NotImplementedError


class CRMClientMock(CRMClientProtocol):
    async def get_offices(self) -> list[Office]:
        return [
            Office(id="antalya_1", title="Анталья 1 (адрес)"),
            Office(id="antalya_2", title="Анталья 2 (адрес)"),
            Office(id="istanbul", title="Стамбул"),
        ]

    async def get_rate(self, office_id: str, direction: str) -> Rate:
        base = 30.0 if direction == "USDT_TO_CASH" else 1.0
        return Rate(value=base)

    async def create_request(self, payload: dict[str, Any]) -> CreateRequestResult:
        return CreateRequestResult(crm_request_id="mock-req-1", raw={"ok": True, "payload": payload})


class CRMClientHTTP(CRMClientProtocol):
    def __init__(self, base_url: str, token: str, timeout_s: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout_s

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                r = await client.request(method, url, headers=self._headers(), json=json)
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as e:
                raise CRMTemporaryError(str(e)) from e

        if r.status_code in (401, 403):
            raise CRMAuthError(f"CRM auth failed: {r.status_code}")

        if 500 <= r.status_code <= 599:
            raise CRMTemporaryError(f"CRM 5xx: {r.status_code}")

        try:
            data = r.json()
        except Exception as e:
            raise CRMInvalidResponse("CRM returned non-json response") from e

        if r.status_code >= 400:
            raise CRMInvalidResponse(f"CRM error: {r.status_code} body={data}")

        if not isinstance(data, dict):
            raise CRMInvalidResponse("CRM json is not an object")
        return data

    async def get_offices(self) -> list[Office]:
        data = await self._request("GET", "/offices")
        items = data.get("offices")
        if not isinstance(items, list):
            raise CRMInvalidResponse("offices is not list")
        res: list[Office] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            oid = str(it.get("id", "")).strip()
            title = str(it.get("title", "")).strip()
            if oid and title:
                res.append(Office(id=oid, title=title))
        return res

    async def get_rate(self, office_id: str, direction: str) -> Rate:
        data = await self._request("GET", f"/rates?office_id={office_id}&direction={direction}")
        val = data.get("rate")
        if val is None:
            raise CRMInvalidResponse("rate is missing")
        try:
            v = float(val)
        except Exception as e:
            raise CRMInvalidResponse("rate is not numeric") from e
        return Rate(value=v)

    async def create_request(self, payload: dict[str, Any]) -> CreateRequestResult:
        data = await self._request("POST", "/requests", json=payload)
        crm_id = data.get("crm_request_id") or data.get("id")
        if crm_id is not None:
            crm_id = str(crm_id)
        return CreateRequestResult(crm_request_id=crm_id, raw=data)