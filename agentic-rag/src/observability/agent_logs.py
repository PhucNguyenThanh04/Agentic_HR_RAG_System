import logging
from typing import Any

from src.core.setup_logging import setup_agent_trace_logger

logger = setup_agent_trace_logger()
RAW_OUTPUT_PREVIEW_CHARS = 1200
TOOL_RESULT_PREVIEW_CHARS = 2000


def log_agent_start(conversation_id: str, message: str, history_len: int, has_pending: bool):
    logger.info(
        f"[START] conv={conversation_id[:8]} "
        f"msg='{message[:60]}' "
        f"history={history_len} "
        f"pending={has_pending}"
    )


def log_agent_step(step: int, raw_output: str, parsed_action: str | None, parsed_thought: str | None):
    logger.info(
        f"[STEP {step}] action={parsed_action or 'PARSE_FAIL'} | "
        f"thought='{(parsed_thought or '')[:80]}'"
    )
    logger.info(f"[STEP {step}] RAW_OUTPUT='{raw_output[:RAW_OUTPUT_PREVIEW_CHARS]}'")
    if parsed_action is None:
        # Log raw output để thấy LLM trả về gì khi parse fail
        logger.warning(f"[STEP {step}] PARSE_FAIL raw_preview='{raw_output[:RAW_OUTPUT_PREVIEW_CHARS]}'")


def log_agent_tool_dispatch(step: int, tool_name: str, tool_input: dict[str, Any]):
    logger.info(f"[TOOL {step}] calling={tool_name} input={tool_input}")


def log_agent_tool_result(
    step: int,
    tool_name: str,
    success: bool,
    result_preview: str,
    *,
    outcome: str = "success",
    retryable: bool = False,
    result_count: int | None = None,
    used_context: bool = False,
    low_confidence: bool = False,
    is_ask_user: bool = False,
):
    level = logging.INFO if success else logging.WARNING
    logger.log(
        level,
        f"[TOOL {step}] {tool_name} "
        f"success={success} "
        f"outcome={outcome} "
        f"retryable={retryable} "
        f"result_count={result_count} "
        f"used_context={used_context} "
        f"low_confidence={low_confidence} "
        f"ask_user={is_ask_user} "
        f"result='{result_preview[:TOOL_RESULT_PREVIEW_CHARS]}'",
    )


def log_agent_finish(
    conversation_id: str,
    total_steps: int,
    steps_this_request: int,
    finish_reason: str,
    used_tools: list[str],
    answer_preview: str,
    elapsed_seconds: float | None = None,
):
    elapsed_part = (
        f" elapsed_seconds={elapsed_seconds:.3f}"
        if elapsed_seconds is not None
        else ""
    )
    logger.info(
        f"[FINISH] conv={conversation_id[:8]} "
        f"steps_this_request={steps_this_request} "
        f"total_steps={total_steps} "
        f"reason={finish_reason} "
        f"tools={used_tools} "
        f"answer='{answer_preview[:80]}'"
        f"{elapsed_part}"
    )
