from __future__ import annotations

from app.config import settings
from app.crm.client import CRMClientHTTP, CRMClientMock, CRMClientProtocol


def get_crm_client() -> CRMClientProtocol:
    if settings.crm_mode == "http":
        return CRMClientHTTP(
            base_url=settings.crm_base_url,
            token=settings.crm_token,
            timeout_s=settings.crm_timeout,
        )
    return CRMClientMock()