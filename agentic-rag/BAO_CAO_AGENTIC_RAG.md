# BÁO CÁO CHI TIẾT DỰ ÁN: AGENTIC RAG — HỆ THỐNG TRỢ LÝ HR THÔNG MINH

---

## THÔNG TIN CHUNG

| Thông tin | Chi tiết |
|---|---|
| **Tên module** | Agentic RAG — HR Chatbot |
| **Thuộc dự án** | Face Attendance Management System |
| **Ngôn ngữ lập trình** | Python 3.11+ |
| **Framework** | FastAPI, Pydantic v2 |
| **Ngày báo cáo** | 15/07/2026 |

---

## 1. GIỚI THIỆU TỔNG QUAN

Module **Agentic RAG** là thành phần trí tuệ nhân tạo của hệ thống quản lý chấm công, đóng vai trò một **trợ lý HR thông minh** có khả năng trả lời câu hỏi tự nhiên của nhân viên về chính sách lao động, lịch chấm công, thông tin ca làm và các dữ liệu HR liên quan.

Điểm khác biệt cốt lõi so với chatbot truyền thống là module này kết hợp hai kỹ thuật tiên tiến:
- **Retrieval-Augmented Generation (RAG)**: Tìm kiếm tài liệu chính sách/pháp luật lao động để hỗ trợ trả lời
- **Agentic AI (ReAct loop)**: LLM tự lập kế hoạch, gọi công cụ tuần tự và suy luận từng bước để đưa ra câu trả lời chính xác

---

## 2. KIẾN TRÚC HỆ THỐNG

### 2.1 Sơ đồ tổng thể

```
User Request
     │
     ▼
┌─────────────────┐
│   FastAPI API   │  ← HTTP endpoint /api/v1/chat
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│          ChatService                │
│  (Điều phối toàn bộ luồng xử lý)  │
└────────┬──────────┬─────────────────┘
         │          │
         ▼          ▼
┌──────────────┐  ┌──────────────────┐
│  Supervisor  │  │ RetrievalPipeline│
│ (ReAct Loop) │  │ (RAG Pipeline)   │
└──────┬───────┘  └──────┬───────────┘
       │                 │
       ▼                 ▼
┌──────────────┐  ┌──────────────────┐
│ GeminiClient │  │ HybridRetriever  │
│ (Google LLM) │  │ (Dense + Sparse) │
└──────────────┘  └──────┬───────────┘
                         │
                   ┌─────┴────┐
                   ▼          ▼
            ┌──────────┐ ┌──────────┐
            │  Qdrant  │ │ Reranker │
            │(Vector DB│ │(BGE-v2-m3│
            └──────────┘ └──────────┘
```

### 2.2 Cấu trúc thư mục

```
agentic-rag/
├── src/
│   ├── agents/           # ReAct agent core
│   │   ├── supervisor.py     # Vòng lặp ReAct chính
│   │   ├── executor.py       # Thực thi công cụ
│   │   ├── state.py          # Trạng thái agent
│   │   └── pending_store.py  # Lưu trạng thái đa lượt
│   ├── rag/
│   │   ├── embeddings/       # Embedding model (BGE-M3)
│   │   ├── ingestion/        # Pipeline nạp tài liệu
│   │   └── retrieval/        # Hybrid retrieval + reranker
│   ├── integrations/
│   │   ├── llm/              # Google Gemini client
│   │   ├── qdrant/           # Vector database
│   │   ├── cache/            # Redis
│   │   └── api_service/      # Kết nối API backend
│   ├── tools/                # Tool definitions
│   ├── features/             # Chat/document features
│   ├── core/                 # Settings, logging
│   └── main.py               # FastAPI app entry
├── eval/                 # Bộ đánh giá chất lượng
│   ├── dataset/              # Tập câu hỏi kiểm thử
│   ├── run_eval.py           # Chạy đánh giá end-to-end
│   ├── compute_metrics.py    # Tổng hợp metrics
│   └── ragas_eval.py         # Đánh giá RAGAS
└── requirements.txt
```

---

## 3. CÁC THÀNH PHẦN KỸ THUẬT CHÍNH

### 3.1 ReAct Agent Loop (Supervisor)

**File:** `src/agents/supervisor.py`

Đây là thành phần trung tâm, triển khai vòng lặp **ReAct (Reasoning + Acting)**:

