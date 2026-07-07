"""
compute_metrics.py

Tổng hợp metrics từ file results.jsonl do run_eval.py sinh ra.

Giả định:
- Mỗi dòng jsonl có các field: question, employee_id, user_role, expected_tool,
  ground_truth, final_answer, finish_reason, is_done, total_steps, tools_called,
  asked_user, retrieved_chunks, latency_ms, correct
- Field `correct` đã được gán tay: true / false / null (null = chưa chấm)
  Chấp nhận cả 1/0 hoặc "true"/"false" dạng string cho tiện khi sửa tay bằng text editor.

Không phụ thuộc RAGAS, không gọi Qdrant/Gemini. Chỉ đọc + tính toán.

Usage:
    python compute_metrics.py results.jsonl
    python compute_metrics.py results.jsonl --output metrics_summary.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_results(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] Bỏ qua dòng {line_no} (JSON lỗi): {e}", file=sys.stderr)
    return rows


def normalize_correct(value: Any) -> bool | None:
    """Chuẩn hoá field `correct` về True / False / None (chưa chấm)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "y", "đúng", "dung"):
            return True
        if v in ("false", "0", "no", "n", "sai"):
            return False
    print(f"[WARN] Giá trị 'correct' không nhận dạng được: {value!r} -> coi như chưa chấm", file=sys.stderr)
    return None


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def latency_stats(latencies: list[float]) -> dict[str, float]:
    if not latencies:
        return {"mean": float("nan"), "p50": float("nan"), "p95": float("nan"),
                "min": float("nan"), "max": float("nan")}
    return {
        "mean": round(statistics.mean(latencies), 1),
        "p50": round(percentile(latencies, 50), 1),
        "p95": round(percentile(latencies, 95), 1),
        "min": round(min(latencies), 1),
        "max": round(max(latencies), 1),
    }


def compute_tool_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Hai cách đo tool selection, báo cáo cả hai vì ý nghĩa khác nhau:
    - first_call_match: tool đầu tiên gọi có đúng expected_tool không (đo khả năng
      routing/reasoning đúng ngay từ đầu, quan trọng với ReAct agent)
    - any_call_match: expected_tool có xuất hiện ở bất kỳ bước nào không (đo agent
      có "tìm ra" đúng tool cuối cùng hay không, khoan dung hơn với retry)
    """
    first_match = 0
    any_match = 0
    total = 0
    for r in rows:
        expected = r.get("expected_tool")
        called = r.get("tools_called") or []
        if expected is None:
            continue
        total += 1
        if called and called[0] == expected:
            first_match += 1
        if expected in called:
            any_match += 1
    if total == 0:
        return {"total": 0, "first_call_accuracy": None, "any_call_accuracy": None}
    return {
        "total": total,
        "first_call_accuracy": round(first_match / total, 4),
        "any_call_accuracy": round(any_match / total, 4),
    }


def compute_correctness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    graded = []
    ungraded = 0
    for r in rows:
        c = normalize_correct(r.get("correct"))
        if c is None:
            ungraded += 1
        else:
            graded.append(c)
    if not graded:
        return {"graded": 0, "ungraded": ungraded, "accuracy": None}
    return {
        "graded": len(graded),
        "ungraded": ungraded,
        "accuracy": round(sum(graded) / len(graded), 4),
    }


def compute_breakdown_by_tool(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = r.get("expected_tool") or "unknown"
        groups[key].append(r)

    breakdown = {}
    for tool, group_rows in groups.items():
        lat = [r["latency_ms"] for r in group_rows if isinstance(r.get("latency_ms"), (int, float))]
        steps = [r["total_steps"] for r in group_rows if isinstance(r.get("total_steps"), (int, float))]
        tool_m = compute_tool_metrics(group_rows)
        correctness_m = compute_correctness(group_rows)
        breakdown[tool] = {
            "count": len(group_rows),
            "tool_selection": tool_m,
            "correctness": correctness_m,
            "avg_steps": round(statistics.mean(steps), 2) if steps else None,
            "latency_ms": latency_stats(lat),
        }
    return breakdown


def compute_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    ask_user_count = sum(1 for r in rows if r.get("finish_reason") == "ask_user")
    not_done = sum(1 for r in rows if not r.get("is_done", True))
    all_latencies = [r["latency_ms"] for r in rows if isinstance(r.get("latency_ms"), (int, float))]
    all_steps = [r["total_steps"] for r in rows if isinstance(r.get("total_steps"), (int, float))]

    return {
        "total_samples": total,
        "ask_user_rate": round(ask_user_count / total, 4) if total else None,
        "not_done_rate": round(not_done / total, 4) if total else None,
        "avg_steps": round(statistics.mean(all_steps), 2) if all_steps else None,
        "latency_ms": latency_stats(all_latencies),
        "tool_selection": compute_tool_metrics(rows),
        "correctness": compute_correctness(rows),
        "breakdown_by_expected_tool": compute_breakdown_by_tool(rows),
    }


def print_report(summary: dict[str, Any]) -> None:
    print("=" * 60)
    print("EVAL METRICS SUMMARY")
    print("=" * 60)
    print(f"Tổng số mẫu: {summary['total_samples']}")
    print(f"Tỷ lệ ask_user: {summary['ask_user_rate']}")
    print(f"Tỷ lệ chưa done (is_done=false): {summary['not_done_rate']}")
    print(f"Số bước trung bình: {summary['avg_steps']}")
    print(f"Latency (ms): {summary['latency_ms']}")
    print()
    print("-- Tool selection (toàn bộ) --")
    print(summary["tool_selection"])
    print()
    print("-- Correctness (toàn bộ, dựa trên field 'correct' đã gán tay) --")
    c = summary["correctness"]
    print(c)
    if c["ungraded"] > 0:
        print(f"[LƯU Ý] Còn {c['ungraded']} mẫu chưa được gán 'correct' -> chưa tính vào accuracy.")
    print()
    print("-- Breakdown theo expected_tool --")
    for tool, m in summary["breakdown_by_expected_tool"].items():
        print(f"\n[{tool}] (n={m['count']})")
        print(f"  tool_selection : {m['tool_selection']}")
        print(f"  correctness    : {m['correctness']}")
        print(f"  avg_steps      : {m['avg_steps']}")
        print(f"  latency_ms     : {m['latency_ms']}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tổng hợp metrics từ results.jsonl")
    parser.add_argument("results_path", type=Path, help="Đường dẫn tới file results.jsonl")
    parser.add_argument("--output", type=Path, default=None,
                         help="Nếu set, ghi summary dạng JSON ra file này")
    args = parser.parse_args()

    if not args.results_path.exists():
        print(f"[ERROR] Không tìm thấy file: {args.results_path}", file=sys.stderr)
        sys.exit(1)

    rows = load_results(args.results_path)
    if not rows:
        print("[ERROR] File rỗng hoặc không parse được dòng nào.", file=sys.stderr)
        sys.exit(1)

    summary = compute_summary(rows)
    print_report(summary)

    if args.output:
        args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nĐã ghi summary JSON ra: {args.output}")


if __name__ == "__main__":
    main()