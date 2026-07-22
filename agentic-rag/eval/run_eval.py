"""
Eval script cho Agentic HR RAG System.

Cách dùng:
    1. Đảm bảo file .env đã cấu hình đúng (GOOGLE_API_KEY, QDRANT_*, REDIS_*, ...).
    2. Đặt file dataset tại eval/dataset/newdata.json (hoặc sửa DATASET_PATH bên dưới).
    3. Chạy từ thư mục gốc agentic-rag:
           python -m eval.run_eval
       hoặc:
           cd eval && python run_eval.py

Script sẽ:
    - Gọi chat_service.chat() thật (đúng production code, không mock).
    - Với mỗi câu, tạo conversation_id riêng biệt (tránh nhiễm state giữa các câu).
    - Bắt log logger "agentic_rag.agent" trong lúc gọi, parse dòng [FINISH]
      để lấy chính xác total_steps, tools_called, finish_reason.
    - Nếu finish_reason == "ask_user" -> tự động gửi lượt 2 với câu trả lời giả lập
      (bạn cấu hình sẵn trong dataset, field "simulated_followup").
    - Rate limit ở tầng GeminiClient._call_once() — mỗi lệnh Gemini thật đều
      được giới hạn tốc độ + retry với Retry-After detection, không chỉ ở tầng
      chat() call bên ngoài.
    - Lưu kết quả progressive ra eval_results.jsonl (ghi từng dòng ngay sau khi
      xử lý xong 1 câu, để không mất dữ liệu nếu script bị dừng giữa chừng).
"""

import asyncio
import json
import logging
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

# ============================================================
# IMPORT — từ source code thật của project
# ============================================================

# Đảm bảo thư mục gốc agentic-rag nằm trong sys.path để import "src.*" hoạt động
_EVAL_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _EVAL_DIR.parent  # agentic-rag/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.features.chat.schemas import ChatRequest, ChatHistoryTurn  # noqa: E402
from src.features.chat.service import ChatService  # noqa: E402
from src.integrations.llm.client import GeminiClient, get_gemini_client, LLMResponse  # noqa: E402
from src.integrations.cache.redis_client import create_redis_async_client  # noqa: E402
from src.integrations.qdrant.client import QdrantClientManager  # noqa: E402
from src.integrations.qdrant.store import QdrantVectorStore  # noqa: E402
from src.rag.embeddings.embedding_client import EmbeddingClient  # noqa: E402
from src.rag.embeddings.embedding_service import EmbeddingService  # noqa: E402
from src.rag.retrieval.reranker import RerankerClient, RerankerService  # noqa: E402
from src.rag.retrieval.hybrid_retriever import HybridRetriever  # noqa: E402
from src.rag.retrieval.context_builder import ContextBuilder  # noqa: E402
from src.rag.retrieval.retrieval_pipeline import RetrievalPipeline  # noqa: E402
from src.agents.pending_store import AgentPendingStore  # noqa: E402
from src.integrations.api_service.clients import APIServiceClient  # noqa: E402
from src.core.settings import get_settings  # noqa: E402

ChatRequestCls = ChatRequest

# ============================================================
# CẤU HÌNH
# ============================================================

DATASET_PATH = _EVAL_DIR / "dataset" / "newdata.json"
OUTPUT_PATH = _EVAL_DIR / "eval_results.jsonl"

# Khoảng cách tối thiểu giữa 2 lệnh Gemini API liên tiếp (giây).
# Free tier Gemini Flash ~15 RPM → 60/15 = 4s, để buffer 5s.
# Giá trị này áp dụng ở tầng _call_once, tức MỌI lệnh Gemini thật,
# bao gồm cả các bước ReAct bên trong 1 lần chat().
GEMINI_MIN_INTERVAL_SECONDS = 5.0

# Số lần retry tối đa khi gặp 429/RESOURCE_EXHAUSTED cho 1 lệnh Gemini.
GEMINI_MAX_RETRIES = 6

