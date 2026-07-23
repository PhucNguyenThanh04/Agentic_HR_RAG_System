# 🤖 Agentic HR RAG System

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Gemini_API-8E75B2?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?style=flat&logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

Agentic HR RAG System là trợ lý AI cho nhân viên và HR: tra cứu chính sách nội bộ, hỏi dữ liệu cá nhân, và làm rõ câu hỏi nhiều lượt bằng ReAct Agent. Hệ thống dùng FastAPI, Gemini API, Qdrant, Redis, PostgreSQL và React/Vite.

## TL;DR

Một hệ thống HR chatbot theo kiến trúc multi-service: Core Backend xác thực JWT và giữ identity, Agentic Service chạy ReAct + RAG để chọn tool phù hợp. Phù hợp cho bài toán HR tiếng Việt cần vừa đọc chính sách, vừa truy vấn dữ liệu nghiệp vụ có phân quyền.

## Features

- ReAct Agent tự chọn tool: `vector_search`, `employee_query`, `shift_query`,
  `attendance_query`, `ask_user`.
- RAG tiếng Việt với BGE-M3 dense+sparse, Qdrant hybrid search, RRF và reranking.
- Multi-turn clarification bằng Redis Pending Store khi câu hỏi thiếu thông tin.
- Core Backend xác thực JWT, truyền `employee_id` và `user_role` đã xác thực sang Agentic Service.
- Agentic Service không nhận identity từ prompt người dùng, giảm rủi ro prompt injection.
- API chat thường và streaming SSE cho frontend.

## Table of Contents

