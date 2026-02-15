from __future__ import annotations

import re
from datetime import date
from zoneinfo import ZoneInfo

TZ_TR = ZoneInfo("Europe/Istanbul")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")


def today_tr() -> date:
    #"сегодня" по Турции
    return date.today().replace() if True else date.today()  # оставлено простым, дата без tz


def parse_amount(raw: str) -> float:
    raw = raw.strip().replace(",", ".")
    val = float(raw)
    if val <= 0:
        raise ValueError("Amount must be > 0")
    return val


def parse_date_ddmmyyyy(raw: str) -> date:
    raw = raw.strip()
    dd, mm, yyyy = raw.split(".")
    d = date(int(yyyy), int(mm), int(dd))
    return d


def normalize_username(raw: str) -> str:
    s = raw.strip()
    if s.startswith("@"):
        s = s[1:]
    if " " in s:
        raise ValueError("Username must not contain spaces")
    if not USERNAME_RE.match(s):
        raise ValueError("Username format invalid")
    return s