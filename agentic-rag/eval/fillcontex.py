"""
Enrich eval_results.jsonl với nội dung text thật của context, lấy từ Qdrant
theo chunk_id đã có sẵn trong citations. Chạy sau khi run_eval.py hoàn tất.

Cách dùng:
    python fillcontex.py

Input:  eval_results_pretty.json hoặc eval_results.jsonl (có citations[].chunk_id, KHÔNG có contexts)
Output: eval_results_enriched.jsonl (có thêm field "contexts": [text, text, ...])
"""

import json
import sys
from pathlib import Path
from typing import Any
from qdrant_client import QdrantClient

# Đảm bảo thư mục gốc agentic-rag nằm trong sys.path để import "src.*" hoạt động
_EVAL_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _EVAL_DIR.parent  # agentic-rag/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.settings import get_settings

INPUT_PATH = _EVAL_DIR / "eval_results_pretty.json"
OUTPUT_PATH = _EVAL_DIR / "eval_results_enriched.jsonl"

TEXT_PAYLOAD_FIELD = "content"


def build_qdrant_client():
    """Khởi tạo Qdrant client đồng bộ."""
    settings = get_settings()
    qdrant_client = QdrantClient(
        url=settings.qdrant_url,
        timeout=settings.qdrant_timeout,
    )
    return qdrant_client, settings.default_qdrant_collection


def load_records(path: Path) -> list[dict[str, Any]]:
    """Đọc JSONL, JSON array, hoặc nhiều JSON object pretty-format."""
    if not path.exists():
        # Thử fallback sang eval_results.jsonl nếu không có pretty.json
        fallback_path = path.parent / "eval_results.jsonl"
        if fallback_path.exists():
            path = fallback_path
        else:
            raise FileNotFoundError(f"Không tìm thấy file kết quả tại {path} hoặc {fallback_path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if text.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("JSON array phải là list object.")
        return data

    # Thử đọc JSONL trước
    rows: list[dict[str, Any]] = []
    jsonl_ok = True

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                jsonl_ok = False
                break
            rows.append(obj)
        except json.JSONDecodeError:
            jsonl_ok = False
            break

    if jsonl_ok and rows:
        return rows

    # Đọc nhiều JSON object pretty-format liên tiếp
    decoder = json.JSONDecoder()
    idx = 0
    rows = []

    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break

        obj, end = decoder.raw_decode(text, idx)
        if not isinstance(obj, dict):
            raise ValueError(f"Object tại vị trí {idx} không phải JSON object.")
        rows.append(obj)
        idx = end

    return rows


def fetch_contexts_for_chunk_ids(qdrant_client, collection_name: str, chunk_ids: list[str]) -> dict[str, str]:
    """
    Lấy text thật cho danh sách chunk_id, trả về dict {chunk_id: text}.
    Dùng retrieve theo batch id để giảm số lần gọi Qdrant.
    """
    if not chunk_ids:
        return {}

    points = qdrant_client.retrieve(
        collection_name=collection_name,
        ids=chunk_ids,
        with_payload=True,
    )

    result = {}
    for point in points:
        text = point.payload.get(TEXT_PAYLOAD_FIELD)
        if text is None:
            print(f"  ⚠️  chunk_id={point.id} không có field '{TEXT_PAYLOAD_FIELD}' trong payload")
            text = ""
        result[str(point.id)] = text

    # Cảnh báo nếu có chunk_id không tìm thấy trong Qdrant (đã bị xóa / sai id)
    found_ids = {str(p.id) for p in points}
    missing = set(chunk_ids) - found_ids
    if missing:
        print(f"  ⚠️  Không tìm thấy {len(missing)} chunk_id trong Qdrant: {missing}")

    return result


def main():
    qdrant_client, collection_name = build_qdrant_client()

    records = load_records(INPUT_PATH)
    print(f"Đã load {len(records)} record")

    # Gom toàn bộ chunk_id duy nhất trước, fetch 1 lần (tránh gọi Qdrant lặp lại
    # cho cùng 1 chunk xuất hiện ở nhiều câu hỏi khác nhau)
    all_chunk_ids = set()
    for record in records:
        for citation in record.get("citations", []):
            if "chunk_id" in citation:
                all_chunk_ids.add(citation["chunk_id"])

    print(f"Cần fetch {len(all_chunk_ids)} chunk_id duy nhất từ Qdrant (Collection: {collection_name})...")
    chunk_id_to_text = fetch_contexts_for_chunk_ids(qdrant_client, collection_name, list(all_chunk_ids))

    n_missing_text = 0
    with open(OUTPUT_PATH, "w", encoding="utf-8") as out_f:
        for record in records:
            contexts = []
            for citation in record.get("citations", []):
                text = chunk_id_to_text.get(citation.get("chunk_id"), "")
                if not text:
                    n_missing_text += 1
                contexts.append(text)
            record["contexts"] = contexts
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n✅ Hoàn tất. Ghi ra {OUTPUT_PATH}")
    if n_missing_text:
        print(f"⚠️  Có {n_missing_text} context bị rỗng hoặc không tìm thấy payload — kiểm tra lại TEXT_PAYLOAD_FIELD hoặc chunk_id.")


if __name__ == "__main__":
    main()