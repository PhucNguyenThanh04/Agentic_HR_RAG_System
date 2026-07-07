from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from src.rag.retrieval.schemas import ToolCitation


@dataclass
class ToolResult:
    observation: str
    citations: list[ToolCitation] = field(default_factory=list)
    used_context: bool = False
    low_confidence: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    name: str
    description: str  # LLM đọc cái này để biết chọn tool nào
    args_schema: type[BaseModel] | None = None
    usage_hint: str = ""          # Mô tả ngắn gọn cho LLM prompt (fallback về description)
    input_example: str = "{}"     # Ví dụ action_input cho LLM prompt

    @abstractmethod
    async def run(self, **kwargs) -> str | ToolResult:
        """
        Thực thi tool và trả về observation string hoặc ToolResult có metadata.
        """
        pass

    def to_dict(self) -> dict:
        """Mô tả tool cho LLM đọc trong prompt."""
        tool = {
            "name": self.name,
            "description": self.description,
        }
        if self.args_schema is not None:
            tool["input_schema"] = self.args_schema.model_json_schema()
        return tool
