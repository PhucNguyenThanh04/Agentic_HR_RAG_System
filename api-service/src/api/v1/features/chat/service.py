from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from fastapi import Depends
from pydantic import ValidationError
from redis.asyncio import Redis

from src.api.v1.features.chat import schemas
from src.api.v1.features.chat.models import ChatMessage, Conversation
from src.api.v1.features.chat.repository import (
    ConversationRepository,
    get_conversation_repository,
)
from src.api.v1.features.staff.models import Employee
from src.api.v1.features.users.models import User
from src.core.clients.chatbox.client import ChatboxClient
from src.core.clients.chatbox.schemas import ChatHistoryTurn, ChatRequest
from src.core.dependencies.dep import get_chatbox_http_client, get_redis_client
from src.core.exceptions import MLProcessingException
from src.utils.setup_logger import setup_logger

CHAT_HISTORY_WINDOW_MESSAGES = 6
CHAT_HISTORY_TTL_SECONDS = 60 * 60
DEFAULT_CONVERSATION_TITLE = "Đoạn chat mới"

logger = setup_logger(__name__)


class ConversationService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        redis_client: Redis,
        chatbox_client: ChatboxClient,
    ) -> None:
        self.conversation_repository = conversation_repository
        self.redis = redis_client
        self.chatbox_client = chatbox_client

    @staticmethod
    def _to_read(conversation: Conversation) -> schemas.ConversationRead:
        return schemas.ConversationRead.model_validate(conversation)

    @staticmethod
    def _message_to_read(message: ChatMessage) -> schemas.ChatMessageRead:
        return schemas.ChatMessageRead.model_validate(message)

    @staticmethod
    def _title_from_message(message: str) -> str:
        title = " ".join(message.split())
        if len(title) <= 80:
            return title
        return f"{title[:77].rstrip()}..."

    async def create_conversation(
        self,
        *,
        payload: schemas.ConversationCreateRequest,
        current_employee: Employee,
    ) -> schemas.ConversationRead:
        title = payload.title or DEFAULT_CONVERSATION_TITLE
        conversation = await self.conversation_repository.create_conversation(
            employee_id=current_employee.employee_id,
            title=title,
        )
        return self._to_read(conversation)

    async def list_conversations(
        self,
        *,
        current_employee: Employee,
    ) -> list[schemas.ConversationRead]:
        conversations = await self.conversation_repository.list_conversations(
            employee_id=current_employee.employee_id,
        )
        return [self._to_read(conversation) for conversation in conversations]

    async def list_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        current_employee: Employee,
    ) -> list[schemas.ChatMessageRead]:
        await self.conversation_repository.get_conversation_for_employee(
            conversation_id=conversation_id,
            employee_id=current_employee.employee_id,
        )
        messages = await self.conversation_repository.list_messages(
            conversation_id=conversation_id,
        )
        return [self._message_to_read(message) for message in messages]

    async def delete_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        current_employee: Employee,
    ) -> None:
        await self.conversation_repository.get_conversation_for_employee(
            conversation_id=conversation_id,
            employee_id=current_employee.employee_id,
        )
        await self.conversation_repository.delete_conversation(
            conversation_id=conversation_id,
        )
        try:
            await self.redis.delete(self._history_key(conversation_id))
        except Exception:
            logger.warning(
                "Failed to delete conversation short-term history: conversation_id=%s",
                conversation_id,
                exc_info=True,
            )

    async def send_message(
        self,
        *,
        conversation_id: uuid.UUID,
        payload: schemas.SendMessageRequest,
        current_employee: Employee,
        current_user: User,
    ) -> schemas.SendMessageResponse:
        conversation = await self.conversation_repository.get_conversation_for_employee(
            conversation_id=conversation_id,
            employee_id=current_employee.employee_id,
        )
        chat_history = await self._get_short_term_history(conversation_id)
        try:
            rag_response = await self.chatbox_client.chat(
                ChatRequest(
                    message=payload.message,
                    employee_id=str(current_employee.employee_id),
                    user_role=current_user.role_name.value,
                    conversation_id=str(conversation_id),
                    chat_history=chat_history,
                )
            )
        except httpx.HTTPError as exc:
            raise MLProcessingException(
                step="rag_chat",
                reason=str(exc),
                task_id=str(conversation_id),
            ) from exc
        except ValidationError as exc:
            raise MLProcessingException(
                step="rag_chat_response",
                reason=str(exc),
                task_id=str(conversation_id),
            ) from exc

        citations = [
            citation.model_dump(mode="json")
            for citation in rag_response.citations
        ]
        user_message, assistant_message = await self.conversation_repository.create_chat_exchange(
            conversation_id=conversation_id,
            user_content=payload.message,
            assistant_content=rag_response.answer,
            citations=citations,
            ask_user=rag_response.ask_user,
            options=list(rag_response.options or []),
            title_if_empty=(
                self._title_from_message(payload.message)
                if conversation.title == DEFAULT_CONVERSATION_TITLE
                else None
            ),
            replace_title=DEFAULT_CONVERSATION_TITLE,
        )
        await self._append_short_term_history_safely(
            conversation_id=conversation_id,
            user_content=payload.message,
            assistant_content=rag_response.answer,
        )
        return schemas.SendMessageResponse(
            answer=rag_response.answer,
            user_message=self._message_to_read(user_message),
            assistant_message=self._message_to_read(assistant_message),
            citations=citations,
            low_confidence=rag_response.low_confidence,
            used_context=rag_response.used_context,
            ask_user=rag_response.ask_user,
            options=list(rag_response.options or []),
            allow_free_text=rag_response.allow_free_text,
            finish_reason=rag_response.finish_reason,
            error_code=rag_response.error_code,
        )

    async def send_message_stream(
        self,
        *,
        conversation_id: uuid.UUID,
        payload: schemas.SendMessageRequest,
        current_employee: Employee,
        current_user: User,
    ) -> AsyncGenerator[str, None]:
        conversation = await self.conversation_repository.get_conversation_for_employee(
            conversation_id=conversation_id,
            employee_id=current_employee.employee_id,
        )
        chat_history = await self._get_short_term_history(conversation_id)
        request = ChatRequest(
            message=payload.message,
            employee_id=str(current_employee.employee_id),
            user_role=current_user.role_name.value,
            conversation_id=str(conversation_id),
            chat_history=chat_history,
        )

        async def event_stream() -> AsyncGenerator[str, None]:
            answer_parts: list[str] = []
            latest_final: dict[str, Any] | None = None

            try:
                async for event, event_payload in self.chatbox_client.chat_stream(request):
                    if event == "delta":
                        text = str(event_payload.get("text") or "")
                        if text:
                            answer_parts.append(text)
                        yield _format_sse(event, event_payload)
                        continue

                    if event == "status":
                        yield _format_sse(event, event_payload)
                        continue

                    if event == "error":
                        yield _format_sse(event, event_payload)
                        return

                    if event != "final":
                        continue

                    latest_final = dict(event_payload)
                    answer = "".join(answer_parts).strip()
                    if not answer:
                        answer = str(latest_final.get("answer") or "").strip()
                    if not answer:
                        yield _format_sse(
                            "error",
                            {
                                "error_code": "EMPTY_STREAM_ANSWER",
                                "message": "Chatbot không trả nội dung để lưu.",
                            },
                        )
                        return

                    citations = list(latest_final.get("citations") or [])
                    ask_user = bool(latest_final.get("ask_user", False))
                    options = list(latest_final.get("options") or [])

                    user_message, assistant_message = (
                        await self.conversation_repository.create_chat_exchange(
                            conversation_id=conversation_id,
                            user_content=payload.message,
                            assistant_content=answer,
                            citations=citations,
                            ask_user=ask_user,
                            options=options,
                            title_if_empty=(
                                self._title_from_message(payload.message)
                                if conversation.title == DEFAULT_CONVERSATION_TITLE
                                else None
                            ),
                            replace_title=DEFAULT_CONVERSATION_TITLE,
                        )
                    )
                    await self._append_short_term_history_safely(
                        conversation_id=conversation_id,
                        user_content=payload.message,
                        assistant_content=answer,
                    )

                    latest_final["answer"] = answer
                    latest_final["citations"] = citations
                    latest_final["ask_user"] = ask_user
                    latest_final["options"] = options
                    latest_final["user_message"] = self._message_to_read(
                        user_message
                    ).model_dump(mode="json")
                    latest_final["assistant_message"] = self._message_to_read(
                        assistant_message
                    ).model_dump(mode="json")
                    yield _format_sse("final", latest_final)
                    return

                if latest_final is None:
                    yield _format_sse(
                        "error",
                        {
                            "error_code": "STREAM_ENDED_WITHOUT_FINAL",
                            "message": "Chatbot kết thúc stream nhưng chưa gửi kết quả cuối.",
                        },
                    )
            except httpx.HTTPError as exc:
                logger.exception(
                    "RAG chat stream HTTP error: conversation_id=%s",
                    conversation_id,
                )
                yield _format_sse(
                    "error",
                    {
                        "error_code": "RAG_STREAM_ERROR",
                        "message": str(exc),
                    },
                )
            except Exception as exc:
                logger.exception(
                    "Unhandled chat stream error: conversation_id=%s",
                    conversation_id,
                )
                yield _format_sse(
                    "error",
                    {
                        "error_code": "CHAT_STREAM_ERROR",
                        "message": str(exc),
                    },
                )

        return event_stream()

    async def send_new_message(
        self,
        *,
        payload: schemas.SendMessageRequest,
        current_employee: Employee,
        current_user: User,
    ) -> schemas.NewMessageResponse:
        conversation = await self.create_conversation(
            payload=schemas.ConversationCreateRequest(
                title=self._title_from_message(payload.message),
            ),
            current_employee=current_employee,
        )
        try:
            response = await self.send_message(
                conversation_id=conversation.id,
                payload=payload,
                current_employee=current_employee,
                current_user=current_user,
            )
        except Exception:
            try:
                await self.delete_conversation(
                    conversation_id=conversation.id,
                    current_employee=current_employee,
                )
            except Exception:
                logger.warning(
                    "Failed to clean up new conversation after chat failure: "
                    "conversation_id=%s",
                    conversation.id,
                    exc_info=True,
                )
            raise

        return schemas.NewMessageResponse(
            conversation=conversation,
            **response.model_dump(),
        )

    @staticmethod
    def _history_key(conversation_id: uuid.UUID) -> str:
        return f"chat:history:{conversation_id}"

    async def _get_short_term_history(
        self,
        conversation_id: uuid.UUID,
    ) -> list[ChatHistoryTurn]:
        key = self._history_key(conversation_id)
        cached_items = []
        try:
            cached_items = await self.redis.lrange(key, 0, -1)
        except Exception:
            logger.warning(
                "Failed to read short-term chat history from Redis: "
                "conversation_id=%s",
                conversation_id,
                exc_info=True,
            )
        if cached_items:
            history: list[ChatHistoryTurn] = []
            for item in cached_items[-CHAT_HISTORY_WINDOW_MESSAGES:]:
                try:
                    payload = json.loads(item)
                    history.append(ChatHistoryTurn.model_validate(payload))
                except (TypeError, ValueError):
                    continue
            if history:
                return history

        messages = await self.conversation_repository.list_recent_messages(
            conversation_id=conversation_id,
            limit=CHAT_HISTORY_WINDOW_MESSAGES,
        )
        history = [
            ChatHistoryTurn(role=message.role.value, content=message.content)
            for message in messages
        ]
        if history:
            try:
                await self.redis.delete(key)
                await self.redis.rpush(
                    key,
                    *[
                        json.dumps(turn.model_dump(mode="json"), ensure_ascii=False)
                        for turn in history
                    ],
                )
                await self.redis.expire(key, CHAT_HISTORY_TTL_SECONDS)
            except Exception:
                logger.warning(
                    "Failed to warm short-term chat history in Redis: "
                    "conversation_id=%s",
                    conversation_id,
                    exc_info=True,
                )
        return history

    async def _append_short_term_history_safely(
        self,
        *,
        conversation_id: uuid.UUID,
        user_content: str,
        assistant_content: str,
    ) -> None:
        try:
            await self._append_short_term_history(
                conversation_id=conversation_id,
                user_content=user_content,
                assistant_content=assistant_content,
            )
        except Exception:
            logger.warning(
                "Failed to append short-term chat history in Redis: "
                "conversation_id=%s",
                conversation_id,
                exc_info=True,
            )

    async def _append_short_term_history(
        self,
        *,
        conversation_id: uuid.UUID,
        user_content: str,
        assistant_content: str,
    ) -> None:
        key = self._history_key(conversation_id)
        turns = [
            ChatHistoryTurn(role="user", content=user_content),
            ChatHistoryTurn(role="assistant", content=assistant_content),
        ]
        await self.redis.rpush(
            key,
            *[
                json.dumps(turn.model_dump(mode="json"), ensure_ascii=False)
                for turn in turns
            ],
        )
        await self.redis.ltrim(key, -CHAT_HISTORY_WINDOW_MESSAGES, -1)
        await self.redis.expire(key, CHAT_HISTORY_TTL_SECONDS)


def _format_sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {data}\n\n"


def get_conversation_service(
    conversation_repository: ConversationRepository = Depends(get_conversation_repository),
    redis_client: Redis = Depends(get_redis_client),
    chatbox_http_client: httpx.AsyncClient = Depends(get_chatbox_http_client),
) -> ConversationService:
    return ConversationService(
        conversation_repository=conversation_repository,
        redis_client=redis_client,
        chatbox_client=ChatboxClient(chatbox_http_client),
    )