# Số lần retry tối đa cho toàn bộ 1 lần gọi chat() (last-resort fallback,
# chỉ dùng cho lỗi KHÔNG phải rate limit — vì rate limit đã được xử lý ở
# tầng thấp hơn bên trong GeminiClient).
CHAT_MAX_RETRIES = 2

LOGGER_NAME = "agentic_rag.agent"  # đúng tên logger xuất hiện trong log bạn gửi


# ============================================================
# RATE LIMITING Ở TẦNG GEMINI API CALL (Vấn đề 1 + 2 + 3)
# ============================================================
#
# Monkey-patch GeminiClient._call_once() để TỪNG lệnh Gemini thật đều
# được rate limit + retry thông minh. Điều này đảm bảo:
#   - Vấn đề 1: Rate limit áp dụng cho mọi lệnh Gemini bên trong ReAct
#     loop, không chỉ ở cấp chat() call bên ngoài.
#   - Vấn đề 2: Khi bước 3/5 bị 429, chỉ retry bước đó (không chạy lại
#     toàn bộ agent loop từ đầu), tiết kiệm quota.
#   - Vấn đề 3: Ưu tiên đọc Retry-After / retry_delay từ exception trước
#     khi dùng exponential backoff cố định.
# ============================================================

# Shared state cho rate limiter
_gemini_last_call_time = 0.0
_gemini_rate_lock = asyncio.Lock()
_gemini_call_count = 0  # theo dõi tổng số lệnh Gemini đã gọi


def _extract_retry_after(exc: Exception) -> float | None:
    """
    Thử trích xuất thời gian chờ từ exception Gemini API.

    Gemini SDK (google-generativeai / google-api-core) có thể chứa thông tin
    retry delay trong nhiều vị trí tùy phiên bản SDK:
      - exc.retry_info.retry_delay (google.api_core.exceptions)
      - exc._errors[*].retry_delay
      - exc.metadata (gRPC exceptions)
      - Retry-After trong error message string
    """
    # 1. google.api_core.exceptions có thể có retry_info
    retry_info = getattr(exc, "retry_info", None)
    if retry_info is not None:
        retry_delay = getattr(retry_info, "retry_delay", None)
        if retry_delay is not None:
            # retry_delay có thể là timedelta hoặc số
            if hasattr(retry_delay, "total_seconds"):
                return retry_delay.total_seconds()
            return float(retry_delay)

    # 2. Một số exception gRPC chứa metadata với retry-after
    metadata = getattr(exc, "metadata", None) or getattr(exc, "trailing_metadata", None)
    if metadata:
        # metadata có thể là list of tuples hoặc dict-like
        if callable(metadata):
            try:
                metadata = metadata()
            except Exception:
                metadata = None
        if metadata:
            for item in metadata:
                if isinstance(item, tuple) and len(item) >= 2:
                    key, value = item[0], item[1]
                    if isinstance(key, (str, bytes)):
                        key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                        if "retry" in key_str.lower() and "after" in key_str.lower():
                            try:
                                return float(value.decode("utf-8") if isinstance(value, bytes) else value)
                            except (ValueError, AttributeError):
                                pass

    # 3. Wrapped exceptions (e.g. LLMError wrapping gRPC error)
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc:
        result = _extract_retry_after(cause)
        if result is not None:
            return result

    # 4. Fallback: parse "retry after <N>" từ error message string
    msg = str(exc)
    match = re.search(r"retry[\s_-]*after[:\s]*(\d+(?:\.\d+)?)", msg, re.IGNORECASE)
    if match:
        return float(match.group(1))

    return None


def _is_rate_limit_error(exc: Exception) -> bool:
    """Kiểm tra xem exception có phải do rate limit (429) không."""
    msg = str(exc)
    return (
        "429" in msg
        or "RESOURCE_EXHAUSTED" in msg
        or "rate limit" in msg.lower()
        or "quota" in msg.lower()
    )


