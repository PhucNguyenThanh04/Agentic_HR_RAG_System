from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.features.chat.models import ChatMessage, Conversation
from src.api.v1.shared.enums import ChatMessageRole
from src.core.db.database import get_db
from src.core.exceptions import DatabaseException, NotFoundException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_conversation(
        self,
        *,
        employee_id: uuid.UUID,
        title: str,
    ) -> Conversation:
        conversation = Conversation(
            employee_id=employee_id,
            title=title.strip(),
        )
        self.db.add(conversation)
        try:
            await self.db.commit()
            await self.db.refresh(conversation)
            return conversation
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create conversation: employee_id=%s title=%s",
                employee_id,
                title,
            )
            raise DatabaseException("Failed to create conversation") from exc

    async def list_conversations(
        self,
        *,
        employee_id: uuid.UUID,
        limit: int = 50,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.employee_id == employee_id)
            .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
            .limit(limit)
        )
        try:
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as exc:
            logger.exception(
                "Failed to list conversations: employee_id=%s",
                employee_id,
            )
            raise DatabaseException("Failed to list conversations") from exc

    async def list_recent_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 6,
    ) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        try:
            result = await self.db.execute(stmt)
            return list(reversed(result.scalars().all()))
        except Exception as exc:
            logger.exception(
                "Failed to list recent messages: conversation_id=%s",
                conversation_id,
            )
            raise DatabaseException("Failed to list recent chat messages") from exc

    async def create_chat_exchange(
        self,
        *,
        conversation_id: uuid.UUID,
        user_content: str,
        assistant_content: str,
        citations: list[dict] | None,
        ask_user: bool,
        options: list | None,
        title_if_empty: str | None = None,
        replace_title: str | None = None,
    ) -> tuple[ChatMessage, ChatMessage]:
        user_message = ChatMessage(
            conversation_id=conversation_id,
            role=ChatMessageRole.user,
            content=user_content,
        )
        assistant_message = ChatMessage(
            conversation_id=conversation_id,
            role=ChatMessageRole.assistant,
            content=assistant_content,
            citations=citations,
            ask_user=ask_user,
            options=options,
        )
        conversation = await self.get_conversation_by_id(conversation_id)
        if conversation is None:
            raise NotFoundException("Conversation")
        if title_if_empty and (
            replace_title is None or conversation.title == replace_title
        ):
            existing_message_id = await self.db.scalar(
                select(ChatMessage.id)
                .where(ChatMessage.conversation_id == conversation_id)
                .limit(1)
            )
            if existing_message_id is None:
                conversation.title = title_if_empty
        conversation.updated_at = func.now()
        self.db.add(user_message)
        self.db.add(assistant_message)
        try:
            await self.db.commit()
            await self.db.refresh(user_message)
            await self.db.refresh(assistant_message)
            return user_message, assistant_message
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create chat exchange: conversation_id=%s",
                conversation_id,
            )
            raise DatabaseException("Failed to create chat messages") from exc

    async def get_conversation_by_id(
        self,
        conversation_id: uuid.UUID,
    ) -> Conversation | None:
        try:
            return await self.db.scalar(
                select(Conversation).where(Conversation.id == conversation_id)
            )
        except Exception as exc:
            logger.exception(
                "Failed to get conversation: conversation_id=%s",
                conversation_id,
            )
            raise DatabaseException("Failed to get conversation") from exc

    async def get_conversation_for_employee(
        self,
        *,
        conversation_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> Conversation:
        try:
            conversation = await self.db.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.employee_id == employee_id,
                )
            )
        except Exception as exc:
            logger.exception(
                "Failed to get conversation for employee: "
                "conversation_id=%s employee_id=%s",
                conversation_id,
                employee_id,
            )
            raise DatabaseException("Failed to get conversation") from exc
        if conversation is None:
            raise NotFoundException("Conversation")
        return conversation

    async def list_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int = 200,
    ) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        try:
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as exc:
            logger.exception(
                "Failed to list messages: conversation_id=%s",
                conversation_id,
            )
            raise DatabaseException("Failed to list chat messages") from exc

    async def delete_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
    ) -> None:
        stmt = delete(Conversation).where(Conversation.id == conversation_id)
        try:
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to delete conversation: conversation_id=%s",
                conversation_id,
            )
            raise DatabaseException("Failed to delete conversation") from exc


def get_conversation_repository(
    db: AsyncSession = Depends(get_db),
) -> ConversationRepository:
    return ConversationRepository(db)
