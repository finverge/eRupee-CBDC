"""Postgres on this deployment has its session TimeZone set to
Asia/Calcutta (not UTC), so psycopg returns DateTime(timezone=True)
columns as IST-aware datetimes, not UTC-aware ones. Comparing those
against datetime.now(timezone.utc) requires converting, not relabeling —
`.replace(tzinfo=timezone.utc)` on an already-aware IST value discards
the +05:30 offset instead of applying it, silently inflating every TTL
(OTP/session expiry, PIN lockout) by 5.5 hours. Use as_utc() on any
datetime read back from the database before comparing it to "now"."""
from datetime import datetime, timezone


def as_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
