# 🤖 Agentic HR RAG System

**Trợ lý AI đa công cụ (Multi-Tool AI Agent) hỗ trợ nhân viên tra cứu chính sách HR và truy vấn dữ liệu cá nhân**, sử dụng kiến trúc ReAct Agent kết hợp RAG pipeline tối ưu cho tiếng Việt (hybrid search + reranking) và Redis-based multi-turn clarification.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Gemini_API-8E75B2?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?style=flat&logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

**Video demo:** 🔗 https://www.youtube.com/watch?v=RRrTFc2tXjM

## 1. Problem Statement

### Vì sao cần kiến trúc Agent

Bài toán thực tế đòi hỏi hệ thống phải **tự quyết định**: câu hỏi này cần tra cứu văn bản chính sách (retrieval), hay cần truy vấn dữ liệu cá nhân qua hệ thống backend (tool call), hay câu hỏi chưa đủ rõ và cần hỏi lại người dùng trước khi hành động. Đây chính là lý do dự án thiết kế một **ReAct Agent đa công cụ (multi-tool)** thay vì một RAG pipeline tuyến tính:

- **Vector Search Tool** — xử lý câu hỏi về nội dung chính sách/quy định (retrieval trên tài liệu HR/pháp lý tiếng Việt)
- **API Query Database Tool** — xử lý câu hỏi cần dữ liệu cá nhân, gắn với danh tính đã xác thực của nhân viên
- **Ask User Tool** — xử lý trường hợp câu hỏi mơ hồ, cần agent chủ động hỏi lại thay vì đoán bừa

Việc để agent tự suy luận (reasoning) và chọn đúng tool, thay vì hard-code luồng xử lý, giúp hệ thống mở rộng linh hoạt hơn khi có thêm loại câu hỏi mới trong tương lai — đồng thời đặt ra bài toán kỹ thuật quan trọng: làm sao đảm bảo agent không bị "dắt mũi" bởi input người dùng để truy cập sai phạm vi dữ liệu (điều được giải quyết ở phần Security-first Controls bên dưới).


## 2. System Architecture

![System Architecture](./docs/System_Architecture.png)

Hệ thống được chia thành 2 dịch vụ độc lập giao tiếp qua HTTP: **Core Backend** (`api-service`) và **Agentic Service** (`agentic-rag`).

### Luồng dữ liệu (Data Flow)

1. **Frontend ➔ Core Backend**: Người dùng gửi yêu cầu. Core Backend xác thực JWT và xác định danh tính/quyền hạn (`employee_id`, `role`).
2. **Core Backend ➔ Agentic Service**: Chuyển tiếp câu hỏi cùng danh tính đã xác thực. Agentic Service không tự nhận diện danh tính từ prompt của người dùng để tránh giả mạo (prompt injection).
3. **Agentic Service ↔ Gemini API**: Thực hiện vòng lặp ReAct (Thought ➔ Action ➔ Observation) để quyết định bước xử lý tiếp theo.
4. **Agentic Service ↔ Qdrant**: Thực hiện tìm kiếm lai (Hybrid Search bằng BGE-M3 + Rerank) trong kho tri thức nội bộ.
5. **Agentic Service ↔ Redis (Pending State)**: Lưu trạng thái hội thoại tạm thời khi cần hỏi lại người dùng (`ask_user`), giúp hệ thống stateless và dễ scale ngang.
6. **Agentic Service ➔ Core Backend**: Khi cần dữ liệu cá nhân (phép, chấm công, ca làm...), Agent gọi ngược lại Core Backend qua API Query Tool để nhận dữ liệu có cấu trúc an toàn.
7. **Core Backend ↔ PostgreSQL & Redis**: Quản lý session/rate-limit qua Redis và lưu trữ cơ sở dữ liệu nghiệp vụ chính trên PostgreSQL.


## 3. ReAct Agent Architecture

![ReAct Agent Architecture](./docs/ReAct.png)

Hệ thống sử dụng mô hình **ReAct (Reasoning + Acting)** để Agent tự động lập luận và đưa ra chuỗi hành động tối ưu nhằm giải quyết yêu cầu của nhân viên.

