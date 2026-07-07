import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.supervisor import Supervisor
from src.core.settings import get_settings
from src.features.chat.schemas import ChatRequest
from src.integrations.api_service.clients import APIServiceClient
from src.integrations.llm.client import get_gemini_client
from src.integrations.qdrant.client import QdrantClientManager
from src.integrations.qdrant.store import QdrantVectorStore
from src.rag.embeddings.embedding_client import EmbeddingClient
from src.rag.embeddings.embedding_service import EmbeddingService
from src.rag.retrieval.context_builder import ContextBuilder
from src.rag.retrieval.hybrid_retriever import HybridRetriever
from src.rag.retrieval.reranker import RerankerClient, RerankerService
from src.rag.retrieval.retrieval_pipeline import RetrievalPipeline
from src.tools.api_queries import AttendanceQueryTool, EmployeeQueryTool, ShiftQueryTool
from src.tools.ask_user_tool import AskUserTool
from src.tools.registry import ToolRegistry
from src.tools.vector_search_tool import VectorSearchTool


DATASET_PATH = Path(
    os.getenv("EVAL_DATASET_PATH", EVAL_DIR / "dataset" / "api_query_tools.json")
)
RESULTS_PATH = Path(
    os.getenv("EVAL_RESULTS_PATH", EVAL_DIR / "results" / "results.jsonl")
)
WARMUP_COUNT = int(os.getenv("EVAL_WARMUP_COUNT", "0"))
DELAY_SECONDS = float(os.getenv("EVAL_DELAY_SECONDS", "20"))
MAX_RETRIES = int(os.getenv("EVAL_MAX_RETRIES", "2"))
RETRY_DELAY_SECONDS = float(os.getenv("EVAL_RETRY_DELAY_SECONDS", "60"))
ENABLE_API_TOOLS = os.getenv("EVAL_ENABLE_API_TOOLS", "1").lower() not in {
    "0",
    "false",
    "no",
}
DEFAULT_EMPLOYEE_ID = os.getenv(
    "EVAL_EMPLOYEE_ID",
    "49fe804f-061c-4dca-80c6-9d981a86a9bd",
)
DEFAULT_USER_ROLE = os.getenv("EVAL_USER_ROLE", "employee")


async def build_retrieval_pipeline() -> tuple[RetrievalPipeline, QdrantClientManager]:
    settings = get_settings()
    embedding_client = EmbeddingClient()
    embedding_service = EmbeddingService(embedding_client)
    await embedding_service.warmup()

    qdrant_manager = QdrantClientManager()
    await qdrant_manager.ensure_collection(settings.default_qdrant_collection)

    vector_store = QdrantVectorStore(qdrant_manager.get_client())

    reranker_client = RerankerClient()
    reranker_service = RerankerService(reranker_client)
    await reranker_service.warmup()

    return (    
        RetrievalPipeline(
            hybrid_retriever=HybridRetriever(
                embedding_service=embedding_service,
                vector_store=vector_store,
            ),
            reranker_service=reranker_service,
            context_builder=ContextBuilder(),
        ),
        qdrant_manager,
    )


def build_registry(
    retrieval_pipeline: RetrievalPipeline,
    request: ChatRequest,
    api_service_client: APIServiceClient | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        VectorSearchTool(
            retrieval_pipeline=retrieval_pipeline,
            allowed_role=request.user_role,
            original_query=request.message,
        )
    )
    if api_service_client is not None:
        registry.register(
            EmployeeQueryTool(
                api_service_client=api_service_client,
                employee_id=request.employee_id,
                user_role=request.user_role,
            )
        )
        registry.register(
            ShiftQueryTool(
                api_service_client=api_service_client,
                employee_id=request.employee_id,
                user_role=request.user_role,
            )
        )
        registry.register(
            AttendanceQueryTool(
                api_service_client=api_service_client,
                employee_id=request.employee_id,
                user_role=request.user_role,
            )
        )
    registry.register(AskUserTool())
    return registry


def build_chat_request(case: dict, conversation_id: str) -> ChatRequest:
    chat_request = case.get("chat_request")
    if isinstance(chat_request, dict):
        payload = dict(chat_request)
        payload["message"] = payload.get("message") or case.get("question")
        payload["employee_id"] = payload.get("employee_id") or DEFAULT_EMPLOYEE_ID
        payload["user_role"] = (
            payload.get("user_role")
            or case.get("user_role")
            or case.get("role")
            or DEFAULT_USER_ROLE
        )
        payload["conversation_id"] = payload.get("conversation_id") or conversation_id
        payload["chat_history"] = payload.get("chat_history") or []
        return ChatRequest.model_validate(payload)

    return ChatRequest(
        message=case.get("message") or case["question"],
        employee_id=str(case.get("employee_id") or DEFAULT_EMPLOYEE_ID),
        user_role=str(case.get("user_role") or case.get("role") or DEFAULT_USER_ROLE),
        conversation_id=conversation_id,
        chat_history=case.get("chat_history") or [],
    )


