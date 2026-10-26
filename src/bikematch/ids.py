"""Identifier generation.

Internal identifiers are UUIDv7: time-ordered, so they sort by creation and give
good B-tree locality in SQLite without needing a separate sequence column.

Human-facing case identifiers are short, transcribable aliases -- people read
them off a screen and type them into email subject lines -- so they use a
reduced alphabet with the visually ambiguous characters removed.

``uuid.uuid7`` only exists from Python 3.14; this package targets >=3.12, so the
RFC 9562 layout is constructed here rather than imported.
"""

from __future__ import annotations

import datetime as _dt
import os
import secrets
import uuid

__all__ = [
    "is_case_alias",
    "is_check_alias",
    "new_case_alias",
    "new_check_alias",
    "new_id",
    "uuid7",
]

# Crockford-style alphabet with I, L, O and U removed. I/1, O/0 and L/1 are the
# pairs people mistype when copying an ID out of an email; U is dropped so that
# generated codes cannot spell anything unfortunate.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ALIAS_BODY_LEN = 6
_CASE_PREFIX = "EDB"
_CHECK_PREFIX = "CHK"


def uuid7() -> uuid.UUID:
    """Return a UUID version 7.

    Layout per RFC 9562 section 5.7::

        unix_ts_ms (48) | ver (4) | rand_a (12) | var (2) | rand_b (62)

    The timestamp is Unix epoch milliseconds and is *not* guaranteed strictly
    increasing across NTP adjustments, so these sort by creation time but must
    not be relied on as a uniqueness-by-ordering guarantee.
    """
    ts_ms = _dt.datetime.now(_dt.UTC).timestamp()
    unix_ts_ms = int(ts_ms * 1000)

    # 74 random bits are needed (12 + 62); take 10 bytes and slice the integer
    # so the entropy is spread across both fields rather than truncated.
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = (rand >> 62) & 0x0FFF
    rand_b = rand & ((1 << 62) - 1)

    value = (unix_ts_ms & 0xFFFF_FFFF_FFFF) << 80
    value |= 0x7 << 76  # version
    value |= rand_a << 64
    value |= 0b10 << 62  # variant
    value |= rand_b
    return uuid.UUID(int=value)


def new_id() -> str:
    """A new internal identifier as a canonical UUID string."""
    return str(uuid7())


def _new_alias(prefix: str, year: int | None) -> str:
    if year is None:
        year = _dt.datetime.now(_dt.UTC).year
    if type(year) is not int or not 1000 <= year <= 9999:
        raise ValueError("case alias year must be a four-digit calendar year")
    body = "".join(secrets.choice(_ALPHABET) for _ in range(_ALIAS_BODY_LEN))
    return f"{prefix}-{year}-{body}"


def _is_alias(value: str, prefix: str) -> bool:
    # Email subject parsing receives untrusted strings. Keep malformed or
    # non-string input out of the case lookup path without raising.
    if not isinstance(value, str):
        return False
    parts = value.strip().upper().split("-")
    if len(parts) != 3:
        return False
    got_prefix, year, body = parts
    return (
        got_prefix == prefix
        and len(year) == 4
        and year.isascii()
        and year.isdecimal()
        and int(year) >= 1000
        and len(body) == _ALIAS_BODY_LEN
        and all(c in _ALPHABET for c in body)
    )


def new_case_alias(year: int | None = None) -> str:
    """Human-facing stolen-bike case identifier, e.g. ``EDB-2026-8F3K2Q``."""
    return _new_alias(_CASE_PREFIX, year)


def new_check_alias(year: int | None = None) -> str:
    """Human-facing reverse-check identifier, e.g. ``CHK-2026-8F3K2Q``."""
    return _new_alias(_CHECK_PREFIX, year)


def is_case_alias(value: str) -> bool:
    """Whether ``value`` is a well-formed case alias.

    Used when recovering the target case from an email subject line, so it is
    deliberately strict: a false positive would attach photographs to the wrong
    owner's case.
    """
    return _is_alias(value, _CASE_PREFIX)


def is_check_alias(value: str) -> bool:
    """Whether ``value`` is a well-formed reverse-check alias."""
    return _is_alias(value, _CHECK_PREFIX)