def _patch_gemini_client_rate_limiting(client: GeminiClient) -> None:
    """
    Monkey-patch GeminiClient._call_once() để thêm per-call rate limiting
    và intelligent retry trực tiếp ở tầng thấp nhất (mỗi lệnh Gemini API).

    Không sửa production code — chỉ áp dụng trong eval script.
    """
    original_call_once = client._call_once

    async def rate_limited_call_once(
        *,
        model: Any,
        prompt: str,
        generation_config: Any,
    ) -> LLMResponse:
        global _gemini_last_call_time, _gemini_call_count

        for attempt in range(GEMINI_MAX_RETRIES):
            # --- Enforce minimum interval giữa 2 lệnh liên tiếp ---
            async with _gemini_rate_lock:
                elapsed = time.monotonic() - _gemini_last_call_time
                if elapsed < GEMINI_MIN_INTERVAL_SECONDS:
                    wait = GEMINI_MIN_INTERVAL_SECONDS - elapsed
                    await asyncio.sleep(wait)
                _gemini_last_call_time = time.monotonic()
                _gemini_call_count += 1
                call_num = _gemini_call_count

            try:
                result = await original_call_once(
                    model=model,
                    prompt=prompt,
                    generation_config=generation_config,
                )
                return result

            except Exception as exc:
                if not _is_rate_limit_error(exc):
                    # Không phải rate limit → raise ngay, để Supervisor xử lý
                    raise

                if attempt >= GEMINI_MAX_RETRIES - 1:
                    print(
                        f"    ⛔ Gemini call #{call_num}: hết {GEMINI_MAX_RETRIES} lần retry, "
                        f"raise exception"
                    )
                    raise

                # Ưu tiên Retry-After từ exception, fallback exponential backoff
                retry_after = _extract_retry_after(exc)
                if retry_after is not None and retry_after > 0:
                    wait = retry_after + 1.0  # +1s buffer
                    print(
                        f"    ⏳ Gemini call #{call_num}: rate limited, "
                        f"server hint retry_after={retry_after:.0f}s → chờ {wait:.0f}s "
                        f"(attempt {attempt + 1}/{GEMINI_MAX_RETRIES})"
                    )
                else:
                    wait = min((2 ** attempt) * 2 + 2, 120)  # cap 120s
                    print(
                        f"    ⏳ Gemini call #{call_num}: rate limited (429), "
                        f"exponential backoff → chờ {wait:.0f}s "
                        f"(attempt {attempt + 1}/{GEMINI_MAX_RETRIES})"
                    )

                await asyncio.sleep(wait)
                continue

        # Không bao giờ tới đây, nhưng type-safety
        raise RuntimeError("Vượt quá số lần retry Gemini API call")

    # Áp dụng monkey-patch
    client._call_once = rate_limited_call_once
    print(
        f"✓ Đã patch GeminiClient với per-call rate limiting "
        f"(interval={GEMINI_MIN_INTERVAL_SECONDS}s, max_retries={GEMINI_MAX_RETRIES})"
    )


# ============================================================
# BUILD CHAT SERVICE — standalone (không qua FastAPI)
# ============================================================

# Giữ reference để cleanup khi kết thúc
_cleanup_resources: dict = {}