### Vòng lặp ReAct (ReAct Loop)

*   **Thought (Suy nghĩ)**: Agent (LLM) phân tích câu hỏi và lịch sử trò chuyện để xác định thông tin còn thiếu hoặc bước xử lý tiếp theo.
*   **Action (Hành động)**: Lựa chọn một công cụ (Tool) phù hợp từ registry và chuẩn hóa tham số đầu vào dưới dạng JSON.
*   **Observation (Quan sát)**: `Executor` chạy công cụ và trả về kết quả thực tế (Observation). Dữ liệu này được đưa ngược vào context để LLM suy luận ở bước kế tiếp.
*   **Final Answer**: Khi đã tích lũy đủ thông tin từ các Observation, Agent kết thúc vòng lặp và tổng hợp câu trả lời cuối cùng gửi tới người dùng.

### Danh sách Công cụ (Tool Registry)

*   `vector_search`: Truy vấn tài liệu quy định, chính sách nội bộ trên Qdrant.
*   `api_query_database`: Tra cứu thông tin trong database
*   `ask_user`: Tạm dừng vòng lặp để yêu cầu người dùng làm rõ câu hỏi khi thông tin bị mơ hồ.

### Cơ chế làm rõ hội thoại (Multi-turn Clarification)

Khi công cụ `ask_user` được kích hoạt:
1. Agentic Service tạm dừng uvicorn process, đóng gói toàn bộ trạng thái suy nghĩ hiện tại (`AgentState`) và lưu vào **Redis Pending Store** (TTL 30 phút).
2. Khi người dùng phản hồi câu hỏi làm rõ, Agentic Service nhận diện trạng thái chờ từ Redis, tải lại `AgentState` cũ và tiếp tục vòng lặp ReAct ban đầu mà không phải suy luận lại từ đầu.

## 4. RAG Pipeline

![RAG Pipeline](./docs/RAG_Pipeline.png)


Quy trình RAG (Retrieval-Augmented Generation) được thiết kế tối ưu cho tiếng Việt, kết hợp tìm kiếm ngữ nghĩa chuyên sâu và cơ chế lọc bảo mật đa lớp:

*   **1. Indexing (Đóng gói tri thức)**: Tài liệu HR và văn bản quy định được trích xuất văn bản, phân đoạn (chunking) theo cấu trúc Điều/Khoản (tránh cắt ngang làm mất ngữ cảnh pháp lý). Các phân đoạn này được mã hóa (encode) bằng mô hình **BGE-M3** thành các đại diện Dense + Sparse Vector kèm siêu dữ liệu phân quyền `allowed_roles` và lưu trữ vào Qdrant.
*   **2. Retrieval (Truy xuất lai bảo mật)**: Câu hỏi của nhân viên được mã hóa qua BGE-M3. Hệ thống thực hiện tìm kiếm lai (Hybrid Search kết hợp Dense + Sparse qua cơ chế RRF), đồng thời lọc theo quyền hạn (`allowed_role`) ngay tại tầng truy vấn của Qdrant (lớp bảo mật thứ hai sau bước kiểm tra session ở Core Backend). Bước này truy xuất ra **20 chunk** ứng viên tiềm năng để cân bằng giữa độ bao phủ (recall) và chi phí tài nguyên xử lý ở bước sau.
*   **3. Reranking & Filtering (Tái xếp hạng & Lọc tin cậy)**: 20 chunk ứng viên tiếp tục đi qua mô hình **BGE-Reranker-v2-m3** (mô hình Cross-Encoder tính toán tương tác trực tiếp câu hỏi - văn bản, tăng độ chính xác so với tính Cosine Similarity thông thường) để chọn ra **5 chunk** phù hợp nhất. Bộ lọc tin cậy (**Confidence Filter**) sẽ loại bỏ tiếp các chunk dưới ngưỡng điểm an toàn — đảm bảo Agent thà từ chối trả lời còn hơn sử dụng ngữ cảnh yếu gây ra hiện tượng ảo giác (hallucination).
## 5. Evaluation

