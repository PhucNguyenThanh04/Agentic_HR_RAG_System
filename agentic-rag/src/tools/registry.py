from __future__ import annotations

from src.tools.base_tool import BaseTool


class ToolRegistry:
    """
    Quản lý danh sách tools cho Supervisor.

    Mỗi request tạo 1 registry riêng vì một số tool cần context
    per-request (allowed_role, employee_id).

    Usage:
        registry = ToolRegistry()
        registry.register(VectorSearchTool(...))
        registry.register(EmployeeQueryTool(...))
        registry.register(ShiftQueryTool(...))
        registry.register(AttendanceQueryTool(...))
        registry.register(AskUserTool())

        tool = registry.get("vector_search")
        await tool.run(query="...")
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' đã được đăng ký. "
                f"Mỗi tool name phải là duy nhất."
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(sorted(self._tools)) or "(không có tool nào)"
            raise KeyError(
                f"Tool '{name}' không tồn tại. "
                f"Các tool có sẵn: {available}"
            )
        return tool

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def build_tools_prompt(self) -> str:
        """
        Tạo mô tả compact cho LLM prompt.

        Đọc usage_hint và input_example từ chính tool class,
        không hardcode mapping ở đây.
        """
        if not self._tools:
            return "Không có tool nào khả dụng."

        lines = ["TOOLS:"]
        for tool in self._tools.values():
            hint = tool.usage_hint or tool.description
            lines.append(
                f"- {tool.name}: {hint} "
                f"Input: {tool.input_example}"
            )

        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
