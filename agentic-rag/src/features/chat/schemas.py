from typing import Literal

from pydantic import BaseModel, Field


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
    ask_user: bool = False                  # signal cho frontend
    options: list[str] = Field(default_factory=list)
    allow_free_text: bool = True
    finish_reason: Literal["answer", "ask_user", "max_steps", "error"] = "answer"
    error_code: str | None = None
