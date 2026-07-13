from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from src.tools.ask_user_tool import AskUserTool
from src.tools.base_tool import ToolCitation, ToolOutcome, ToolResult
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

TOOL_RUNTIME_ERROR_OBSERVATION = (
    "[Tool error: tool '{action}' failed with runtime error. "
    "Do not repeat the same action without changing input.]"
)


@dataclass
class ExecutionResult:
    observation: str
    outcome: ToolOutcome = "success"
    retryable: bool = False
    is_ask_user: bool = False
    ask_user_payload: dict[str, Any] | None = None
    is_error: bool = False
    citations: list[ToolCitation] = field(default_factory=list)
    used_context: bool = False
    low_confidence: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class Executor:
    """
    Executes tools selected by Supervisor and returns structured results.

    Supervisor owns the loop/state. Executor only knows how to:
    - find a tool in ToolRegistry
    - run the tool
    - normalize tool errors into observations
    - detect ask_user signals
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(
        self,
        action: str,
        action_input: dict[str, Any],
    ) -> ExecutionResult:
        try:
            tool = self.registry.get(action)
        except KeyError:
            available = ", ".join(self.registry.tool_names) or "(không có tool nào)"
            return ExecutionResult(
                observation=(
                    f"Tool '{action}' không tồn tại. "
                    f"Các tool có sẵn: {available}"
                ),
                outcome="error",
                is_error=True,
            )

        try:
            validated_input = self._validate_action_input(tool, action_input)
        except ValidationError as exc:
            return ExecutionResult(
                observation=f"Tham số tool '{action}' không hợp lệ: {exc}",
                outcome="error",
                is_error=True,
            )

        try:
            raw_result = await tool.run(**validated_input)
        except Exception as exc:
            logger.error("Tool '%s' error: %s", action, exc, exc_info=True)
            return ExecutionResult(
                observation=TOOL_RUNTIME_ERROR_OBSERVATION.format(action=action),
                outcome="error",
                is_error=True,
            )

        tool_result = self._normalize_tool_result(raw_result)
        observation = tool_result.observation

        if AskUserTool.is_ask_user(observation):
            try:
                payload = AskUserTool.parse_payload(observation)
            except ValueError:
                logger.warning(
                    "Invalid ask_user payload from tool '%s': %s",
                    action,
                    observation,
                    exc_info=True,
                )
            else:
                return ExecutionResult(
                    observation=observation,
                    outcome=tool_result.outcome,
                    retryable=tool_result.retryable,
                    is_ask_user=True,
                    ask_user_payload=payload,
                    citations=tool_result.citations,
                    used_context=tool_result.used_context,
                    low_confidence=tool_result.low_confidence,
                    metadata=tool_result.metadata,
                )

        return ExecutionResult(
            observation=observation,
            outcome=tool_result.outcome,
            retryable=tool_result.retryable,
            is_error=tool_result.outcome == "error",
            citations=tool_result.citations,
            used_context=tool_result.used_context,
            low_confidence=tool_result.low_confidence,
            metadata=tool_result.metadata,
        )

    @staticmethod
    def _normalize_tool_result(result: ToolResult) -> ToolResult:
        if isinstance(result, ToolResult):
            return result
        logger.error(
            "Tool returned unsupported result type: %s",
            type(result).__name__,
        )
        return ToolResult(
            observation="[Tool error: tool returned an invalid result type.]",
            outcome="error",
            retryable=False,
            metadata={"invalid_result_type": type(result).__name__},
        )

    @staticmethod
    def _validate_action_input(tool: Any, action_input: dict[str, Any]) -> dict[str, Any]:
        if tool.args_schema is None:
            return action_input

        args = tool.args_schema.model_validate(action_input or {})
        return args.model_dump(exclude_none=True)