Hệ thống được đánh giá hiệu năng dựa trên bộ tiêu chuẩn **RAGAS** (sử dụng Gemini-1.5-Flash làm Judge LLM) kết hợp cùng một số chỉ số tùy chỉnh dành riêng cho Agent (Custom Agent Metrics):

### Bảng chỉ số đánh giá (Evaluation Metrics)

| Chỉ số (Metrics) | Điểm số | Ý nghĩa kỹ thuật |
|---|---|---|
| **Faithfulness** (Độ trung thực) | **0.89** | Đo lường mức độ câu trả lời được suy ra hoàn toàn từ Context được cung cấp (tránh hallucination). |
| **Answer Relevancy** (Độ liên quan) | **0.70** | Đánh giá câu trả lời có trực tiếp giải quyết đúng trọng tâm câu hỏi của người dùng hay không. |
| **Context Precision** (Độ chuẩn xác Context) | **0.95** | Đo lường xem các chunk thực sự liên quan có được Reranker đưa lên các vị trí đầu tiên hay không. |
| **Context Recall** (Độ phủ Context) | **0.93** | Đánh giá tỷ lệ thông tin cần thiết trong tài liệu gốc được truy xuất thành công. |
| **Tool Dispatch Accuracy** (Custom) | **92%** | Tỷ lệ Agent gọi chính xác công cụ nghiệp vụ (`vector_search` vs `api_query_database`). |
| **Clarification Rate** (Custom) | **15%** | Tỷ lệ Agent kích hoạt `ask_user` thành công khi gặp các câu hỏi mơ hồ, thay vì đoán mò. |

### Phát hiện kỹ thuật thú vị khi Debug (Engineering Notes)

Trong quá trình phát triển hệ thống Agentic Multi-turn, một vấn đề nghiêm trọng đã được phát hiện ở bước **Query Rewriting**:
*   **Vấn đề**: Ở các lượt hội thoại tiếp theo (multi-turn), LLM (Supervisor) khi suy luận để gọi `vector_search` thường tự động viết lại câu hỏi ban đầu bằng các từ đồng nghĩa hoặc rút gọn ngữ cảnh (ví dụ: chuyển từ *"quy định nghỉ thai sản"* sang *"chế độ sinh đẻ"*). Việc này vô tình làm lệch phân phối embedding của mô hình BGE-M3 so với từ khóa pháp lý trong tài liệu gốc, dẫn đến **suy giảm nghiêm trọng hiệu năng truy xuất (degrade retrieval)**.
*   **Giải pháp xử lý**: Trong file `vector_search_tool.py`, hệ thống không chỉ tìm kiếm bằng câu truy vấn do LLM viết lại, mà luôn đính kèm cả **câu truy vấn thô ban đầu của người dùng** (`original_query`). Trình truy xuất sẽ chạy song song cả hai truy vấn, sau đó tổng hợp kết quả và ưu tiên đoạn văn bản có điểm tương quan cao nhất. Giải pháp này giúp giữ nguyên các từ khóa cốt lõi của người dùng, khôi phục lại độ chính xác của RAG pipeline.

## 6. Tech Stack

Dưới đây là các công nghệ và thư viện cốt lõi được sử dụng trong dự án, phân nhóm theo các lớp kiến trúc:

| Lớp kiến trúc (Layer) | Công nghệ / Thư viện sử dụng | Vai trò trong hệ thống |
|---|---|---|
| **Core Backend** | FastAPI, SQLAlchemy, Alembic, Uvicorn, Pydantic v2 | Xây dựng RESTful API, quản lý xác thực người dùng (JWT), phân quyền dữ liệu, quản lý và tự động hóa migration cơ sở dữ liệu. |
| **AI-Agent** | Gemini API (Google Generative AI), Custom ReAct loop | Triển khai mô hình tác tử tự suy luận và lập luận hành động (Thought -> Action -> Observation). |
| **Retrieval (RAG)** | Qdrant, BGE-M3 (FlagEmbedding), BGE-Reranker-v2-m3 | Cơ sở dữ liệu vector lưu trữ tri thức, mô hình sinh embedding lai (dense + sparse), và mô hình cross-encoder tái xếp hạng kết quả chính xác cao. |
| **Infrastructure** | Docker, Docker Compose, Redis, PostgreSQL, CUDA 11.8 | Đóng gói ứng dụng dạng containerized, bộ nhớ lưu trữ phiên hội thoại & trạng thái chờ (Redis), cơ sở dữ liệu nghiệp vụ (Postgres), chạy tăng tốc phần cứng (GPU Laptop RTX 3050). |

