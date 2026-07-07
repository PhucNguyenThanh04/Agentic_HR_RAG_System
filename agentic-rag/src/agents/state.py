from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from src.features.chat.schemas import ChatHistoryTurn
from src.tools.base_tool import ToolCitation

@dataclass
class AgentStep:
    thought: str
    action: str                     # tên tool: "vector_search", "employee_query", "ask_user", ...
    action_input: dict[str, Any]    # params truyền vào tool.run(**action_input)
    observation: str                # kết quả tool trả về — Supervisor append vào prompt loop kế tiếp
    is_error: bool = False
    citations: list[ToolCitation] = field(default_factory=list)
    used_context: bool = False
    low_confidence: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_pending_dict(self) -> dict[str, Any]:
        return {
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "is_error": self.is_error,
            "citations": [
                {
                    "index": citation.index,
                    "chunk_id": citation.chunk_id,
                    "filename": citation.filename,
                    "score": citation.score,
                    "document_id": citation.document_id,
                    "page": citation.page,
                    "section": citation.section,
                    "clause_number": citation.clause_number,
                    "file_path": citation.file_path,
                }
                for citation in self.citations
            ],
            "used_context": self.used_context,
            "low_confidence": self.low_confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_pending_dict(cls, data: dict[str, Any]) -> "AgentStep":
        citations = [
            ToolCitation(
                index=int(item["index"]),
                chunk_id=str(item["chunk_id"]),
                filename=str(item["filename"]),
                score=float(item["score"]),
                document_id=item.get("document_id"),
                page=item.get("page"),
                section=item.get("section"),
                clause_number=item.get("clause_number"),
                file_path=item.get("file_path"),
            )
            for item in data.get("citations", [])
            if isinstance(item, dict)
        ]
        return cls(
            thought=str(data.get("thought") or ""),
            action=str(data["action"]),
            action_input=dict(data.get("action_input") or {}),
            observation=str(data.get("observation") or ""),
            is_error=bool(data.get("is_error", False)),
            citations=citations,
            used_context=bool(data.get("used_context", False)),
            low_confidence=bool(data.get("low_confidence", False)),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class AgentState:

    # ── Input (không đổi trong suốt loop) ──
    user_message: str
    employee_id: str
    user_role: str
    chat_history: list[ChatHistoryTurn] = field(default_factory=list)

    # ── Accumulator (cập nhật mỗi iteration) ──
    steps: list[AgentStep] = field(default_factory=list)

    # ── Output (set khi loop kết thúc) ──
    final_answer: str = ""
    finish_reason: Literal["answer", "ask_user", "max_steps", "error"] = "answer"
    is_done: bool = False

    # ── ask_user payload (nếu finish_reason == "ask_user") ──
    ask_user_payload: dict[str, Any] | None = None

    def add_step(self, step: AgentStep) -> None:
        self.steps.append(step)

    def finish_with_answer(self, answer: str) -> None:
        self.final_answer = answer
        self.finish_reason = "answer"
        self.is_done = True

    def finish_with_ask_user(self, payload: dict[str, Any]) -> None:
        self.final_answer = payload.get("question", "")
        self.ask_user_payload = payload
        self.finish_reason = "ask_user"
        self.is_done = True

    def finish_with_error(self, error_message: str) -> None:
        self.final_answer = error_message
        self.finish_reason = "error"
        self.is_done = True

    def finish_max_steps(self) -> None:
        self.final_answer = (
            "Tôi đã thử nhiều cách nhưng chưa tìm được câu trả lời phù hợp. "
            "Bạn vui lòng đặt lại câu hỏi cụ thể hơn."
        )
        self.finish_reason = "max_steps"
        self.is_done = True

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def to_pending_dict(self) -> dict[str, Any]:
        return {
            "user_message": self.user_message,
            "employee_id": self.employee_id,
            "user_role": self.user_role,
            "chat_history": [
                turn.model_dump(mode="json")
                for turn in self.chat_history
            ],
            "steps": [step.to_pending_dict() for step in self.steps],
        }

    @classmethod
    def from_pending_dict(cls, data: dict[str, Any]) -> "AgentState":
        state = cls(
            user_message=str(data["user_message"]),
            employee_id=str(data["employee_id"]),
            user_role=str(data["user_role"]),
            chat_history=[
                ChatHistoryTurn.model_validate(item)
                for item in data.get("chat_history", [])
            ],
        )
        state.steps = [
            AgentStep.from_pending_dict(item)
            for item in data.get("steps", [])
            if isinstance(item, dict)
        ]
        state.is_done = False
        state.finish_reason = "answer"
        state.final_answer = ""
        state.ask_user_payload = None
        return state

    def resume_from_ask_user_answer(self, user_answer: str) -> None:
        answer = user_answer.strip()
        for step in reversed(self.steps):
            if step.action == "ask_user":
                step.observation = f"Người dùng trả lời: {answer}"
                return
        raise ValueError("Pending state does not contain an ask_user step")
