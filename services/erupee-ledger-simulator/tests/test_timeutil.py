"""app/timeutil.py::as_utc() — regression coverage for the bug where
`.replace(tzinfo=timezone.utc)` relabeled an already-aware (IST) datetime
instead of converting it, silently inflating every TTL by 5.5 hours on
this machine's Postgres (session TimeZone=Asia/Calcutta)."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.timeutil import as_utc


def test_naive_datetime_is_treated_as_utc():
    naive = datetime(2026, 1, 1, 12, 0, 0)
    assert as_utc(naive) == datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_utc_aware_datetime_is_unchanged():
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert as_utc(aware) == aware


def test_ist_aware_datetime_is_converted_not_relabeled():
    """The exact failure mode: an IST 15:00 (i.e. UTC 09:30) must convert
    to UTC 09:30, not get relabeled as UTC 15:00 (a 5.5-hour error)."""
    ist = ZoneInfo("Asia/Calcutta")
    ist_time = datetime(2026, 1, 1, 15, 0, 0, tzinfo=ist)

    converted = as_utc(ist_time)

    assert converted == datetime(2026, 1, 1, 9, 30, 0, tzinfo=timezone.utc)
    # the buggy .replace() behavior would have produced this instead:
    assert converted != datetime(2026, 1, 1, 15, 0, 0, tzinfo=timezone.utc)


def test_round_trip_preserves_the_absolute_instant():
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(ZoneInfo("Asia/Calcutta"))
    assert as_utc(now_ist) - now_utc < timedelta(microseconds=1)
