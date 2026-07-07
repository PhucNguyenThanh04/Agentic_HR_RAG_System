from __future__ import annotations
import json

from pydantic import BaseModel, ConfigDict, Field

from src.tools.base_tool import BaseTool

ASK_USER_PREFIX = "__ASK_USER__"


class AskUserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        default="",
        description="Câu hỏi cần hỏi lại người dùng.",
    )
    options: list[str] | None = Field(
        default=None,
        description="Danh sách lựa chọn gợi ý cho người dùng, nếu có.",
    )
    allow_free_text: bool = Field(
        default=True,
        description="Cho phép người dùng nhập câu trả lời tự do ngoài options.",
    )


class AskUserTool(BaseTool):
    name = "ask_user"
    description = (
        "Hỏi lại người dùng khi câu hỏi thiếu thông tin cần thiết để tra cứu. "
        "Dùng khi không rõ mốc thời gian, tháng năm, loại nghỉ phép, hoặc điều kiện cụ thể. "
        "Có thể cung cấp options gợi ý cho user chọn. "
        "Không dùng khi đã đủ thông tin để tra cứu."
    )
    usage_hint = "Hỏi thêm khi thiếu thông tin mà tool không tự lấy được."
    input_example = (
        '{"question":"câu hỏi",'
        '"options":[],'
        '"allow_free_text":true}'
    )
    args_schema = AskUserInput

    async def run(
        self,
        question: str = "",
        options: list[str] | None = None,
        allow_free_text: bool = True,
    ) -> str:
        if not question.strip():
            question = "Bạn có thể cung cấp thêm thông tin để tôi hỗ trợ tốt hơn không?"

        payload = {
            "question": question.strip(),
            "options": options or [],
            "allow_free_text": allow_free_text,
        }
        return f"{ASK_USER_PREFIX}{json.dumps(payload, ensure_ascii=False)}"

    @staticmethod
    def is_ask_user(observation: str) -> bool:
        """Kiểm tra observation có phải là signal ask_user không."""
        return observation.startswith(ASK_USER_PREFIX)

    @staticmethod
    def parse_payload(observation: str) -> dict:
        """Parse JSON payload từ observation ask_user.

        Returns:
            {"question": str, "options": list[str], "allow_free_text": bool}

        Raises:
            ValueError: nếu observation không phải ask_user signal hoặc JSON invalid.
        """
        if not observation.startswith(ASK_USER_PREFIX):
            raise ValueError("Observation không phải ask_user signal")
        try:
            return json.loads(observation[len(ASK_USER_PREFIX):])
        except json.JSONDecodeError as exc:
            raise ValueError(f"ask_user payload không phải JSON hợp lệ: {exc}") from exc
