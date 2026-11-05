"""
Time helpers.

The database stores naive datetimes that represent UTC (datetime.utcnow()).
Browsers send deadlines either as a bare `datetime-local` value (no zone) or
as an ISO string with 'Z' / an offset. These helpers normalise both to the
naive-UTC convention used throughout the app.
"""
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """Current time as a naive UTC datetime (same convention as the DB)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_deadline(raw: str) -> datetime:
    """
    Parse an ISO-8601 string into a naive UTC datetime.

    - '2030-01-01T10:00:00Z'       -> 10:00 UTC
    - '2030-01-01T10:00:00+09:00'  -> 01:00 UTC
    - '2030-01-01T10:00'           -> treated as UTC (no zone information)

    Raises ValueError for anything that is not ISO-8601.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty deadline")
    if s[-1] in ("Z", "z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def to_api(dt: Optional[datetime]) -> Optional[str]:
    """Serialise a naive-UTC datetime for the API with an explicit 'Z'."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat() + "Z"
