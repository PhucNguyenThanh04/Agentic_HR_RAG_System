from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import ChatMessageRole


class ConversationBase(AppTimezoneModel):
    employee_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized


class ConversationCreate(ConversationBase):
    pass


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized


class ConversationRead(ConversationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ConversationListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    employee_id: uuid.UUID | None = None
    search: str | None = Field(default=None, min_length=1, max_length=120)
    created_from: datetime | None = None
    created_to: datetime | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "ConversationListQuery":
        if self.created_from and self.created_to and self.created_to < self.created_from:
            raise ValueError("created_to must be on/after created_from")
        return self


class ChatMessageBase(AppTimezoneModel):
    conversation_id: uuid.UUID
    role: ChatMessageRole
    content: str = Field(..., min_length=1)
    citations: list[dict[str, Any]] | None = None
    ask_user: bool = False
    options: list[str | dict[str, Any]] | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_ask_user_options(self) -> "ChatMessageBase":
        if self.options and not self.ask_user:
            raise ValueError("options can only be set when ask_user=True")
        return self


class ChatMessageCreate(ChatMessageBase):
    pass


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank")
        return normalized


class ChatMessageUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    citations: list[dict[str, Any]] | None = None
    ask_user: bool | None = None
    options: list[str | dict[str, Any]] | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_ask_user_options(self) -> "ChatMessageUpdate":
        if self.options and self.ask_user is False:
            raise ValueError("options can only be set when ask_user=True")
        return self


class ChatMessageRead(ChatMessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class SendMessageResponse(BaseModel):
    answer: str
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    citations: list[dict[str, Any]] = Field(default_factory=list)
    low_confidence: bool = False
    used_context: bool = False
    ask_user: bool = False
    options: list[str] = Field(default_factory=list)
    allow_free_text: bool = True
    finish_reason: str
    error_code: str | None = None


class NewMessageResponse(SendMessageResponse):
    conversation: ConversationRead


class ChatMessageListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    conversation_id: uuid.UUID | None = None
    role: ChatMessageRole | None = None
    ask_user: bool | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "ChatMessageListQuery":
        if self.created_from and self.created_to and self.created_to < self.created_from:
            raise ValueError("created_to must be on/after created_from")
        return self


class ConversationWithMessagesRead(ConversationRead):
    messages: list[ChatMessageRead] = Field(default_factory=list)
