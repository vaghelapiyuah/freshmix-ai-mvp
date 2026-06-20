"""Safety utilities (Phase 8 edge cases).

PII redaction — never send emails/phone numbers to the agent or write them to
logs. Applied to free-text before it reaches Claude or any log line.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def redact_pii(text: str | None) -> str:
    if not text:
        return text or ""
    t = _EMAIL.sub("[email]", text)
    t = _PHONE.sub("[phone]", t)
    return t
