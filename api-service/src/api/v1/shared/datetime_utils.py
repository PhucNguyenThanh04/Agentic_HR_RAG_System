from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import BaseModel, field_serializer

BASE_DIR = Path(__file__).resolve().parents[4]
DEFAULT_APP_TIMEZONE = "Asia/Ho_Chi_Minh"


@lru_cache
def get_app_timezone() -> ZoneInfo:
    load_dotenv(BASE_DIR / ".env")
    return ZoneInfo(os.getenv("DATABASE_TIMEZONE", DEFAULT_APP_TIMEZONE))


def to_app_timezone(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(get_app_timezone())


class AppTimezoneModel(BaseModel):
    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_datetime_fields(self, value):
        if isinstance(value, datetime):
            return to_app_timezone(value).isoformat()
        return value
