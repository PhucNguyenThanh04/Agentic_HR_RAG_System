from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends
from redis.asyncio import Redis

from src.agents.pending_store import AgentPendingStore
from src.agents.state import AgentState
from src.agents.supervisor import Supervisor
from src.core.dependenci import get_api_service_client, get_redis_client
from src.features.chat.schemas import ChatCitation, ChatRequest, ChatResponse
from src.integrations.api_service.clients import APIServiceClient
from src.integrations.llm.client import GeminiClient, get_gemini_client
from src.rag.retrieval.retrieval_pipeline import (
    RetrievalPipeline,
    get_retrieval_pipeline,
)
from src.tools.api_queries import (
    AttendanceQueryTool,
    EmployeeQueryTool,
    ShiftQueryTool,
)
from src.tools.ask_user_tool import AskUserTool
from src.tools.registry import ToolRegistry
from src.tools.vector_search_tool import VectorSearchTool


class ChatService:
    def __init__(
        self,
        retrieval_pipeline: RetrievalPipeline,
        api_service_client: APIServiceClient,
        llm_client: GeminiClient,
        pending_store: AgentPendingStore,
    ) -> None:
        self.retrieval_pipeline = retrieval_pipeline
        self.api_service_client = api_service_client
        self.supervisor = Supervisor(
            llm_client=llm_client,
            pending_store=pending_store,
        )

    async def chat(self, request: ChatRequest, *, access_token: str) -> ChatResponse:
        await self._validate_actor_context(request, access_token)
        registry = self._build_registry(request, access_token)
        state = await self.supervisor.run(request, registry)
        return self._to_chat_response(state)

    async def chat_stream(
        self,
        request: ChatRequest,
        *,
        access_token: str,
    ) -> AsyncGenerator[str, None]:
        await self._validate_actor_context(request, access_token)
        registry = self._build_registry(request, access_token)

        async def event_stream() -> AsyncGenerator[str, None]:
            async for event, payload in self.supervisor.stream(request, registry):
                if event == "_final_state":
                    state = payload["state"]
                    response = self._to_chat_response(state)
                    yield _format_sse("final", response.model_dump(mode="json"))
                    continue

                yield _format_sse(event, payload)

        return event_stream()

    async def _validate_actor_context(
        self,
        request: ChatRequest,
        access_token: str,
    ) -> None:
        await self.api_service_client.validate_actor_context(
            access_token=access_token,
            expected_employee_id=request.employee_id,
            expected_role=request.user_role,
        )

    def _build_registry(
        self,
        request: ChatRequest,
        access_token: str,
    ) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(
            VectorSearchTool(
                retrieval_pipeline=self.retrieval_pipeline,
                allowed_role=request.user_role,
                original_query=request.message,
            )
        )
        registry.register(
            EmployeeQueryTool(
                api_service_client=self.api_service_client,
                employee_id=request.employee_id,
                user_role=request.user_role,
                access_token=access_token,
            )
        )
        registry.register(
            ShiftQueryTool(
                api_service_client=self.api_service_client,
                employee_id=request.employee_id,
                user_role=request.user_role,
                access_token=access_token,
            )
        )
        registry.register(
            AttendanceQueryTool(
                api_service_client=self.api_service_client,
                employee_id=request.employee_id,
                user_role=request.user_role,
                access_token=access_token,
            )
        )
        registry.register(AskUserTool())
        return registry

    @staticmethod
    def _to_chat_response(state: AgentState) -> ChatResponse:
        citations = _collect_citations(state)
        used_context = any(step.used_context for step in state.steps)
        low_confidence = any(step.low_confidence for step in state.steps)

        if state.finish_reason == "ask_user":
            payload = state.ask_user_payload or {}
            return ChatResponse(
                answer=state.final_answer,
                citations=citations,
                low_confidence=low_confidence,
                used_context=used_context,
                ask_user=True,
                options=list(payload.get("options") or []),
                allow_free_text=bool(payload.get("allow_free_text", True)),
                finish_reason=state.finish_reason,
                error_code=None,
            )

        error_code = None
        if state.finish_reason == "max_steps":
            error_code = "MAX_STEPS_REACHED"
        elif state.finish_reason == "error":
            error_code = "AGENT_ERROR"

        return ChatResponse(
            answer=state.final_answer,
            citations=citations,
            low_confidence=low_confidence,
            used_context=used_context,
            ask_user=False,
            options=[],
            allow_free_text=True,
            finish_reason=state.finish_reason,
            error_code=error_code,
        )


def _collect_citations(state: AgentState) -> list[ChatCitation]:
    citations: list[ChatCitation] = []
    seen_chunk_ids: set[str] = set()

    for step in state.steps:
        for citation in step.citations:
            if citation.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(citation.chunk_id)
            citations.append(
                ChatCitation(
                    index=citation.index,
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    filename=citation.filename,
                    page=citation.page,
                    section=citation.section,
                    clause_number=citation.clause_number,
                    score=citation.score,
                    file_path=citation.file_path,
                )
            )

    return citations


def _format_sse(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def get_chat_service(
    retrieval_pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline),
    api_service_client: APIServiceClient = Depends(get_api_service_client),
    redis_client: Redis = Depends(get_redis_client),
) -> ChatService:
    return ChatService(
        retrieval_pipeline=retrieval_pipeline,
        api_service_client=api_service_client,
        llm_client=get_gemini_client(),
        pending_store=AgentPendingStore(redis_client),
    )
