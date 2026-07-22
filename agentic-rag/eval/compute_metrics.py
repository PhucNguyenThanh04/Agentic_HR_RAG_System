"""
compute_metrics.py

Tổng hợp metrics từ file results.jsonl do run_eval.py sinh ra.

Giả định:
- Mỗi dòng jsonl có các field: question, employee_id, user_role, expected_tool,
  finish_reason, is_done, total_steps, tools_called và latency_ms.

Script chỉ đọc file cục bộ, không gọi API, Qdrant, Gemini hoặc so sánh
answer với ground_truth. File input không bị chỉnh sửa.

Usage:
    python compute_metrics.py results.jsonl
    python compute_metrics.py results.jsonl --output metrics_summary.json
    python compute_metrics.py results.jsonl --normalized-output results_normalized.jsonl
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
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # Nếu lỗi, có thể do dòng chứa nhiều JSON objects dính nhau
                # Thử giải mã tuần tự bằng raw_decode
                pos = 0
                objs = []
                while pos < len(line):
                    # Bỏ qua khoảng trắng
                    while pos < len(line) and line[pos].isspace():
                        pos += 1
                    if pos >= len(line):
                        break
                    try:
                        obj, idx = decoder.raw_decode(line, pos)
                        objs.append(obj)
                        pos = idx
                    except json.JSONDecodeError as e:
                        print(f"[WARN] Dòng {line_no} chứa JSON lỗi tại vị trí {pos}: {e}", file=sys.stderr)
                        break
                if objs:
                    rows.extend(objs)
    return rows


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

        # Chuẩn hoá expected thành danh sách các tool mong đợi
        if isinstance(expected, list):
            expected_list = expected
        elif isinstance(expected, str):
            expected_list = [expected]
        else:
            expected_list = []

        if not expected_list:
            continue

        if called and called[0] in expected_list:
            first_match += 1
        if any(t in called for t in expected_list):
            any_match += 1
    if total == 0:
        return {"total": 0, "first_call_accuracy": None, "any_call_accuracy": None}
    return {
        "total": total,
        "first_call_accuracy": round(first_match / total, 4),
        "any_call_accuracy": round(any_match / total, 4),
    }


def compute_breakdown_by_tool(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        expected = r.get("expected_tool")
        if isinstance(expected, list):
            key = ", ".join(expected)
        else:
            key = expected or "unknown"
        groups[key].append(r)

    breakdown = {}
    for tool, group_rows in groups.items():
        lat = [
            r["latency_ms"]
            for r in group_rows
            if isinstance(r.get("latency_ms"), (int, float))
        ]
        steps = [
            r["total_steps"]
            for r in group_rows
            if isinstance(r.get("total_steps"), (int, float))
        ]
        tool_m = compute_tool_metrics(group_rows)
        breakdown[tool] = {
            "count": len(group_rows),
            "tool_selection": tool_m,
            "avg_steps": round(statistics.mean(steps), 2) if steps else None,
            "latency_ms": latency_stats(lat),
        }
    return breakdown


def compute_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    ask_user_count = sum(1 for r in rows if r.get("finish_reason") == "ask_user")
    not_done = sum(1 for r in rows if not r.get("is_done", True))
    all_latencies = [
        r["latency_ms"]
        for r in rows
        if isinstance(r.get("latency_ms"), (int, float))
    ]
    all_steps = [
        r["total_steps"]
        for r in rows
        if isinstance(r.get("total_steps"), (int, float))
    ]

    return {
        "total_samples": total,
        "ask_user_rate": round(ask_user_count / total, 4) if total else None,
        "not_done_rate": round(not_done / total, 4) if total else None,
        "avg_steps": round(statistics.mean(all_steps), 2) if all_steps else None,
        "latency_ms": latency_stats(all_latencies),
        "tool_selection": compute_tool_metrics(rows),
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
    print("-- Breakdown theo expected_tool --")
    for tool, m in summary["breakdown_by_expected_tool"].items():
        print(f"\n[{tool}] (n={m['count']})")
        print(f"  tool_selection : {m['tool_selection']}")
        print(f"  avg_steps      : {m['avg_steps']}")
        print(f"  latency_ms     : {m['latency_ms']}")
    print("=" * 60)


def load_dataset_expected_tools() -> dict[str, Any]:
    """Đọc expected_tool từ tất cả dataset JSON cục bộ."""
    dataset_dir = Path(__file__).resolve().parent / "dataset"
    mapping: dict[str, Any] = {}
    for path in sorted(dataset_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[WARN] Không thể đọc dataset {path}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            expected_tool = item.get("expected_tool")
            if question and expected_tool:
                mapping[question] = expected_tool
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="Tổng hợp metrics từ results.jsonl")
    parser.add_argument(
        "results_path",
        type=Path,
        help="Đường dẫn tới file results.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Nếu set, ghi summary dạng JSON ra file này",
    )
    parser.add_argument(
        "--normalized-output",
        type=Path,
        default=None,
        help=(
            "Nếu set, ghi các record đã bổ sung total_steps, latency_ms, "
            "expected_tool và is_done ra một file JSONL mới"
        ),
    )
    args = parser.parse_args()

    if not args.results_path.exists():
        print(f"[ERROR] Không tìm thấy file: {args.results_path}", file=sys.stderr)
        sys.exit(1)

    rows = load_results(args.results_path)
    if not rows:
        print("[ERROR] File rỗng hoặc không parse được dòng nào.", file=sys.stderr)
        sys.exit(1)

    # Tự động tính toán/bổ sung các trường còn thiếu từ dataset gốc
    expected_tools_map = load_dataset_expected_tools()
    for r in rows:
        records = r.get("log_finish_records") or []

        # Lấy total_steps từ log FINISH cuối cùng nếu record chưa có.
        if r.get("total_steps") is None:
            total_steps = next(
                (
                    rec.get("total_steps")
                    for rec in reversed(records)
                    if isinstance(rec.get("total_steps"), (int, float))
                ),
                None,
            )
            r["total_steps"] = total_steps

        # Tính latency_ms từ log_finish_records
        if r.get("latency_ms") is None:
            total_sec = sum(
                rec.get("elapsed_seconds", 0.0)
                for rec in records
                if isinstance(rec.get("elapsed_seconds"), (int, float))
            )
            r["latency_ms"] = total_sec * 1000.0 if total_sec > 0 else None

        # Lấy expected_tool từ dataset gốc
        if r.get("expected_tool") is None and "question" in r:
            q = r["question"].strip()
            if q in expected_tools_map:
                r["expected_tool"] = expected_tools_map[q]
        expected_tool = r.get("expected_tool")
        if isinstance(expected_tool, str):
            r["expected_tool"] = [expected_tool]
        elif expected_tool is None:
            r["expected_tool"] = []

        # Gán is_done nếu thiếu
        if "is_done" not in r:
            r["is_done"] = "error" not in r

    summary = compute_summary(rows)
    print_report(summary)

    if args.normalized_output:
        args.normalized_output.parent.mkdir(parents=True, exist_ok=True)
        with args.normalized_output.open("w", encoding="utf-8") as output_file:
            for row in rows:
                output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\nĐã ghi records chuẩn hóa ra: {args.normalized_output}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nĐã ghi summary JSON ra: {args.output}")


if __name__ == "__main__":
    main()
