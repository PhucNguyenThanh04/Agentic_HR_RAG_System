from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, cast

import httpx
import pytest
from fastapi import HTTPException

from src.agents.state import AgentState
from src.core.dependenci import get_user_access_token
from src.features.chat.service import ChatService
from src.features.chat.schemas import ChatRequest
from src.integrations.api_service.clients import APIServiceClient
from src.tools.api_queries.attendance_tool import AttendanceQueryTool
from src.tools.api_queries.employee_tool import EmployeeQueryTool
from src.tools.base_tool import ToolResult


ACTOR_USER_ID = uuid.uuid4()
ACTOR_EMPLOYEE_ID = uuid.uuid4()
SUBORDINATE_EMPLOYEE_ID = uuid.uuid4()
OUTSIDE_EMPLOYEE_ID = uuid.uuid4()


def employee_payload(employee_id: uuid.UUID, *, user_id: uuid.UUID | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "employee_id": str(employee_id),
        "user_id": str(user_id) if user_id else None,
        "employee_code": f"EMP-{str(employee_id)[:8]}",
        "full_name": "Test Employee",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }


class ToolCallingSupervisor:
    def __init__(self, action: str, action_input: dict[str, object]) -> None:
        self.action = action
        self.action_input = action_input
        self.tool_result: ToolResult | None = None

    async def run(self, request: ChatRequest, registry):
        self.tool_result = await registry.get(self.action).run(**self.action_input)
        state = AgentState(
            user_message=request.message,
            employee_id=request.employee_id,
            user_role=request.user_role,
            chat_history=request.chat_history,
        )
        state.finish_with_answer(self.tool_result.observation)
        return state


def test_actor_context_validation_uses_bearer_and_rejects_mismatch() -> None:
    access_token = "request-scoped-user-jwt"
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        if request.url.path == "/api/v1/auth/me":
            return httpx.Response(
                200,
                json={"user_id": str(ACTOR_USER_ID), "role_name": "manager"},
            )
        if request.url.path == "/api/v1/employees/me":
            return httpx.Response(
                200,
                json=employee_payload(ACTOR_EMPLOYEE_ID, user_id=ACTOR_USER_ID),
            )
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://api.test",
        ) as http_client:
            client = APIServiceClient(http_client)
            await client.validate_actor_context(
                access_token=access_token,
                expected_employee_id=str(ACTOR_EMPLOYEE_ID),
                expected_role="manager",
            )
            with pytest.raises(ValueError, match="role context"):
                await client.validate_actor_context(
                    access_token=access_token,
                    expected_employee_id=str(ACTOR_EMPLOYEE_ID),
                    expected_role="admin",
                )

    asyncio.run(run())

    assert seen_requests
    assert all(
        request.headers["Authorization"] == f"Bearer {access_token}"
        for request in seen_requests
    )
    assert all("Rag-API-Key" not in request.headers for request in seen_requests)


def test_employee_self_query_succeeds_through_request_scoped_agent_registry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer employee-jwt"
        if request.url.path == "/api/v1/auth/me":
            return httpx.Response(
                200,
                json={"user_id": str(ACTOR_USER_ID), "role_name": "employee"},
            )
        if request.url.path in {
            "/api/v1/employees/me",
            f"/api/v1/employees/{ACTOR_EMPLOYEE_ID}",
        }:
            return httpx.Response(
                200,
                json=employee_payload(ACTOR_EMPLOYEE_ID, user_id=ACTOR_USER_ID),
            )
        return httpx.Response(404)

    async def run() -> ToolResult:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://api.test",
        ) as http_client:
            service = ChatService(
                retrieval_pipeline=cast(Any, object()),
                api_service_client=APIServiceClient(http_client),
                llm_client=cast(Any, object()),
                pending_store=cast(Any, None),
            )
            supervisor = ToolCallingSupervisor("employee_query", {})
            service.supervisor = cast(Any, supervisor)
            await service.chat(
                ChatRequest(
                    message="Hồ sơ của tôi",
                    employee_id=str(ACTOR_EMPLOYEE_ID),
                    user_role="employee",
                    conversation_id=str(uuid.uuid4()),
                ),
                access_token="employee-jwt",
            )
            assert supervisor.tool_result is not None
            return supervisor.tool_result

    result = asyncio.run(run())
    assert result.outcome == "success"