```
Mỗi iteration:
  1. Gọi LLM → nhận JSON {thought, action, action_input}
  2. Phân tích action:
     - "final_answer" → kết thúc, trả lời user
     - "ask_user"     → hỏi thêm, lưu pending state
     - <tool_name>    → thực thi tool, nhận observation
  3. Append observation vào scratchpad
  4. Lặp lại (tối đa max_steps = 5 bước)
```

**Cơ chế bảo vệ đặc biệt:**
- **Duplicate Guard**: Chặn agent gọi cùng một tool với cùng input nhiều lần, tránh vòng lặp vô tận
- **LLM Truncation Recovery**: Tự động retry khi Gemini cắt output do vượt token limit
- **Step Budget Hint**: Cảnh báo agent khi còn ≤ 2 bước, buộc đưa ra `final_answer`
- **Max ask_user limit**: Giới hạn 2 lần hỏi thêm user, tránh chatbot hỏi liên tục

**Hai mode hoạt động:**
- `run()`: Trả về `AgentState` sau khi hoàn thành (batch mode)
- `stream()`: Yield từng event real-time qua Server-Sent Events (streaming mode)

### 3.2 Hệ thống Tool (Tools Registry)

**File:** `src/tools/`

Agent có quyền truy cập các tool sau:

| Tool | Mô tả | Nguồn dữ liệu |
|------|--------|---------------|
| `vector_search` | Tìm kiếm tài liệu chính sách/pháp luật | Qdrant vector DB |
| `employee_query` | Tra cứu thông tin nhân viên đang đăng nhập | API Service |
| `attendance_query` | Kiểm tra lịch sử chấm công | API Service |
| `shift_query` | Xem thông tin ca làm việc | API Service |
| `ask_user` | Yêu cầu user cung cấp thêm thông tin | Interactive |

Mỗi tool trả về `ToolResult` gồm: `observation`, `outcome` (success/empty/error), `retryable`, `citations`, `low_confidence`.

### 3.3 RAG Pipeline — Hybrid Retrieval

**File:** `src/rag/retrieval/`

Pipeline truy xuất tài liệu gồm 3 giai đoạn:

**Bước 1 — Hybrid Retriever (`hybrid_retriever.py`)**
- Embed câu hỏi thành **dense vector** (BAAI/bge-m3) và **sparse vector** (BM25-style)
- Tìm kiếm hybrid trên Qdrant: kết hợp semantic similarity + keyword matching
- Áp dụng **permission filter** (allowed_role) ngay trong query để kiểm soát truy cập tài liệu

**Bước 2 — Reranker (`reranker.py`)**
- Model: `BAAI/bge-reranker-v2-m3` (FlagEmbedding)
- Cross-encoder reranking: tính relevance score cho từng cặp (query, passage)
- Chạy trong ThreadPoolExecutor (model không thread-safe), non-blocking với asyncio
- Sắp xếp lại kết quả, cắt top_n

**Bước 3 — Quality Filter + Context Builder (`retrieval_pipeline.py`)**
- Lọc chunks có score ≥ `retrieval_score_threshold`
- Phát hiện **score spread**: nếu spread > 0.3, chỉ giữ chunks trong top 0.1 điểm
- Đánh dấu `low_confidence = True` nếu chỉ có 1 chunk đủ điều kiện
- Xây dựng context string với citation index [1], [2], ...

### 3.4 LLM Client — Google Gemini

**File:** `src/integrations/llm/client.py`

`GeminiClient` bao gồm:
- `generate_json()`: Gọi Gemini với `response_mime_type = application/json` để đảm bảo JSON output
- `generate_stream()`: Stream text chunks qua async generator
- Phát hiện `finish_reason = MAX_TOKENS` → raise `LLMTruncatedError`
- Tất cả I/O chạy qua `asyncio.to_thread()` (SDK là sync) + `asyncio.wait_for()` timeout

### 3.5 Prompt Engineering

**File:** `src/integrations/llm/prompts.py`

Hệ thống prompt được thiết kế kỹ lưỡng:

**System Prompt (REACT_SYSTEM_PROMPT):**
- Định nghĩa format output JSON tuyệt đối (không có text thừa trước/sau JSON)
- Quy tắc bảo mật: từ chối tra cứu nhân viên khác, không bịa dữ liệu
- Chiến lược chọn tool và xử lý lỗi tool
- Suy luận thời gian tự động (hôm qua, tuần trước, tháng này → ngày cụ thể)
- Prompt injection protection: bỏ qua lệnh đổi role trong Observation

