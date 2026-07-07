import redis.asyncio as aioredis
from src.core.settings import get_settings


settings = get_settings()

def create_redis_async_client(force_no_auth: bool = False) -> aioredis.Redis:
    if not force_no_auth and settings.redis_url.strip():
        redis_url = settings.redis_url.strip()
    else:
        redis_url = f"redis://{settings.redis_host}:{settings.redis_port}/0"

    return aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
    )