@pytest.mark.parametrize("access_token", ["expired-token", "wrong-audience-token"])
def test_invalid_forwarded_token_is_rejected_without_fallback(
    access_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "invalid token"})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://api.test",
        ) as http_client:
            client = APIServiceClient(http_client)
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.validate_actor_context(
                    access_token=access_token,
                    expected_employee_id=str(ACTOR_EMPLOYEE_ID),
                    expected_role="employee",
                )
            assert access_token not in str(exc_info.value)

    with caplog.at_level(logging.WARNING):
        asyncio.run(run())
    assert access_token not in caplog.text


def test_rag_key_without_user_bearer_has_no_pii_fallback() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_user_access_token(None))
    assert exc_info.value.status_code == 401


def test_employee_attendance_for_other_employee_is_denied_by_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer employee-jwt"
        assert "Rag-API-Key" not in request.headers
        if request.url.params.get("employee_id") != str(ACTOR_EMPLOYEE_ID):
            return httpx.Response(403, json={"detail": "forbidden"})
        return httpx.Response(200, json=[])

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://api.test",
        ) as http_client:
            tool = AttendanceQueryTool(
                APIServiceClient(http_client),
                employee_id=str(ACTOR_EMPLOYEE_ID),
                user_role="employee",
                access_token="employee-jwt",
            )
            own_result = await tool.run()
            other_result = await tool.run(employee_id=OUTSIDE_EMPLOYEE_ID)
            return own_result, other_result

    own_result, other_result = asyncio.run(run())
    assert own_result.outcome == "empty"
    assert other_result.outcome == "error"
    assert other_result.metadata["http_status"] == 403


def test_manager_tool_allows_subordinate_but_api_denies_outside_scope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer manager-jwt"
        target_id = uuid.UUID(request.url.path.rsplit("/", 1)[-1])
        if target_id not in {ACTOR_EMPLOYEE_ID, SUBORDINATE_EMPLOYEE_ID}:
            return httpx.Response(403, json={"detail": "forbidden"})
        return httpx.Response(200, json=employee_payload(target_id))

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://api.test",
        ) as http_client:
            tool = EmployeeQueryTool(
                APIServiceClient(http_client),
                employee_id=str(ACTOR_EMPLOYEE_ID),
                user_role="manager",
                access_token="manager-jwt",
            )
            subordinate_result = await tool.run(employee_id=SUBORDINATE_EMPLOYEE_ID)
            outside_result = await tool.run(employee_id=OUTSIDE_EMPLOYEE_ID)
            return subordinate_result, outside_result

    subordinate_result, outside_result = asyncio.run(run())
    assert subordinate_result.outcome == "success"
    assert outside_result.outcome == "error"
    assert outside_result.metadata["http_status"] == 403


def test_access_token_is_not_serialized_in_chat_or_pending_state() -> None:
    access_token = "must-never-be-persisted"
    request = ChatRequest(
        message="Hôm nay tôi đi ca nào?",
        employee_id=str(ACTOR_EMPLOYEE_ID),
        user_role="employee",
        conversation_id=str(uuid.uuid4()),
    )
    state = AgentState(
        user_message=request.message,
        employee_id=request.employee_id,
        user_role=request.user_role,
        chat_history=[],
    )

    serialized = json.dumps(
        {
            "request": request.model_dump(mode="json"),
            "pending": state.to_pending_dict(),
        }
    )
    assert "access_token" not in serialized
    assert access_token not in serialized