async def build_chat_service() -> ChatService:
    """
    Khởi tạo ChatService giống hệt lúc app chạy thật (main.py lifespan),
    KHÔNG qua FastAPI Depends (vì script chạy standalone, không có
    HTTP request/response cycle).
    """
    import httpx

    settings = get_settings()

    # --- Redis ---
    redis_client = create_redis_async_client()
    try:
        await redis_client.ping()
        print("✓ Redis kết nối thành công")
    except Exception as exc:
        # Thử fallback no-auth nếu server không cần password
        if "without any password configured" in str(exc):
            await redis_client.aclose()
            redis_client = create_redis_async_client(force_no_auth=True)
            await redis_client.ping()
            print("✓ Redis kết nối thành công (no-auth fallback)")
        else:
            raise
    _cleanup_resources["redis"] = redis_client

    # --- Embedding ---
    embedding_client = EmbeddingClient()
    embedding_service = EmbeddingService(embedding_client)
    print(f"⏳ Warming up embedding model trên {embedding_client.device}...")
    await embedding_service.warmup()
    print("✓ Embedding model warmup completed")

    # --- Qdrant ---
    qdrant_manager = QdrantClientManager()
    await qdrant_manager.ensure_collection(settings.default_qdrant_collection)
    vector_store = QdrantVectorStore(qdrant_manager.get_client())
    print(f"✓ Qdrant client initialized, collection: {settings.default_qdrant_collection}")
    _cleanup_resources["qdrant"] = qdrant_manager

    # --- Reranker ---
    reranker_client = RerankerClient()
    reranker_service = RerankerService(reranker_client)
    print(f"⏳ Warming up reranker model trên {reranker_client.device}...")
    await reranker_service.warmup()
    print("✓ Reranker model warmup completed")

    # --- Retrieval Pipeline ---
    retrieval_pipeline = RetrievalPipeline(
        hybrid_retriever=HybridRetriever(
            embedding_service=embedding_service,
            vector_store=vector_store,
        ),
        reranker_service=reranker_service,
        context_builder=ContextBuilder(),
    )

    # --- API Service Client (httpx -> APIServiceClient) ---
    http_client = httpx.AsyncClient(
        base_url=settings.api_server_base_url.rstrip("/"),
        timeout=httpx.Timeout(10.0, connect=3.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    api_service_client = APIServiceClient(http_client)
    print(f"✓ API Service client -> {settings.api_server_base_url}")
    _cleanup_resources["http_client"] = http_client

    # --- LLM Client (Gemini) + Rate Limiting Patch ---
    llm_client = get_gemini_client()
    _patch_gemini_client_rate_limiting(llm_client)
    print(f"✓ Gemini client initialized, model: {settings.gemini_model}")

    # --- Pending Store (Redis-backed) ---
    pending_store = AgentPendingStore(redis_client)

    # --- Assemble ChatService ---
    chat_service = ChatService(
        retrieval_pipeline=retrieval_pipeline,
        api_service_client=api_service_client,
        llm_client=llm_client,
        pending_store=pending_store,
    )

    print("✓ ChatService đã sẵn sàng\n")
    return chat_service


async def cleanup():
    """Dọn dẹp tài nguyên sau khi chạy xong."""
    http_client = _cleanup_resources.get("http_client")
    if http_client is not None:
        await http_client.aclose()

    qdrant = _cleanup_resources.get("qdrant")
    if qdrant is not None:
        await qdrant.close()

    redis = _cleanup_resources.get("redis")
    if redis is not None:
        await redis.aclose()

    print(f"✓ Đã dọn dẹp tài nguyên (tổng Gemini API calls: {_gemini_call_count})")


# ============================================================
# LOG CAPTURE — bắt dòng [FINISH] để lấy tools_called/total_steps
# ============================================================

FINISH_LINE_RE = re.compile(
    r"\[FINISH\]\s+conv=(?P<conv>\S+)\s+"
    r"steps_this_request=(?P<steps_this_request>\d+)\s+"
    r"total_steps=(?P<total_steps>\d+)\s+"
    r"reason=(?P<reason>\S+)\s+"
    r"tools=(?P<tools>\[[^\]]*\])\s+"
    r"answer='(?P<answer>.*?)'\s+"
    r"elapsed_seconds=(?P<elapsed>[\d.]+)"
)


class ConversationLogCapture(logging.Handler):
    """
    Handler tạm thời gắn vào logger agentic_rag.agent trong lúc gọi chat(),
    chỉ giữ lại các dòng [FINISH] khớp với conversation_id đang xử lý.
    """

    def __init__(self, conversation_id: str):
        super().__init__(level=logging.INFO)
        self.conversation_id = conversation_id
        self.finish_records: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if "[FINISH]" not in msg:
            return
        m = FINISH_LINE_RE.search(msg)
        if not m:
            return
        # conv= có thể là "pending-xxxx" ở lượt đầu tiên nếu hệ thống tự sinh id
        # trước khi gán conversation_id thật -> vẫn chấp nhận nếu chứa đúng id
        # hoặc khớp tuyệt đối.
        if self.conversation_id not in m.group("conv") and m.group("conv") not in self.conversation_id:
            return
        self.finish_records.append(
            {
                "steps_this_request": int(m.group("steps_this_request")),
                "total_steps": int(m.group("total_steps")),
                "finish_reason": m.group("reason"),
                "tools_called": json.loads(m.group("tools").replace("'", '"')),
                "log_answer": m.group("answer"),
                "elapsed_seconds": float(m.group("elapsed")),
            }
        )


async def call_with_log_capture(chat_service, chat_request, conversation_id: str):
    """Gọi chat_service.chat() và đồng thời bắt log [FINISH] tương ứng."""
    logger = logging.getLogger(LOGGER_NAME)
    handler = ConversationLogCapture(conversation_id)
    logger.addHandler(handler)
    try:
        response = await chat_service.chat(chat_request)
    finally:
        logger.removeHandler(handler)
    return response, handler.finish_records


# ============================================================
# CHAT-LEVEL FALLBACK RETRY (last-resort, cho lỗi KHÔNG phải 429)
# ============================================================
#
# Vì rate limit + retry 429 đã được xử lý ở tầng _call_once (bên trong
# GeminiClient), hàm này chỉ đóng vai trò safety net cho lỗi transient
# khác (network timeout, server 500, v.v.). Không cần rate limiting ở đây
# vì _call_once đã xử lý rồi.
# ============================================================


async def resilient_chat_call(chat_service, chat_request, conversation_id: str):
    """
    Gọi chat_service.chat() với fallback retry cho lỗi transient
    (KHÔNG phải rate limit — đã xử lý ở tầng GeminiClient).
    """
    last_exc = None
    for attempt in range(CHAT_MAX_RETRIES):
        try:
            return await call_with_log_capture(chat_service, chat_request, conversation_id)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            # Rate limit errors: không retry ở tầng này vì đã retry ở _call_once
            if _is_rate_limit_error(exc):
                raise
            # Lỗi khác: retry 1 lần nữa
            if attempt < CHAT_MAX_RETRIES - 1:
                wait = 3 * (attempt + 1)
                print(f"    ⚠️ Lỗi transient, retry sau {wait}s: {type(exc).__name__}: {exc}")
                await asyncio.sleep(wait)
                continue
            raise
    raise last_exc  # type: ignore[misc]


# ============================================================
# LOGIC EVAL CHO 1 CÂU (có xử lý ask_user 2 lượt)
# ============================================================


async def run_single_item(chat_service, item: dict, ChatRequestCls) -> dict:
    conversation_id = f"eval-{uuid.uuid4()}"

    request = ChatRequestCls(
        message=item["question"],
        employee_id=item["employee_id"],
        user_role=item["user_role"],
        conversation_id=conversation_id,
        chat_history=[],
    )

    response, finish_records = await resilient_chat_call(chat_service, request, conversation_id)

    result = {
        "question": item["question"],
        "employee_id": item["employee_id"],
        "user_role": item["user_role"],
        "category": item.get("category"),
        "ground_truth": item.get("ground_truth"),
        "source_reference": item.get("source_reference"),
        "conversation_id": conversation_id,
        "answer": response.answer,
        "ask_user": response.ask_user,
        "finish_reason": response.finish_reason,
        "low_confidence": response.low_confidence,
        "used_context": response.used_context,
        "citations": [c.model_dump() for c in response.citations],
        # từ log [FINISH] - nguồn chính xác cho tools_called / total_steps
        "log_finish_records": finish_records,
    }

    # Nếu hệ thống hỏi lại (ask_user) -> chỉ gửi lượt follow-up khi dataset
    # có field "simulated_followup" cụ thể. Nếu không có, ghi nhận ask_user
    # là kết quả hợp lệ (tránh gửi câu trả lời generic vô nghĩa khiến agent
    # lặp ask_user → max_steps).
    if response.ask_user and "simulated_followup" in item:
        followup_text = item["simulated_followup"]
        print(f"    → Agent hỏi lại, gửi follow-up: {followup_text[:50]}...")
        followup_request = ChatRequestCls(
            message=followup_text,
            employee_id=item["employee_id"],
            user_role=item["user_role"],
            conversation_id=conversation_id,  # GIỮ NGUYÊN conv id để nối pending state
            chat_history=[
                ChatHistoryTurn(role="user", content=item["question"]),
                ChatHistoryTurn(role="assistant", content=response.answer),
            ],
        )
        followup_response, followup_finish_records = await resilient_chat_call(
            chat_service, followup_request, conversation_id
        )
        result["followup_message"] = followup_text
        result["followup_answer"] = followup_response.answer
        result["followup_finish_reason"] = followup_response.finish_reason
        result["log_finish_records"].extend(followup_finish_records)
    elif response.ask_user:
        print(f"    → Agent hỏi lại (ask_user), không có simulated_followup → bỏ qua follow-up")

    # Gộp tools_called từ toàn bộ log records của conversation này
    all_tools = []
    for rec in result["log_finish_records"]:
        all_tools.extend(rec["tools_called"])
    result["tools_called"] = all_tools
    result["total_steps"] = (
        result["log_finish_records"][-1]["total_steps"] if result["log_finish_records"] else None
    )

    return result


# ============================================================
# MAIN
# ============================================================


async def main():
    if not DATASET_PATH.exists():
        print(f"❌ Không tìm thấy dataset tại: {DATASET_PATH}")
        print("   Hãy đặt file dataset JSON vào đúng đường dẫn.")
        sys.exit(1)

    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"Đã load {len(dataset)} câu từ {DATASET_PATH}")

    # ── Resume: đếm số dòng đã có trong eval_results.jsonl ──
    completed_count = 0
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip():  # bỏ qua dòng trống
                    completed_count += 1

    if completed_count > 0:
        if completed_count >= len(dataset):
            print(f"✅ Đã hoàn thành toàn bộ {completed_count}/{len(dataset)} câu. Không cần chạy thêm.")
            print(f"   Kết quả tại: {OUTPUT_PATH}")
            return
        print(f"📋 Tìm thấy {completed_count}/{len(dataset)} câu đã chạy trong {OUTPUT_PATH.name}")
        print(f"   → Tiếp tục từ câu {completed_count + 1}\n")
    else:
        print(f"📋 Chưa có kết quả cũ, bắt đầu từ câu 1\n")

    # Chỉ lấy các câu chưa chạy
    remaining_dataset = dataset[completed_count:]

    chat_service = await build_chat_service()

    results = []
    try:
        # Mở ở chế độ APPEND ("a") để giữ nguyên kết quả cũ
        with open(OUTPUT_PATH, "a", encoding="utf-8") as out_f:
            for i, item in enumerate(remaining_dataset):
                absolute_idx = completed_count + i + 1
                print(f"[{absolute_idx}/{len(dataset)}] {item['question'][:60]}...")
                try:
                    result = await run_single_item(chat_service, item, ChatRequestCls)
                except Exception as exc:  # noqa: BLE001
                    print(f"    ❌ LỖI: {exc}")
                    result = {
                        "question": item["question"],
                        "error": str(exc),
                    }
                results.append(result)
                out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                out_f.flush()  # ghi ngay, không mất dữ liệu nếu crash giữa chừng
    finally:
        await cleanup()

    total_done = completed_count + len(results)
    print(f"\n✅ Hoàn tất. Kết quả lưu tại {OUTPUT_PATH}")
    print(f"Lần chạy này: {len(results)} câu mới | Tổng cộng: {total_done}/{len(dataset)}")
    n_errors = sum(1 for r in results if "error" in r)
    n_ask_user = sum(1 for r in results if r.get("ask_user"))
    print(f"Kết quả lần này: Lỗi: {n_errors} | Ask user: {n_ask_user}")
    print(f"Tổng Gemini API calls: {_gemini_call_count}")


if __name__ == "__main__":
    asyncio.run(main())