from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

PENDING_TTL_SECONDS = 30 * 60


class AgentPendingStore:
    def __init__(
        self,
        redis_client: Redis,
        ttl_seconds: int = PENDING_TTL_SECONDS,
    ) -> None:
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def key(conversation_id: str) -> str:
        return f"agent:pending:{conversation_id}"

    async def get_pending(self, conversation_id: str) -> dict[str, Any] | None:
        try:
            raw = await self.redis.get(self.key(conversation_id))
        except Exception:
            logger.warning(
                "Failed to read agent pending state from Redis: conversation_id=%s",
                conversation_id,
                exc_info=True,
            )
            return None

        if raw is None:
            return None

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            logger.warning(
                "Invalid JSON in agent pending state: conversation_id=%s",
                conversation_id,
                exc_info=True,
            )
            await self.delete_pending(conversation_id)
            return None

        if not isinstance(payload, dict):
            logger.warning(
                "Invalid agent pending state type: conversation_id=%s type=%s",
                conversation_id,
                type(payload).__name__,
            )
            await self.delete_pending(conversation_id)
            return None

        return payload

    async def save_pending(
        self,
        conversation_id: str,
        data: dict[str, Any],
    ) -> None:
        encoded = json.dumps(data, ensure_ascii=False, default=str)
        await self.redis.set(
            self.key(conversation_id),
            encoded,
            ex=self.ttl_seconds,
        )

    async def delete_pending(self, conversation_id: str) -> None:
        try:
            await self.redis.delete(self.key(conversation_id))
        except Exception:
            logger.warning(
                "Failed to delete agent pending state from Redis: conversation_id=%s",
                conversation_id,
                exc_info=True,
            )
