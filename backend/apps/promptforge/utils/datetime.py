"""Datetime utilities for consistent timezone handling.

SQLite strips timezone info from stored datetimes. These helpers ensure
API responses always include UTC timezone, preventing misinterpretation
by clients in non-UTC timezones.
"""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BeforeValidator


def _ensure_utc(v: datetime) -> datetime:
    """Add UTC tzinfo to naive datetimes (SQLite read-back fix)."""
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


UTCDatetime = Annotated[datetime, BeforeValidator(_ensure_utc)]
"""Pydantic-annotated datetime that normalizes naive values to UTC."""