**PromptMemoryConfig:**
Kiểm soát token budget cho từng phần của prompt:
- `window_steps = 2`: Chỉ đưa 2 bước gần nhất vào scratchpad (tránh overflow)
- Per-tool observation limits: attendance (3000 chars), vector_search (1500 chars), etc.
- Truncation tự động với marker `[truncated, original_length=N]`

### 3.6 Bảo mật và Kiểm soát Truy cập

**Guardrails được triển khai ở nhiều tầng:**

1. **Prompt-level**: Quy tắc cứng trong system prompt — agent phải từ chối mọi yêu cầu về nhân viên khác. Bất kỳ ID nào xuất hiện trong câu hỏi đều bị coi là ID người khác (người dùng không bao giờ cần tự cung cấp ID của mình)
2. **Tool-level**: Tool API không nhận `employee_id` từ LLM — luôn dùng ID từ JWT token (authenticated user)
3. **Vector DB-level**: Permission filter theo `user_role` ngay trong Qdrant query
4. **Pending State Security**: Kiểm tra `employee_id` và `user_role` khớp trước khi resume pending state

### 3.7 Pending State — Hỗ trợ Multi-turn

**File:** `src/agents/pending_store.py`

Khi agent cần hỏi thêm user (`ask_user`):
1. Serialize toàn bộ `AgentState` (steps, scratchpad, context) → lưu Redis với TTL
2. Trả về câu hỏi cho user
3. Khi user trả lời: load state từ Redis, inject câu trả lời vào bước `ask_user`, tiếp tục loop

---

## 4. PIPELINE NẠP TÀI LIỆU (INGESTION)

**File:** `src/rag/ingestion/`

Quy trình xử lý tài liệu pháp lý/chính sách:

1. **Loader Factory**: Hỗ trợ PDF (`pypdf`) và DOCX (`python-docx`)
2. **Legal Structure-Aware Chunker** (`legachunker.py`): Chunker đặc biệt nhận biết cấu trúc văn bản pháp lý (điều, khoản, điểm), tránh cắt giữa điều khoản
3. **Document Indexer**: Embed từng chunk → upsert vào Qdrant với metadata (filename, page, section, clause_number, allowed_role)
4. **Batch Processing**: Upsert theo batch (`qdrant_upsert_batch_size`) để tránh timeout

---

## 5. ĐÁNH GIÁ CHẤT LƯỢNG (EVALUATION)

### 5.1 Bộ dữ liệu kiểm thử

**File:** `eval/dataset/newdata.json`

- Tập câu hỏi đa dạng về pháp luật lao động (Bộ luật Lao động 2019), chính sách nội bộ, chấm công
- Mỗi mẫu gồm: `question`, `employee_id`, `user_role`, `ground_truth`, `source_reference`, `expected_tool`, `category`
- Có hỗ trợ `simulated_followup` cho các câu hỏi multi-turn (agent hỏi lại user)

### 5.2 Quy trình đánh giá

**File:** `eval/run_eval.py`

Script đánh giá end-to-end với production code (không mock):

- **Chạy thật**: Gọi `ChatService.chat()` thực sự — embedding, Qdrant, Gemini, Reranker đều hoạt động
- **Rate limiting thông minh**: Monkey-patch `GeminiClient._call_once()` để áp dụng rate limit ở tầng mỗi lệnh Gemini API (bao gồm cả các bước bên trong ReAct loop), không phải chỉ ở tầng `chat()` call
- **Retry Gemini 429**: Đọc `Retry-After` từ exception để chờ đúng thời gian, fallback exponential backoff (tối đa 120s)
- **Log capture**: Bắt dòng `[FINISH]` từ logger để trích xuất `total_steps`, `tools_called`, `finish_reason` chính xác
- **Progressive save**: Ghi kết quả từng câu ngay sau khi xử lý xong (không mất dữ liệu nếu crash)
- **Resume**: Tự động tiếp tục từ câu bị dừng giữa chừng

### 5.3 Metrics đánh giá

**File:** `eval/compute_metrics.py`

