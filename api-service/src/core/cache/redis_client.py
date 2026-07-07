import redis.asyncio as aioredis
from src.core.configs.settings import settings


def create_redis_async_client(force_no_auth: bool = False) -> aioredis.Redis:
    if force_no_auth:
        redis_url = (
            f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db_session}"
        )
    elif settings.redis_url.strip():
        redis_url = settings.redis_url.strip()
    else:
        redis_url = settings.redis_session_url

    return aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
