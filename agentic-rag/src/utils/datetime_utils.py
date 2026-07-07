from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import BaseModel, field_serializer

def _find_project_root() -> Path:
    """Tìm thư mục gốc dự án (chứa run.py). Hoạt động cả local và Docker."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "run.py").exists():
            return parent
    # Fallback: trong Docker WORKDIR=/app
    return Path("/app")


BASE_DIR = _find_project_root()
DEFAULT_APP_TIMEZONE = "Asia/Ho_Chi_Minh"


@lru_cache
def get_app_timezone() -> ZoneInfo:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
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