| Metric | Mô tả |
|--------|--------|
| **Tool Selection Accuracy** | Tỷ lệ chọn đúng tool đầu tiên (first_call) và bất kỳ bước nào (any_call) |
| **Correctness** | So sánh câu trả lời với ground_truth, dùng Gemini làm judge tự động |
| **Avg Steps** | Số bước trung bình của ReAct loop |
| **Latency (ms)** | Mean, P50, P95, min, max thời gian phản hồi |
| **Ask User Rate** | Tỷ lệ câu hỏi cần hỏi thêm |

**Breakdown theo category và expected_tool** để phân tích chi tiết hiệu suất từng loại câu hỏi.

### 5.4 Đánh giá RAGAS

**File:** `eval/ragas_eval.py`, `ragas_summary.json`

Sử dụng framework **RAGAS** để đánh giá chất lượng RAG theo 4 chiều:

| Metric | Giá trị | Mô tả |
|--------|---------|--------|
| **Faithfulness** | **0.888** | Câu trả lời trung thực với context tìm được |
| **Answer Relevancy** | **0.698** | Mức độ liên quan của câu trả lời với câu hỏi |
| **Context Precision** | **0.947** | Độ chính xác của context được truy xuất |
| **Context Recall** | **0.933** | Tỷ lệ thông tin cần thiết có trong context |

> **Tập đánh giá RAGAS:** 15 mẫu, 13 completed, 10 evaluated

**Nhận xét:**
- Context Precision (0.947) và Context Recall (0.933) rất cao → pipeline RAG hybrid + reranker hoạt động tốt, tìm đúng tài liệu
- Faithfulness (0.888) cao → agent ít bịa thông tin, trung thực với dữ liệu tìm được
- Answer Relevancy (0.698) thấp hơn → một số câu trả lời chưa trả lời trực tiếp câu hỏi (do thiếu chunk, agent nói "không tìm thấy")

---

## 6. CÔNG NGHỆ SỬ DỤNG

| Thành phần | Công nghệ | Phiên bản |
|-----------|-----------|-----------|
| Web Framework | FastAPI | 0.111.0 |
| LLM | Google Gemini | gemini-1.5-flash |
| Embedding Model | BAAI/bge-m3 | FlagEmbedding 1.4.0 |
| Reranker Model | BAAI/bge-reranker-v2-m3 | FlagEmbedding 1.4.0 |
| Vector Database | Qdrant | qdrant-client 1.10.1 |
| Cache / State Store | Redis | redis-py 5.2.1 |
| HTTP Client | httpx | 0.28.1 |
| Config Management | Pydantic Settings | 2.14.2 |
| PDF Parser | pypdf | 4.2.0 |
| DOCX Parser | python-docx | 1.1.2 |
| Deep Learning | PyTorch (CUDA) | via base image |
| Evaluation | RAGAS | custom |

---

## 7. QUY TRÌNH HOẠT ĐỘNG TỔNG THỂ (END-TO-END)

### Luồng xử lý một câu hỏi điển hình

```
User: "Hôm nay tôi có đi trễ không?"

Step 1 [LLM reasoning]:
  Thought: "Cần biết ca làm của user hôm nay trước"
  Action: shift_query
  → API Service → Trả về ca 8:00-17:00

Step 2 [LLM reasoning]:
  Thought: "Có ca rồi, cần xem giờ check-in thực tế"
  Action: attendance_query {date: "2026-07-15"}
  → API Service → Trả về check-in: 8:15

Step 3 [LLM reasoning]:
  Thought: "Check-in 8:15, ca bắt đầu 8:00 → đi trễ 15 phút"
  Action: final_answer
  → "Hôm nay bạn đã đến muộn 15 phút. Ca làm của bạn bắt đầu lúc 8:00, nhưng bạn check-in lúc 8:15."
```

### Luồng xử lý câu hỏi chính sách

```
User: "Lương thử việc tối thiểu là bao nhiêu phần trăm?"

Step 1 [LLM reasoning]:
  Thought: "Câu hỏi về chính sách/luật lao động, dùng vector_search"
  Action: vector_search {query: "lương thử việc tối thiểu phần trăm"}
  → Qdrant hybrid search → Reranker → Top chunks từ Bộ luật Lao động 2019

Step 2 [LLM reasoning]:
  Thought: "Đã có thông tin từ tài liệu, đủ để trả lời"
  Action: final_answer
  → "Theo Điều 26 của Bộ luật Lao động [1], tiền lương thử việc do hai bên
     thỏa thuận nhưng ít nhất phải bằng 85% mức lương của công việc đó."
```

