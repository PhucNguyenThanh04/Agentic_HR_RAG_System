from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatboxPaths:
    CHAT_MESSAGE = "/api/v1/chat/message"
    CHAT_MESSAGE_STREAM = "/api/v1/chat/message/stream"
    DOCUMENTS = "/api/v1/rag/documents"
    DOCUMENT_VECTORS = "/api/v1/rag/documents/{document_id}/vectors"


class ChatHistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    employee_id: str
    user_role: str = Field(..., min_length=1)
    conversation_id: str = Field(..., min_length=1)
    chat_history: list[ChatHistoryTurn] = Field(default_factory=list)


class ChatCitation(BaseModel):
    index: int
    chunk_id: str
    document_id: str | None = None
    filename: str
    page: int | None = None
    section: str | None = None
    clause_number: str | None = None
    score: float
    file_path: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)
    low_confidence: bool = False
    used_context: bool = False
    ask_user: bool = False
    options: list[str] = Field(default_factory=list)
    allow_free_text: bool = True
    finish_reason: Literal["answer", "ask_user", "max_steps", "error"] = "answer"
    error_code: str | None = None


class DocumentIngestResponse(BaseModel):
    document_id: str
    filename: str
    collection: str
    status: Literal["ready", "failed", "processing"]
    chunks_count: int
    vector_indexed: bool
    keyword_indexed: bool
    error_code: str | None = None
    message: str | None = None


class DocumentVectorDeleteResponse(BaseModel):
    document_id: str
    collection: str
    status: Literal["deleted"]
    deleted: bool
    message: str
