from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


def now_ist() -> datetime:
    return datetime.now(tz=ISTANBUL_TZ)