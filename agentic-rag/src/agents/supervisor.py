from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from datetime import date
from time import perf_counter
from typing import Any

from src.agents.executor import Executor
from src.agents.pending_store import AgentPendingStore
from src.agents.state import AgentState, AgentStep
from src.core.settings import get_settings
from src.features.chat.schemas import ChatRequest
from src.integrations.llm.client import GeminiClient, LLMError, LLMTruncatedError
from src.integrations.llm.prompts import FINAL_ANSWER_SYSTEM_PROMPT, PromptBuilder
from src.observability.agent_logs import (
    log_agent_finish,
    log_agent_start,
    log_agent_step,
    log_agent_tool_dispatch,
    log_agent_tool_result,
)
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_ASK_USER_COUNT = 2

AgentStreamEvent = tuple[str, dict[str, Any]]

TOOL_STATUS_MESSAGES = {
    "vector_search": "Đang tìm tài liệu liên quan...",
    "employee_query": "Đang kiểm tra thông tin nhân viên...",
    "shift_query": "Đang kiểm tra thông tin ca làm...",
    "attendance_query": "Đang kiểm tra dữ liệu chấm công...",
    "ask_user": "Cần thêm một chút thông tin...",
}


class Supervisor:
    """
    Coordinates the ReAct loop for one chat request.

    Supervisor owns state and loop control. The caller owns tool composition.
    Executor owns tool execution details.
    """

    def __init__(
        self,
        llm_client: GeminiClient,
        pending_store: AgentPendingStore | None = None,
        max_steps: int | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        settings = get_settings() if max_steps is None or prompt_builder is None else None
        self.llm_client = llm_client
        self.pending_store = pending_store
        self.max_steps = max_steps if max_steps is not None else settings.agent_max_steps
        self.prompt_builder = (
            prompt_builder
            if prompt_builder is not None
            else PromptBuilder.from_settings(settings)
        )

    async def run(
        self,
        request: ChatRequest,
        registry: ToolRegistry,
    ) -> AgentState:
        request_started_at = perf_counter()
        state, resumed_pending = await self._build_initial_state(request)
        initial_step_count = state.step_count

        executor = Executor(registry)
        system_prompt = PromptBuilder.build_system_prompt(
            tool_descriptions=registry.build_tools_prompt(),
            current_date=date.today().isoformat(),
        )

        log_agent_start(
            conversation_id=request.conversation_id,
            message=request.message,
            history_len=len(request.chat_history),
            has_pending=resumed_pending,
        )
        logger.info(
            "Supervisor started | employee_id=%s user_role=%s chat_history_count=%d message=%s",
            request.employee_id,
            request.user_role,
            len(request.chat_history),
            request.message[:80],
        )

        while not state.is_done and state.step_count < self.max_steps:
            try:
                parsed = await self._call_llm(state, system_prompt)
            except LLMTruncatedError as exc:
                logger.warning("LLM output truncated, retrying with concise hint: %s", exc)
                state.add_step(AgentStep(
                    thought="(output bị cắt do quá dài)",
                    action="_system_retry",
                    action_input={},
                    observation=(
                        "⚠️ Output trước bị cắt vì quá dài. "
                        "Hãy giữ thought dưới 2 câu và trả lời ngay bằng final_answer."
                    ),
                    is_error=True,
                ))
                continue
            except (LLMError, json.JSONDecodeError, ValueError) as exc:
                logger.error("LLM error in supervisor loop: %s", exc)
                state.finish_with_error(
                    "Xin lỗi, tôi gặp lỗi khi xử lý yêu cầu. "
                    "Bạn vui lòng thử lại."
                )
                break

            thought = str(parsed.get("thought", ""))
            action = str(parsed.get("action", ""))
            action_input = parsed.get("action_input", {})
            if not isinstance(action_input, dict):
                logger.warning(
                    "Invalid action_input type from LLM | action=%s type=%s",
                    action,
                    type(action_input).__name__,
                )
                action_input = {}

            if action == "ask_user" and self._ask_user_count(state) >= MAX_ASK_USER_COUNT:
                logger.warning(
                    "Max ask_user count reached | conversation_id=%s count=%d",
                    request.conversation_id,
                    self._ask_user_count(state),
                )
                state.finish_with_error("Không đủ thông tin để trả lời.")
                break

            if action == "final_answer":
                state.add_step(
                    AgentStep(
                        thought=thought,
                        action=action,
                        action_input=action_input,
                        observation="",
                    )
                )
                self._log_step(state, state.steps[-1])
                answer = str(action_input.get("answer") or thought or "")
                if not action_input.get("answer"):
                    logger.warning("final_answer action missing answer field")
                state.finish_with_answer(answer)
                break

            next_step = state.step_count + 1
            log_agent_tool_dispatch(
                step=next_step,
                tool_name=action,
                tool_input=action_input,
            )
            result = await executor.execute(action, action_input)
            log_agent_tool_result(
                step=next_step,
                tool_name=action,
                success=not result.is_error,
                result_preview=result.observation,
                used_context=result.used_context,
                low_confidence=result.low_confidence,
                is_ask_user=result.is_ask_user,
            )
            state.add_step(
                AgentStep(
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=result.observation,
                    is_error=result.is_error,
                    citations=result.citations,
                    used_context=result.used_context,
                    low_confidence=result.low_confidence,
                    metadata=result.metadata,
                )
            )
            self._log_step(state, state.steps[-1])

            if result.is_ask_user:
                state.finish_with_ask_user(result.ask_user_payload or {})
                break

        if not state.is_done:
            state.finish_max_steps()
            logger.warning(
                "Supervisor max steps reached | employee_id=%s actions=%s message=%s",
                request.employee_id,
                [step.action for step in state.steps],
                request.message[:80],
            )

        await self._sync_pending_state(request.conversation_id, state)

        elapsed_seconds = perf_counter() - request_started_at
        logger.info(
            "Supervisor finished | reason=%s steps_this_request=%d "
            "total_steps=%d elapsed_seconds=%.3f",
            state.finish_reason,
            state.step_count - initial_step_count,
            state.step_count,
            elapsed_seconds,
        )
        log_agent_finish(
            conversation_id=request.conversation_id,
            total_steps=state.step_count,
            steps_this_request=state.step_count - initial_step_count,
            finish_reason=state.finish_reason,
            used_tools=[
                step.action
                for step in state.steps
                if step.action != "final_answer"
            ],
            answer_preview=state.final_answer,
            elapsed_seconds=elapsed_seconds,
        )
        return state

    async def stream(
        self,
        request: ChatRequest,
        registry: ToolRegistry,
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        request_started_at = perf_counter()
        state, resumed_pending = await self._build_initial_state(request)
        initial_step_count = state.step_count

        executor = Executor(registry)
        system_prompt = PromptBuilder.build_stream_system_prompt(
            tool_descriptions=registry.build_tools_prompt(),
            current_date=date.today().isoformat(),
        )

        log_agent_start(
            conversation_id=request.conversation_id,
            message=request.message,
            history_len=len(request.chat_history),
            has_pending=resumed_pending,
        )
        logger.info(
            "Supervisor stream started | employee_id=%s user_role=%s "
            "chat_history_count=%d message=%s",
            request.employee_id,
            request.user_role,
            len(request.chat_history),
            request.message[:80],
        )
        yield "status", {"message": "Đang phân tích yêu cầu..."}

        stream_error: str | None = None

        while not state.is_done and state.step_count < self.max_steps:
            try:
                parsed = await self._call_llm(state, system_prompt)
            except LLMTruncatedError as exc:
                logger.warning("LLM output truncated in stream, retrying: %s", exc)
                state.add_step(AgentStep(
                    thought="(output bị cắt do quá dài)",
                    action="_system_retry",
                    action_input={},
                    observation=(
                        "⚠️ Output trước bị cắt vì quá dài. "
                        "Hãy giữ thought dưới 2 câu và trả lời ngay bằng final_answer."
                    ),
                    is_error=True,
                ))
                yield "status", {"message": "Đang thử lại..."}
                continue
            except (LLMError, json.JSONDecodeError, ValueError) as exc:
                logger.error("LLM error in supervisor stream loop: %s", exc)
                state.finish_with_error(
                    "Xin lỗi, tôi gặp lỗi khi xử lý yêu cầu. "
                    "Bạn vui lòng thử lại."
                )
                stream_error = "AGENT_ERROR"
                yield "error", {
                    "error_code": stream_error,
                    "message": state.final_answer,
                }
                break

            thought = str(parsed.get("thought", ""))
            action = str(parsed.get("action", ""))
            action_input = parsed.get("action_input", {})
            if not isinstance(action_input, dict):
                logger.warning(
                    "Invalid action_input type from LLM | action=%s type=%s",
                    action,
                    type(action_input).__name__,
                )
                action_input = {}

            if action == "ask_user" and self._ask_user_count(state) >= MAX_ASK_USER_COUNT:
                logger.warning(
                    "Max ask_user count reached | conversation_id=%s count=%d",
                    request.conversation_id,
                    self._ask_user_count(state),
                )
                state.finish_with_error("Không đủ thông tin để trả lời.")
                stream_error = "AGENT_ERROR"
                yield "error", {
                    "error_code": stream_error,
                    "message": state.final_answer,
                }
                break

            if action == "final_answer":
                state.add_step(
                    AgentStep(
                        thought=thought,
                        action=action,
                        action_input=action_input,
                        observation="",
                    )
                )
                self._log_step(state, state.steps[-1])
                yield "status", {"message": "Đang tổng hợp câu trả lời..."}

                direct_answer = str(action_input.get("answer") or "").strip()
                answer_parts: list[str] = []
                if direct_answer:
                    for chunk in self._chunk_text(direct_answer):
                        answer_parts.append(chunk)
                        yield "delta", {"text": chunk}
                else:
                    try:
                        async for chunk in self._stream_final_answer(state):
                            answer_parts.append(chunk)
                            yield "delta", {"text": chunk}
                    except LLMError as exc:
                        logger.error("LLM error while streaming final answer: %s", exc)
                        state.finish_with_error(
                            "Xin lỗi, tôi gặp lỗi khi tổng hợp câu trả lời. "
                            "Bạn vui lòng thử lại."
                        )
                        stream_error = "AGENT_ERROR"
                        yield "error", {
                            "error_code": stream_error,
                            "message": state.final_answer,
                        }
                        break

                answer = "".join(answer_parts).strip()
                if not answer:
                    answer = direct_answer or thought.strip()
                if not answer:
                    answer = "Xin lỗi, tôi chưa tổng hợp được câu trả lời phù hợp."
                state.finish_with_answer(answer)
                break

            next_step = state.step_count + 1
            yield "status", {
                "message": TOOL_STATUS_MESSAGES.get(
                    action,
                    "Đang xử lý yêu cầu...",
                )
            }
            log_agent_tool_dispatch(
                step=next_step,
                tool_name=action,
                tool_input=action_input,
            )
            result = await executor.execute(action, action_input)
            log_agent_tool_result(
                step=next_step,
                tool_name=action,
                success=not result.is_error,
                result_preview=result.observation,
                used_context=result.used_context,
                low_confidence=result.low_confidence,
                is_ask_user=result.is_ask_user,
            )
            state.add_step(
                AgentStep(
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=result.observation,
                    is_error=result.is_error,
                    citations=result.citations,
                    used_context=result.used_context,
                    low_confidence=result.low_confidence,
                    metadata=result.metadata,
                )
            )
            self._log_step(state, state.steps[-1])

            if result.is_ask_user:
                state.finish_with_ask_user(result.ask_user_payload or {})
                break

        if not state.is_done and stream_error is None:
            state.finish_max_steps()
            logger.warning(
                "Supervisor stream max steps reached | employee_id=%s "
                "actions=%s message=%s",
                request.employee_id,
                [step.action for step in state.steps],
                request.message[:80],
            )

        await self._sync_pending_state(request.conversation_id, state)

        elapsed_seconds = perf_counter() - request_started_at
        logger.info(
            "Supervisor stream finished | reason=%s steps_this_request=%d "
            "total_steps=%d elapsed_seconds=%.3f",
            state.finish_reason,
            state.step_count - initial_step_count,
            state.step_count,
            elapsed_seconds,
        )
        log_agent_finish(
            conversation_id=request.conversation_id,
            total_steps=state.step_count,
            steps_this_request=state.step_count - initial_step_count,
            finish_reason=state.finish_reason,
            used_tools=[
                step.action
                for step in state.steps
                if step.action != "final_answer"
            ],
            answer_preview=state.final_answer,
            elapsed_seconds=elapsed_seconds,
        )

        if stream_error is None:
            yield "_final_state", {"state": state}

    async def _build_initial_state(self, request: ChatRequest) -> tuple[AgentState, bool]:
        if self.pending_store is not None:
            pending = await self.pending_store.get_pending(request.conversation_id)
            if pending is not None:
                try:
                    if (
                        str(pending.get("employee_id")) != request.employee_id
                        or str(pending.get("user_role")) != request.user_role
                    ):
                        logger.warning(
                            "Pending state context mismatch | conversation_id=%s",
                            request.conversation_id,
                        )
                        await self.pending_store.delete_pending(request.conversation_id)
                    else:
                        state = AgentState.from_pending_dict(pending)
                        state.resume_from_ask_user_answer(request.message)
                        logger.info(
                            "Supervisor resumed pending state | conversation_id=%s steps=%d",
                            request.conversation_id,
                            state.step_count,
                        )
                        return state, True
                except (KeyError, TypeError, ValueError) as exc:
                    logger.warning(
                        "Invalid pending state, starting a new loop | "
                        "conversation_id=%s error=%s",
                        request.conversation_id,
                        exc,
                    )
                    await self.pending_store.delete_pending(request.conversation_id)

        return (
            AgentState(
                user_message=request.message,
                employee_id=request.employee_id,
                user_role=request.user_role,
                chat_history=list(request.chat_history),
            ),
            False,
        )

    async def _sync_pending_state(
        self,
        conversation_id: str,
        state: AgentState,
    ) -> None:
        if self.pending_store is None:
            return

        if state.finish_reason == "ask_user":
            try:
                await self.pending_store.save_pending(
                    conversation_id,
                    state.to_pending_dict(),
                )
            except Exception as exc:
                logger.error(
                    "Failed to save agent pending state: conversation_id=%s error=%s",
                    conversation_id,
                    exc,
                    exc_info=True,
                )
                await self.pending_store.delete_pending(conversation_id)
                state.finish_with_error(
                    "Xin lỗi, tôi chưa thể lưu trạng thái cần hỏi thêm. "
                    "Bạn vui lòng thử lại."
                )
            return

        await self.pending_store.delete_pending(conversation_id)

    @staticmethod
    def _ask_user_count(state: AgentState) -> int:
        return sum(1 for step in state.steps if step.action == "ask_user")

    async def _call_llm(
        self,
        state: AgentState,
        system_prompt: str,
    ) -> dict[str, Any]:
        scratchpad = self.prompt_builder.build_scratchpad(state.steps)
        user_prompt = self.prompt_builder.build_react_prompt(
            user_message=state.user_message,
            chat_history=state.chat_history,
            scratchpad=scratchpad,
            current_step=state.step_count,
            max_steps=self.max_steps,
        )

        response = await self.llm_client.generate_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )
        raw_output = response.content
        next_step = state.step_count + 1
        try:
            parsed = self._parse_llm_json(raw_output)
        except json.JSONDecodeError:
            log_agent_step(
                step=next_step,
                raw_output=raw_output,
                parsed_action=None,
                parsed_thought=None,
            )
            raise

        if not isinstance(parsed, dict):
            log_agent_step(
                step=next_step,
                raw_output=raw_output,
                parsed_action=None,
                parsed_thought=None,
            )
            raise ValueError(f"Gemini response must be a JSON object: {parsed}")
        if "action" not in parsed:
            log_agent_step(
                step=next_step,
                raw_output=raw_output,
                parsed_action=None,
                parsed_thought=str(parsed.get("thought", "")),
            )
            raise ValueError(f"Gemini response thiếu field 'action': {parsed}")

        log_agent_step(
            step=next_step,
            raw_output=raw_output,
            parsed_action=str(parsed.get("action", "")),
            parsed_thought=str(parsed.get("thought", "")),
        )
        return parsed

    async def _stream_final_answer(
        self,
        state: AgentState,
    ) -> AsyncGenerator[str, None]:
        scratchpad = self.prompt_builder.build_scratchpad(
            [
                step
                for step in state.steps
                if step.action != "final_answer"
            ]
        )
        prompt = self.prompt_builder.build_final_answer_prompt(
            user_message=state.user_message,
            chat_history=state.chat_history,
            scratchpad=scratchpad,
        )

        async for chunk in self.llm_client.generate_stream(
            prompt=prompt,
            system_prompt=FINAL_ANSWER_SYSTEM_PROMPT,
            temperature=0.0,
        ):
            yield chunk

    @staticmethod
    def _parse_llm_json(raw_output: str) -> Any:
        """
        Gemini lite models sometimes return one valid JSON object followed by
        stray text. Keep the first object so tool dispatch can continue, but log
        the trailing payload for diagnosis.
        """
        stripped = raw_output.strip()
        parsed, end_index = json.JSONDecoder().raw_decode(stripped)
        trailing = stripped[end_index:].strip()
        if trailing:
            logger.warning(
                "LLM JSON had trailing content after first object: %s",
                trailing[:300],
            )
        return parsed

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 80) -> list[str]:
        if len(text) <= chunk_size:
            return [text]
        return [
            text[index:index + chunk_size]
            for index in range(0, len(text), chunk_size)
        ]

    @staticmethod
    def _log_step(state: AgentState, step: AgentStep) -> None:
        logger.info(
            "Supervisor step | step=%d action=%s is_error=%s "
            "used_context=%s low_confidence=%s observation_length=%d",
            state.step_count,
            step.action,
            step.is_error,
            step.used_context,
            step.low_confidence,
            len(step.observation or ""),
        )