def case_key(case: dict) -> tuple[str, str, str]:
    chat_request = case.get("chat_request")
    if isinstance(chat_request, dict):
        return (
            str(chat_request.get("message") or case.get("question") or ""),
            str(chat_request.get("employee_id") or DEFAULT_EMPLOYEE_ID),
            str(
                chat_request.get("user_role")
                or case.get("user_role")
                or case.get("role")
                or DEFAULT_USER_ROLE
            ),
        )

    return (
        str(case.get("message") or case["question"]),
        str(case.get("employee_id") or DEFAULT_EMPLOYEE_ID),
        str(case.get("user_role") or case.get("role") or DEFAULT_USER_ROLE),
    )


async def run_eval():
    # ── 1. Load dataset ──
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    # ── 2. Resume — bỏ qua câu đã chạy ──
    RESULTS_PATH.parent.mkdir(exist_ok=True)

    done_cases = set()
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                done_cases.add(case_key(r))
        print(f"Đã có {len(done_cases)} kết quả, tiếp tục...")

    remaining = [c for c in cases if case_key(c) not in done_cases]
    print(f"Còn {len(remaining)} câu cần chạy")

    if not remaining:
        print("Xong hết rồi!")
        return

    # ── 3. Khởi tạo supervisor + retrieval pipeline ──
    settings = get_settings()
    supervisor = Supervisor(llm_client=get_gemini_client())
    retrieval_pipeline, qdrant_manager = await build_retrieval_pipeline()
    api_service_http_client: httpx.AsyncClient | None = None
    api_service_client: APIServiceClient | None = None
    if ENABLE_API_TOOLS:
        api_service_http_client = httpx.AsyncClient(
            base_url=settings.api_server_base_url.rstrip("/"),
            timeout=httpx.Timeout(10.0, connect=3.0),
        )
        api_service_client = APIServiceClient(api_service_http_client)

    try:
        # ── 4. Warm up nếu cần ──
        # Mặc định tắt để không tốn quota Gemini khi chạy eval hàng loạt.
        if WARMUP_COUNT > 0:
            print(f"Warming up {WARMUP_COUNT} câu...")
            for i, case in enumerate(remaining[:WARMUP_COUNT], start=1):
                request = build_chat_request(case, conversation_id=f"warmup_{i}")
                await supervisor.run(
                    request,
                    build_registry(retrieval_pipeline, request, api_service_client),
                )
                await asyncio.sleep(DELAY_SECONDS)
            print("Warm up xong\n")

        # ── 5. Chạy eval thực sự ──
        for i, case in enumerate(remaining):
            request = build_chat_request(case, conversation_id=f"eval_{i}")
            print(f"[{i+1}/{len(remaining)}] {request.message[:60]}...")
            registry = build_registry(retrieval_pipeline, request, api_service_client)

            state = None
            start = time.perf_counter()
            for attempt in range(MAX_RETRIES + 1):
                state = await supervisor.run(request, registry)
                if state.finish_reason != "error":
                    break

                if attempt >= MAX_RETRIES:
                    break

                wait_seconds = RETRY_DELAY_SECONDS * (attempt + 1)
                print(
                    "    → gặp lỗi agent/LLM, chờ "
                    f"{wait_seconds:.0f}s rồi thử lại lần {attempt + 2}"
                )
                await asyncio.sleep(wait_seconds)

            latency_ms = (time.perf_counter() - start) * 1000
            assert state is not None

            # ── 6. Extract từ AgentState thực tế ──
            record = {
                "question": request.message,
                "employee_id": request.employee_id,
                "user_role": request.user_role,
                "expected_tool": case["expected_tool"],
                "ground_truth": case["ground_truth_answer"],
                "final_answer": state.final_answer,
                "finish_reason": state.finish_reason,  # "answer"|"ask_user"|"max_steps"|"error"
                "is_done": state.is_done,
                "total_steps": state.step_count,
                "tools_called": [
                    s.action for s in state.steps
                    if s.action != "final_answer"
                ],
                "asked_user": any(
                    s.action == "ask_user" for s in state.steps
                ),
                "retrieved_chunks": [
                    c.chunk_id
                    for s in state.steps
                    if s.action == "vector_search"
                    for c in s.citations
                ],
                "latency_ms": round(latency_ms, 1),
                "correct": None,  # Thành điền tay sau
            }

            # ── 7. Ghi ngay sau mỗi req ──
            with open(RESULTS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            print(f"    → finish_reason={state.finish_reason} | {latency_ms:.0f}ms")

            # ── 8. Delay tránh hết quota ──
            if i < len(remaining) - 1:
                await asyncio.sleep(DELAY_SECONDS)

        print(f"\nXong! Mở {RESULTS_PATH} để điền correct: true/false")
    finally:
        if api_service_http_client is not None:
            await api_service_http_client.aclose()
        await qdrant_manager.close()

if __name__ == "__main__":
    asyncio.run(run_eval())