- [Demo](#demo)
- [Architecture](#architecture)
- [RAG Pipeline](#rag-pipeline)
- [Evaluation](#evaluation)
- [Engineering Notes / Lessons Learned](#engineering-notes--lessons-learned)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Roadmap](#roadmap)
- [License / Contributing / Contact](#license--contributing--contact)

## Demo

**Video demo:** https://www.youtube.com/watch?v=RRrTFc2tXjM

<!-- TODO: thêm screenshot dashboard -->

## Architecture

### System Architecture

![System Architecture](./docs/System_Architecture.png)

- **Frontend -> Core Backend (`api-service`)**: client gọi API, Core Backend xác thực JWT và xác định `employee_id`, `role`.
- **Core Backend -> Agentic Service (`agentic-rag`)**: gửi câu hỏi cùng identity đã xác thực; Agentic Service không tự nhận identity từ prompt.
- **Agentic Service -> Gemini API**: chạy ReAct loop (`Thought -> Action -> Observation -> Final Answer`).
- **Agentic Service -> Qdrant**: tìm kiếm chính sách bằng hybrid search và reranking.
- **Agentic Service -> Redis**: lưu pending state khi `ask_user` cần hỏi lại người dùng.
- **Agentic Service -> Core Backend**: truy vấn dữ liệu nghiệp vụ qua API tool; backend vẫn là lớp kiểm soát dữ liệu.
- **Core Backend -> PostgreSQL/Redis**: lưu nghiệp vụ HR, conversation, session/cache/rate-limit.

### ReAct Architecture

![ReAct Agent Architecture](./docs/ReAct.png)

- **Thought**: LLM phân tích câu hỏi, lịch sử chat và observation gần nhất.
- **Action**: LLM chọn tool từ registry và sinh `action_input` dạng JSON.
- **Observation**: Executor chạy tool thật, trả kết quả về state.
- **Final Answer**: LLM tổng hợp câu trả lời cuối cùng, kèm citation nếu dùng context.

### Tool Registry

| Tool | Input chính | Output | Dùng khi |
|---|---|---|---|
| `vector_search` | `{ "query": "..." }` | `ToolResult` gồm observation, citations, `used_context`, `low_confidence` | Tra cứu chính sách, nội quy, quy trình đã index trong Qdrant. |
| `employee_query` | `employee_id` tùy chọn | Hồ sơ nhân viên theo scope đã được API kiểm tra | Tra cứu mã nhân viên, họ tên, trạng thái, phòng ban, chức vụ, quản lý hoặc thông tin liên hệ. |
| `shift_query` | `employee_id`, `as_of` tùy chọn | Ca làm tại ngày cần tra cứu | Tra cứu giờ bắt đầu/kết thúc, ngưỡng đi trễ/về sớm hoặc số phút làm việc yêu cầu. |
| `attendance_query` | Khoảng ngày, trạng thái và các bộ lọc tùy chọn | Danh sách bản ghi chấm công | Tra cứu check-in/check-out, đi trễ, về sớm, ngày công hoặc trạng thái chấm công. |
| `ask_user` | `question`, `options`, `allow_free_text` | Signal `__ASK_USER__{...}` để lưu pending state | Câu hỏi thiếu mốc thời gian, loại phép, hoặc điều kiện cần làm rõ. |


### Multi-turn Clarification

- `ask_user` trả về payload hỏi lại người dùng, không cố đoán.
- Supervisor dừng vòng ReAct, lưu `AgentState` vào Redis Pending Store.
- Khi người dùng trả lời, Agentic Service resume state cũ và tiếp tục loop.

## RAG Pipeline

![RAG Pipeline](./docs/RAG_Pipeline.png)

- **1. Indexing**: tài liệu HR/pháp lý được chunk theo cấu trúc Điều/Khoản; BGE-M3 tạo dense vector + sparse vector; metadata có `allowed_roles`.
- **2. Retrieval**: BGE-M3 encode query; Qdrant hybrid search dùng dense+sparse với RRF; filter `allowed_roles` ngay ở query; lấy **20 chunk** ứng viên.
- **3. Reranking**: BGE-Reranker-v2-m3 rerank 20 chunk còn **5 chunk**; confidence filter dùng `RETRIEVAL_SCORE_THRESHOLD` để tránh context yếu.

## Evaluation

Kết quả dưới đây được tổng hợp từ các artifact hiện có trong
[`agentic-rag/eval/results`](./agentic-rag/eval/results). Bộ đánh giá gồm hai
phần:

- **Agent metrics**: chạy luồng `ChatService` thật, không mock, để đo khả năng
  hoàn thành, chọn tool, số bước và latency trên 82 test case.
- **RAGAS**: đánh giá các test case `vector_search` bằng Groq
  `llama-3.3-70b-versatile` làm judge LLM và BGE-M3 làm embedding model.

### Kết quả tổng quan

| Chỉ số | Kết quả |
|---|---:|
| Tổng số test case | **82** |
| Tỷ lệ hoàn thành (`is_done=true`) | **100.00%** |
| Tỷ lệ kết thúc với `ask_user` | **2.44% (2/82)** |
| Số bước trung bình | **2.08** |
| First-call tool accuracy | **92.68% (76/82)** |
| Any-call tool accuracy | **92.68% (76/82)** |

`First-call tool accuracy` đo tỷ lệ tool đầu tiên khớp `expected_tool`.
`Any-call tool accuracy` đo tỷ lệ tool mong đợi xuất hiện ở bất kỳ bước nào
trong ReAct loop. Hai chỉ số bằng nhau trên lần chạy này.

### Kết quả theo expected tool

| Expected tool | Số mẫu | First-call accuracy | Any-call accuracy | Số bước TB | Latency TB |
|---|---:|---:|---:|---:|---:|
| `vector_search` | 68 | 92.65% | 92.65% | 2.10 | 16,455.2 ms |
| `employee_query` | 5 | 80.00% | 80.00% | 1.80 | 16,751.6 ms |
| `shift_query` | 3 | 100.00% | 100.00% | 2.00 | 9,758.0 ms |
| `attendance_query` | 5 | 100.00% | 100.00% | 2.00 | 42,065.8 ms |
| `shift_query` hoặc `attendance_query` | 1 | 100.00% | 100.00% | 3.00 | 15,324.0 ms |

Với test case có nhiều `expected_tool`, metric hiện tại tính là đúng khi agent
gọi một trong các tool được kỳ vọng; metric này không yêu cầu gọi đủ tất cả
tool trong danh sách.

### Latency

| Chỉ số | Thời gian |
|---|---:|
| Trung bình | **17,861.8 ms** |
| P50 | **10,136.0 ms** |
| P95 | **54,311.2 ms** |
| Nhỏ nhất | **5,178.0 ms** |
| Lớn nhất | **94,922.0 ms** |

### RAGAS

| Metric | Điểm | Phần trăm |
|---|---:|---:|
| Faithfulness | **0.9005** | **90.05%** |
| Answer relevancy | **0.8018** | **80.18%** |
| Context precision | **0.9490** | **94.90%** |
| Context recall | **0.9075** | **90.75%** |

RAGAS nhận 68 dòng `vector_search` hợp lệ. Trong đó có một câu hỏi bị lặp,
nên kết quả gồm 67 mẫu duy nhất đã đánh giá thành công, không có mẫu thất bại
hoặc bị bỏ qua. Vì summary lấy 68 dòng hợp lệ trừ 67 khóa kết quả duy nhất,
`n_remaining=1` là hệ quả của cơ chế deduplicate/resume, không phải một mẫu
duy nhất chưa được đánh giá.

### Nhận xét và phạm vi diễn giải

- `context_precision` là metric RAGAS cao nhất, đạt 94.90%;
  `answer_relevancy` thấp nhất, đạt 80.18%.
- `employee_query` có tool accuracy thấp nhất (80.00%), nhưng tập này chỉ có
  5 mẫu.
- `attendance_query` có latency trung bình cao nhất (42.07 giây) và P95 đạt
  92.59 giây.
- 2.44% là **tỷ lệ xuất hiện `ask_user` trên toàn bộ tập**, không phải độ chính
  xác phát hiện câu hỏi mơ hồ. Muốn đo clarification accuracy cần một tập mẫu
  được gán nhãn riêng cho trường hợp cần/không cần hỏi lại.

Chi tiết đầy đủ xem tại
[`agentic-rag/eval/report.md`](./agentic-rag/eval/report.md). Số liệu nguồn:
[`metrics_summary.json`](./agentic-rag/eval/results/metrics_summary.json) và
[`ragas_summary_run2.json`](./agentic-rag/eval/results/ragas_summary_run2.json).

## Engineering Notes / Lessons Learned

### Bug: Query Rewriting làm degrade retrieval

Trong quá trình phát triển Agentic Multi-turn, một vấn đề nghiêm trọng xuất hiện ở bước **Query Rewriting**.

- **Vấn đề**: ở các lượt hội thoại tiếp theo, LLM khi gọi `vector_search` thường tự viết lại câu hỏi bằng từ đồng nghĩa hoặc rút gọn ngữ cảnh. Ví dụ: từ *"quy định nghỉ thai sản"* thành *"chế độ sinh đẻ"*. Điều này làm lệch embedding BGE-M3 so với từ khóa pháp lý trong tài liệu gốc, dẫn tới degrade retrieval.
- **Cách fix**: `VectorSearchTool` nhận thêm `original_query` từ request gốc. Khi LLM gọi query đã rewrite, tool chạy retrieval cho cả query rewrite và `original_query`, sau đó chọn kết quả có score tốt nhất.
- **Bài học**: với RAG tiếng Việt/pháp lý, query rewrite không luôn tốt. Giữ lại câu hỏi thô giúp bảo toàn keyword nghiệp vụ và giảm lỗi ở multi-turn.

## Tech Stack

| Layer | Công nghệ | Vai trò |
|---|---|---|
| Core Backend | FastAPI, SQLAlchemy, Alembic, Pydantic v2, Uvicorn | REST API, JWT auth, phân quyền, nghiệp vụ HR, migration. |
| Agentic Service | FastAPI, Gemini API, custom ReAct loop | Reasoning, tool dispatch, final answer, streaming. |
| RAG | Qdrant, BGE-M3, BGE-Reranker-v2-m3, FlagEmbedding | Hybrid retrieval, dense+sparse vectors, reranking. |
| State & Data | PostgreSQL, Redis | Database nghiệp vụ, cache/session, pending agent state. |
| Infra | Docker Compose, CUDA/NVIDIA Container Toolkit | Chạy local multi-service, GPU cho embedding/reranker. |

## Project Structure

### agentic-rag — Agentic Service (port 8081)

```text
agentic-rag/
├── src/
│   ├── agents/                        # ReAct Agent core
│   │   ├── supervisor.py              # Chạy ReAct loop: Thought → Action → Observation → Final Answer
│   │   ├── executor.py                # Gọi tool thật từ registry, trả observation
│   │   ├── state.py                   # AgentState: giữ history, scratchpad, metadata qua các bước
│   │   └── pending_store.py           # Lưu/resume AgentState vào Redis khi ask_user
│   │
│   ├── tools/                         # Tool registry & implementations
│   │   ├── registry.py                # Map tên tool → class, cung cấp danh sách cho prompt
│   │   ├── base_tool.py               # BaseTool abstract class
│   │   ├── vector_search_tool.py      # Gọi retrieval pipeline, trả context + citations
│   │   ├── ask_user_tool.py           # Sinh signal __ASK_USER__ để hỏi lại người dùng
│   │   └── api_queries/               # Nhóm tool truy vấn dữ liệu qua api-service
│   │       ├── attendance_tool.py     # Lịch sử chấm công, check-in/check-out
│   │       ├── employee_tool.py       # Thông tin nhân viên (tên, phòng ban, chức vụ)
│   │       ├── shift_tool.py          # Ca làm việc, lịch trực
│   │       ├── schemas.py             # Pydantic schemas cho API response
│   │       ├── formatters.py          # Format dữ liệu API thành text cho LLM
│   │       └── errors.py              # Error handling cho API tool
│   │
│   ├── rag/                           # RAG Pipeline
│   │   ├── embeddings/
│   │   │   ├── embedding_client.py    # BGE-M3 client: dense + sparse vectors
│   │   │   └── embedding_service.py   # Singleton quản lý model lifecycle
│   │   ├── ingestion/
│   │   │   ├── pipeline.py            # Orchestrate load → chunk → index
│   │   │   ├── indexer.py             # Upsert vectors + metadata vào Qdrant
│   │   │   ├── chunkers/              # Chunk theo Điều/Khoản cho tài liệu pháp lý
│   │   │   └── loaders/               # Load PDF/DOCX/TXT
│   │   └── retrieval/
│   │       ├── retrieval_pipeline.py  # Orchestrate retrieve → rerank → build context
│   │       ├── hybrid_retriever.py    # Qdrant hybrid search (dense + sparse + RRF)
│   │       ├── reranker.py            # BGE-Reranker-v2-m3 rerank + confidence filter
│   │       ├── context_builder.py     # Ghép chunks thành context string + citations
│   │       └── schemas.py             # RetrievalResult, Citation, ContextChunk
│   │
│   ├── integrations/                  # External service clients
│   │   ├── llm/
│   │   │   ├── client.py             # Gemini API client (generate, parse JSON)
│   │   │   └── prompts.py            # System prompt, ReAct format, tool descriptions
│   │   ├── qdrant/
│   │   │   ├── client.py             # Qdrant connection singleton
│   │   │   └── store.py              # Collection CRUD, search, upsert
│   │   ├── cache/
│   │   │   └── redis_client.py       # Redis connection cho pending state
│   │   └── api_service/
│   │       ├── clients.py            # HTTP client gọi api-service internal endpoints
│   │       └── schemas.py            # Response schemas từ api-service
│   │
│   ├── api/v1/                        # FastAPI routers
│   │   ├── chat_router.py            # POST /chat, /chat/stream (nhận từ api-service)
│   │   └── document_router.py        # POST /documents/ingest
│   │
│   ├── features/                      # Business logic layer
│   │   ├── chat/
│   │   │   ├── service.py            # ChatService: orchestrate agent + streaming
│   │   │   └── schemas.py            # ChatRequest, ChatResponse
│   │   └── documents/
│   │       ├── service.py            # DocumentService: trigger ingestion pipeline
│   │       └── schemas.py
│   │
│   ├── observability/
│   │   └── agent_logs.py             # Structured logging cho ReAct steps
│   │
│   ├── core/
│   │   ├── settings.py               # Pydantic Settings (env vars)
│   │   ├── dependenci.py             # FastAPI dependency injection
│   │   └── setup_logging.py          # Logging configuration
│   │
│   ├── utils/
│   │   ├── datetime_utils.py         # Timezone helpers cho dữ liệu HR
│   │   └── enums.py                  # Shared enums (ToolName, FinishReason...)
│   │
│   └── main.py                       # FastAPI app entrypoint
│
├── eval/                              # RAGAS evaluation scripts & results
├── Dockerfile
└── requirements.txt
```

### api-service — Các phần liên quan đến Agentic RAG (port 8000)

```text
api-service/
├── src/
│   ├── api/v1/features/
│   │   ├── chat/                     # Proxy: nhận message từ frontend, gọi agentic-rag
│   │   ├── attendance/               # CRUD chấm công — agentic-rag gọi qua api_queries
│   │   ├── shifts/                   # Ca làm việc — agentic-rag gọi qua api_queries
│   │   ├── staff/                    # Thông tin nhân viên — agentic-rag gọi qua api_queries
│   │   ├── leaves/                   # Nghỉ phép
│   │   ├── corrections/              # Đơn điều chỉnh chấm công
│   │   └── auth/                     # JWT auth, xác định employee_id trước khi gọi agent
│   │
│   ├── core/
│   │   ├── clients/chatbox/          # HTTP client gọi agentic-rag (internal, X-API-Key)
│   │   ├── security/                 # JWT verify, RBAC
│   │   └── middleware/               # Rate-limit, CORS, request logging
│   │
│   └── main.py
│
├── alembic/                          # Database migrations
└── Dockerfile
```

## Getting Started

### Prerequisites

- Docker & Docker Compose.
- NVIDIA Container Toolkit nếu muốn chạy embedding/reranker bằng GPU.
- Node.js + npm nếu chạy frontend local.
- Gemini API key cho `agentic-rag`.

### Installation

**Bước 1: Cấu hình biến môi trường**

```bash
cp api-service/.env.example api-service/.env
cp agentic-rag/.env.example agentic-rag/.env

# fill các biến theo .env.example

```

Đảm bảo `RAG_API_KEY` giống nhau ở `api-service/.env` và `agentic-rag/.env`.

**Bước 2: Khởi động backend qua Docker Compose**

```bash
docker compose up -d --build
```

Lệnh này chạy PostgreSQL, Redis, Qdrant, `api-service` và `agentic-rag`.

**Bước 3: Khởi chạy frontend**

```bash
cd web-dashboard
npm install
npm run dev
```

Frontend mặc định chạy ở URL Vite in ra terminal, thường là `http://localhost:5173`.

### Try the API

Luồng public nên đi qua Core Backend vì JWT ở đây xác định identity. Agentic Service là internal service và được bảo vệ bằng `X-API-Key`.

**1. Login**

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "Admin12345"
  }'
```

Response rút gọn:

```json
{
  "access_token": "<JWT>",
  "refresh_token": "<REFRESH_TOKEN>",
  "token_type": "bearer"
}
```

**2. Tạo conversation**

```bash
curl -s -X POST http://localhost:8000/api/v1/chat/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Hỏi chính sách nghỉ phép"}'
```

Response rút gọn:

```json
{
  "id": "<conversation_id>",
  "employee_id": "<employee_id>",
  "title": "Hỏi chính sách nghỉ phép"
}
```

**3. Gửi message**

```bash
curl -s -X POST http://localhost:8000/api/v1/chat/<conversation_id>/messages \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Quy định nghỉ thai sản như thế nào?"
  }'
```

Response rút gọn:

```json
{
  "answer": "Theo tài liệu ... [1]",
  "citations": [
    {
      "index": 1,
      "filename": "policy.pdf",
      "page": 12,
      "score": 0.82
    }
  ],
  "used_context": true,
  "ask_user": false,
  "finish_reason": "answer"
}
```

**Streaming SSE**

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/<conversation_id>/messages/stream \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hôm nay tôi làm ca nào?"}'
```

### Ports

| Service | Host port | Container port | Mô tả |
|---|---:|---:|---|
| PostgreSQL | `5433` | `5432` | Database nghiệp vụ. |
| Redis | `6379` | `6379` | Cache, session, pending state. |
| Qdrant HTTP | `6333` | `6333` | Vector database HTTP API. |
| Qdrant gRPC | `6334` | `6334` | Vector database gRPC API. |
| api-service | `8000` | `8000` | Core Backend. |
| agentic-rag | `8081` | `8081` | Agentic Service. |
| web-dashboard | `5173` | N/A | Vite dev server khi chạy local. |
