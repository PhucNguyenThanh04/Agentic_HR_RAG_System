# Evaluation Report

## Tổng quan

| Chỉ số | Kết quả |
|---|---:|
| Tổng số test case | 82 |
| Tỷ lệ hoàn thành (`is_done=true`) | 100.00% |
| Tỷ lệ yêu cầu người dùng bổ sung thông tin (`ask_user`) | 2.44% (2/82) |
| Số bước trung bình | 2.08 |
| Độ chính xác chọn tool ở lần gọi đầu tiên | 92.68% (76/82) |
| Độ chính xác chọn tool ở bất kỳ lần gọi nào | 92.68% (76/82) |

## Latency

| Chỉ số | Thời gian |
|---|---:|
| Trung bình | 17,861.8 ms |
| P50 | 10,136.0 ms |
| P95 | 54,311.2 ms |
| Nhỏ nhất | 5,178.0 ms |
| Lớn nhất | 94,922.0 ms |

## Kết quả theo expected tool

| Expected tool | Số mẫu | First-call accuracy | Any-call accuracy | Số bước TB | Latency TB | P50 | P95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `vector_search` | 68 | 92.65% | 92.65% | 2.10 | 16,455.2 ms | 10,192.0 ms | 49,581.8 ms |
| `employee_query` | 5 | 80.00% | 80.00% | 1.80 | 16,751.6 ms | 10,115.0 ms | 42,149.6 ms |
| `shift_query` | 3 | 100.00% | 100.00% | 2.00 | 9,758.0 ms | 9,726.0 ms | 10,000.5 ms |
| `attendance_query` | 5 | 100.00% | 100.00% | 2.00 | 42,065.8 ms | 14,955.0 ms | 92,588.8 ms |
| `shift_query`, `attendance_query` | 1 | 100.00% | 100.00% | 3.00 | 15,324.0 ms | 15,324.0 ms | 15,324.0 ms |

## RAGAS Evaluation

RAGAS được chạy trên tập `vector_search` bằng Groq `llama-3.3-70b-versatile` và embedding BGE-M3.

| Metric | Điểm | Phần trăm |
|---|---:|---:|
| Faithfulness | 0.9005 | 90.05% |
| Answer relevancy | 0.8018 | 80.18% |
| Context precision | 0.9490 | 94.90% |
| Context recall | 0.9075 | 90.75% |

### Trạng thái RAGAS

| Chỉ số | Số lượng |
|---|---:|
| Tổng số dòng đầu vào | 68 |
| Dòng hợp lệ | 68 |
| Mẫu duy nhất đã đánh giá thành công | 67 |
| Mẫu thất bại | 0 |
| Mẫu bị bỏ qua do dữ liệu không hợp lệ | 0 |

Tập đầu vào có một câu hỏi bị lặp, vì vậy 68 dòng chỉ tương ứng với 67 mẫu duy nhất. Trường `n_remaining=1` trong `ragas_summary_run2.json` là hệ quả của cách summary lấy 68 dòng hợp lệ trừ 67 khóa kết quả duy nhất; không có mẫu duy nhất nào còn thiếu kết quả.

## Nhận xét

- Khả năng chọn tool tổng thể đạt 92.68%; `shift_query` và `attendance_query` đạt 100% trên tập hiện tại.
- `employee_query` có độ chính xác chọn tool thấp nhất, đạt 80.00%, nhưng chỉ được đo trên 5 mẫu.
- `attendance_query` có latency trung bình cao nhất, 42.07 giây, và P95 đạt 92.59 giây.
- Trong các chỉ số RAGAS, context precision cao nhất ở mức 94.90%; answer relevancy thấp nhất ở mức 80.18%.

## Nguồn số liệu

- `results/metrics_summary.json`
- `results/ragas_summary_run2.json`
- `results/ragas_results_run2.jsonl`
