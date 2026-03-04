# app/utils/__init__.py
from __future__ import annotations

import re
from datetime import date


_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")


def parse_amount(text: str) -> float:
    s = (text or "").strip().replace(" ", "").replace(",", ".")
    if not s:
        raise ValueError("empty")

    try:
        value = float(s)
    except Exception as e:
        raise ValueError("not_a_number") from e

    if value <= 0:
        raise ValueError("non_positive")

    if value > 10**12:
        raise ValueError("too_large")

    return value


def parse_date_ddmmyyyy(text: str) -> date:
    s = (text or "").strip()
    parts = s.split(".")
    if len(parts) != 3:
        raise ValueError("bad_format")

    dd, mm, yyyy = parts
    if not (dd.isdigit() and mm.isdigit() and yyyy.isdigit()):
        raise ValueError("bad_format")

    return date(int(yyyy), int(mm), int(dd))


def normalize_username(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("@"):
        s = s[1:].strip()

    if not s or not _USERNAME_RE.fullmatch(s):
        raise ValueError("bad_username")

    return s