---

## 8. ĐIỂM NỔI BẬT VÀ ĐỔI MỚI

### 8.1 Thiết kế Agentic thay vì Pipeline cứng

Thay vì pipeline RAG cố định (query → retrieve → generate), hệ thống sử dụng **ReAct agent** cho phép:
- Kết hợp nhiều nguồn dữ liệu (vector DB + REST API) trong một lượt hội thoại
- Tự quyết định thứ tự gọi tool dựa trên context
- Tự phát hiện thiếu thông tin và hỏi thêm user khi cần

### 8.2 Hybrid Search với Permission Control

Kết hợp dense + sparse vectors cho truy xuất chính xác hơn so với chỉ dùng semantic search thuần túy. Permission filter được thực thi ngay tại Qdrant query, đảm bảo không rò rỉ tài liệu nội bộ.

### 8.3 Bảo mật đa tầng cho HR Chatbot

Trong bối cảnh HR, dữ liệu nhạy cảm của từng nhân viên cần được bảo vệ nghiêm ngặt. Hệ thống triển khai guardrail ở 3 tầng độc lập (prompt, tool, database) để tránh một tầng bị bypass dẫn đến lộ dữ liệu.

### 8.4 Legal Structure-Aware Chunking

Chunker tùy chỉnh nhận biết cấu trúc văn bản pháp lý (Điều/Khoản/Điểm), tránh cắt giữa một điều khoản hoàn chỉnh — đây là yếu tố quan trọng để RAG trả lời chính xác các câu hỏi pháp lý.

### 8.5 Rate-limit Aware Evaluation

Pipeline đánh giá tự động xử lý rate limit của Gemini API bằng cách áp dụng giới hạn tốc độ ở tầng mỗi lệnh API call (không phải mỗi lần chat), đọc `Retry-After` từ exception để tránh chờ quá lâu hoặc quá ngắn.

---

## 9. HẠN CHẾ VÀ HƯỚNG PHÁT TRIỂN

### Hạn chế hiện tại

| Hạn chế | Nguyên nhân |
|---------|-------------|
| Answer Relevancy chưa cao (0.698) | Chunking chưa tối ưu với văn bản pháp lý dài, agent đôi khi không tìm đủ chunk |
| Latency còn cao (~10-60s/câu) | Phụ thuộc Gemini API free tier (rate limit 15 RPM) |
| Số bước cứng tối đa 5 bước | Câu hỏi phức tạp có thể cần nhiều bước hơn |
| RAGAS chỉ evaluate 10/15 mẫu | Một số mẫu không có context (API-only questions) |

### Hướng phát triển

1. **Fine-tuning embedding model** trên domain HR/pháp luật lao động Việt Nam để tăng retrieval accuracy
2. **Multi-collection Qdrant**: Tách riêng collection cho từng loại tài liệu (luật lao động, nội quy công ty, BHXH)
3. **Caching layer**: Cache kết quả vector search cho các câu hỏi phổ biến
4. **Nâng cấp LLM**: Dùng Gemini Pro hoặc model tự host để giảm latency và tăng giới hạn tốc độ
5. **Self-reflection**: Thêm bước agent tự đánh giá câu trả lời trước khi trả về

---

## 10. KẾT LUẬN

Module Agentic RAG đã xây dựng thành công một hệ thống trợ lý HR thông minh với:

- **Kiến trúc hoàn chỉnh** từ ingestion tài liệu → hybrid retrieval → reranking → agentic reasoning → streaming response
- **Chất lượng RAG đo được**: Context Precision 94.7%, Context Recall 93.3%, Faithfulness 88.8%
- **Bảo mật nghiêm ngặt** đặc biệt quan trọng trong môi trường HR
- **Pipeline đánh giá tự động** đầy đủ (end-to-end eval + RAGAS)
- **Code production-ready**: Async hoàn toàn, error handling kỹ lưỡng, observability (structured logging, agent trace)

Hệ thống cho thấy khả năng ứng dụng thực tế của kiến trúc Agentic RAG trong bài toán HR chatbot, đặc biệt là khả năng kết hợp linh hoạt giữa tài liệu tĩnh (chính sách, pháp luật) và dữ liệu động (chấm công, ca làm, thông tin nhân viên) trong cùng một luồng hội thoại.

---

*Báo cáo được soạn thảo ngày 15/07/2026*