## 7. Project Structure

Cấu trúc phân mục của dự án được tổ chức rõ ràng theo mô hình Microservices:

```text
hr_bot/
├── agentic-rag/              # Dịch vụ trí tuệ nhân tạo & AI Agent (Cổng 8081)
│   ├── src/
│   │   ├── agents/           # Bộ điều phối Agent (Supervisor, Executor, AgentState)
│   │   ├── integrations/     # Kết nối API ngoài (Gemini API Client, Qdrant Client)
│   │   ├── rag/              # Quy trình RAG (Retrieval Pipeline, Hybrid Retriever, Reranker)
│   │   ├── tools/            # Công cụ của Agent (vector_search, api_queries, ask_user)
│   │   └── main.py           # Điểm khởi chạy FastAPI của Agent Service
│   ├── Dockerfile            # Container build CUDA 11.8 cho Agent
│   └── requirements.txt      # Thư viện phục vụ AI/RAG
├── api-service/              # Dịch vụ Core Backend nghiệp vụ (Cổng 8000)
│   ├── alembic/              # Quản lý lịch sử và file cấu hình di cư DB (migration)
│   ├── src/
│   │   ├── api/              # Định nghĩa router & logic nghiệp vụ (Auth, Nhân viên, Chấm công, Chat...)
│   │   ├── core/             # Cấu hình hệ thống (DB setup, Redis Cache, JWT, HTTP Chatbox Client)
│   │   └── main.py           # Điểm chạy FastAPI chính
│   ├── Dockerfile            # Container build backend Python 3.10
│   └── requirements.txt      # Thư viện core backend
├── web-dashboard/            # Giao diện người dùng Frontend (Vite + React + TypeScript)
│   ├── src/                  # Chứa giao diện chatbox và bảng quản trị của HR
│   ├── package.json          # Quản lý package Node.js
│   └── vite.config.ts        # File cấu hình build Vite
├── docker-compose.yml        # Định nghĩa orchestrator cho các container (đầy đủ GPU link & dependencies)
└── README.md                 # Tài liệu hướng dẫn dự án
```

## 8. Setup & Quick Start

### Yêu cầu hệ thống (Prerequisites)
*   **Docker & Docker Compose** đã cài đặt.
*   **NVIDIA Container Toolkit** (nếu muốn tăng tốc GPU laptop/PC).

### Các bước cài đặt và vận hành

**Bước 1: Cấu hình biến môi trường**
Tạo và chỉnh sửa file cấu hình môi trường cho từng service dựa trên file mẫu:
*   Tại thư mục `api-service/`: Tạo file `.env` từ `.env.example`.
*   Tại thư mục `agentic-rag/`: Tạo file `.env` từ `.env.example`. 

*(Đảm bảo đã điền thông tin khoá `GOOGLE_API_KEY` (Gemini API Key) đầy đủ trong file `.env` của `agentic-rag`)*

**Bước 2: Khởi động hệ thống Backend qua Docker Compose**
Chạy lệnh sau tại thư mục gốc dự án để tự động build và chạy toàn bộ dịch vụ phụ trợ (`PostgreSQL`, `Redis`, `Qdrant`), `api-service`, và `agentic-rag`:
```bash
sudo docker compose up -d --build
```

**Bước 3: Khởi chạy Giao diện (Frontend)**
Mở một terminal mới trên máy host, di chuyển vào thư mục Frontend và khởi chạy:
```bash
cd web-dashboard
npm install
npm run dev
```

Truy cập địa chỉ local hiển thị trên terminal (thường là `http://localhost:5173`) để bắt đầu trải nghiệm trợ lý HR!



