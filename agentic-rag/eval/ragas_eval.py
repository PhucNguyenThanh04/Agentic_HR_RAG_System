from __future__ import annotations

import argparse
import json
import math
import os
import sys
import types
import inspect
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def install_ragas_langchain_compat() -> None:
    """Let RAGAS 0.4.x import with newer langchain-community releases.

    RAGAS 0.4.3 imports langchain_community.chat_models.vertexai at module load
    time. Newer langchain-community releases removed that legacy path. This eval
    script uses Gemini via langchain_google_genai, so the VertexAI class is only
    needed as an import-time type placeholder inside RAGAS.
    """
    module_name = "langchain_community.chat_models.vertexai"
    try:
        __import__(module_name)
        return
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise

    module = types.ModuleType(module_name)

    class ChatVertexAI:
        pass

    module.ChatVertexAI = ChatVertexAI
    sys.modules[module_name] = module


install_ragas_langchain_compat()

from datasets import Dataset
from dotenv import load_dotenv
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from ragas.run_config import RunConfig


METRICS = {
    "faithfulness": faithfulness,
    "answer_relevancy": answer_relevancy,
    "context_precision": context_precision,
    "context_recall": context_recall,
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def ragas_uses_legacy_schema() -> bool:
    """RAGAS 0.1.x expects question/answer/contexts/ground_truth columns."""
    try:
        raw_version = version("ragas")
    except PackageNotFoundError:
        return False

    parts = raw_version.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return False

    return (major, minor) < (0, 2)


def build_evaluator_models() -> tuple[Any, Any] | tuple[None, None]:
    """Build Gemini judge LLM and BGE-M3 embeddings for RAGAS."""
    load_dotenv(PROJECT_ROOT / ".env")

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        return None, None

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise RuntimeError(
            "GOOGLE_API_KEY đã có nhưng thiếu package langchain_google_genai. "
            "Cài thêm: pip install langchain-google-genai"
        ) from exc

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu HuggingFace embeddings integration. "
                "Cài thêm: pip install langchain-huggingface sentence-transformers"
            ) from exc

    llm_model = (
        os.getenv("RAGAS_GEMINI_MODEL")
        or os.getenv("GEMINI_MODEL")
        or "gemini-1.5-flash"
    )
    embedding_model = (
        os.getenv("RAGAS_EMBEDDING_MODEL")
        or os.getenv("EMBEDDING_MODEL")
        or "BAAI/bge-m3"
    )
    embedding_device = (
        os.getenv("RAGAS_EMBEDDING_DEVICE")
        or os.getenv("EMBEDDING_DEVICE")
        or "cpu"
    )
    temperature = float(os.getenv("RAGAS_LLM_TEMPERATURE", os.getenv("LLM_TEMPERATURE", "0")))
    timeout = float(os.getenv("RAGAS_LLM_TIMEOUT", os.getenv("LLM_TIMEOUT", "60")))

    llm = ChatGoogleGenerativeAI(
        model=llm_model,
        google_api_key=google_api_key,
        temperature=temperature,
        timeout=timeout,
    )
    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model,
        model_kwargs={"device": embedding_device},
        encode_kwargs={"normalize_embeddings": True},
    )
    print(
        "Using models for RAGAS | "
        f"judge_llm={llm_model} | embeddings={embedding_model} | device={embedding_device}"
    )
    return llm, embeddings


def load_records(path: Path) -> list[dict[str, Any]]:
    """Đọc JSONL, JSON array, hoặc nhiều JSON object pretty-format."""
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


def build_ragas_dataset(records: list[dict[str, Any]]) -> tuple[Dataset, list[dict[str, Any]], list[dict[str, Any]]]:
    """Map input của bạn sang schema đúng với phiên bản RAGAS đang cài."""
    ragas_rows: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    legacy_schema = ragas_uses_legacy_schema()

    for idx, row in enumerate(records):
        question = row.get("question")
        answer = row.get("answer") or row.get("final_answer")
        reference = row.get("ground_truth") or row.get("ground_truth_answer")
        contexts = row.get("contexts") or row.get("retrieved_contexts")

        reasons = []
        if not question:
            reasons.append("missing question")
        if not answer:
            reasons.append("missing answer/final_answer")
        if not reference:
            reasons.append("missing ground_truth/ground_truth_answer")
        if not isinstance(contexts, list) or not contexts:
            reasons.append("contexts must be a non-empty list[str]")
        elif not all(isinstance(c, str) and c.strip() for c in contexts):
            reasons.append("contexts must contain only non-empty strings")

        if reasons:
            skipped.append({
                "index": idx,
                "question": question,
                "reasons": reasons,
            })
            continue

        if legacy_schema:
            ragas_rows.append({
                "question": question,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": reference,
            })
        else:
            ragas_rows.append({
                "user_input": question,
                "response": answer,
                "retrieved_contexts": contexts,
                "reference": reference,
            })
        kept.append(row)

    return Dataset.from_list(ragas_rows), kept, skipped


def sample_key(row: dict[str, Any]) -> str:
    """Stable key for resume/dedupe across repeated eval runs."""
    payload = {
        "question": row.get("question"),
        "answer": row.get("answer") or row.get("final_answer"),
        "ground_truth": row.get("ground_truth") or row.get("ground_truth_answer"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def is_failed_result(row: dict[str, Any]) -> bool:
    return row.get("ragas_status") == "failed" or bool(row.get("ragas_error"))


def load_completed_results(
    path: Path,
    *,
    retry_failed: bool = False,
) -> tuple[set[str], list[dict[str, Any]]]:
    if not path.exists():
        return set(), []

    completed_keys: set[str] = set()
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(f"Warning: bỏ qua dòng output lỗi JSON tại {path}:{line_no}")
                continue
            rows.append(row)
            if not (retry_failed and is_failed_result(row)):
                completed_keys.add(sample_key(row))

    return completed_keys, rows


def clean_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json_value(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        try:
            return clean_json_value(value.item())
        except ValueError:
            pass
    return value


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean_row = clean_json_value(row)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(clean_row, ensure_ascii=False) + "\n")
        f.flush()


def write_summary(
    path: Path,
    result_rows: list[dict[str, Any]],
    metric_names: list[str],
    *,
    n_total: int,
    n_valid: int,
    n_skipped: int,
) -> None:
    latest_by_key: dict[str, dict[str, Any]] = {}
    for row in result_rows:
        latest_by_key[sample_key(row)] = row

    completed_rows = list(latest_by_key.values())
    successful_rows = [row for row in completed_rows if not is_failed_result(row)]
    failed_rows = [row for row in completed_rows if is_failed_result(row)]

    summary: dict[str, Any] = {}
    for metric in metric_names:
        values = [
            row.get(metric)
            for row in successful_rows
            if isinstance(row.get(metric), (int, float))
            and not math.isnan(float(row.get(metric)))
        ]
        if values:
            summary[metric] = float(sum(values) / len(values))

    summary["n_total"] = n_total
    summary["n_valid"] = n_valid
    summary["n_evaluated"] = len(successful_rows)
    summary["n_failed"] = len(failed_rows)
    summary["n_completed"] = len(completed_rows)
    summary["n_skipped"] = n_skipped
    summary["n_remaining"] = max(n_valid - len(completed_rows), 0)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def evaluate_one(
    row: dict[str, Any],
    kept_row: dict[str, Any],
    metric_names: list[str],
    llm: Any,
    embeddings: Any,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "dataset": Dataset.from_list([row]),
        "metrics": [METRICS[m] for m in metric_names],
        "llm": llm,
        "embeddings": embeddings,
        "raise_exceptions": True,
        "run_config": RunConfig(
            timeout=int(float(os.getenv("RAGAS_LLM_TIMEOUT", "600"))),
            max_retries=int(os.getenv("RAGAS_MAX_RETRIES", "2")),
            max_wait=int(float(os.getenv("RAGAS_MAX_WAIT", "60"))),
            max_workers=int(os.getenv("RAGAS_MAX_WORKERS", "4")),
        ),
    }
    if "show_progress" in inspect.signature(evaluate).parameters:
        kwargs["show_progress"] = False

    result = evaluate(**kwargs)
    result_row = result.to_pandas().iloc[0].to_dict()
    result_row["question"] = kept_row.get("question")
    result_row["answer"] = kept_row.get("answer") or kept_row.get("final_answer")
    result_row["ground_truth"] = (
        kept_row.get("ground_truth") or kept_row.get("ground_truth_answer")
    )
    result_row["correct"] = kept_row.get("correct")
    result_row["latency_ms"] = kept_row.get("latency_ms")
    result_row["ragas_status"] = "success"
    return result_row


def build_failed_result(kept_row: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "question": kept_row.get("question"),
        "answer": kept_row.get("answer") or kept_row.get("final_answer"),
        "ground_truth": kept_row.get("ground_truth")
        or kept_row.get("ground_truth_answer"),
        "correct": kept_row.get("correct"),
        "latency_ms": kept_row.get("latency_ms"),
        "ragas_status": "failed",
        "ragas_error_type": type(exc).__name__,
        "ragas_error": str(exc),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation.")
    parser.add_argument("input", type=Path, help="Input file chứa question/answer/contexts/ground_truth")
    parser.add_argument("--output", type=Path, default=Path("ragas_results.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("ragas_summary.json"))
    parser.add_argument(
        "--metrics",
        default="faithfulness,answer_relevancy,context_precision,context_recall",
        help="Comma-separated metrics",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum new samples to evaluate in this run. Useful for limited quota.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry samples previously written with ragas_status=failed.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately when one sample fails instead of saving failure and continuing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    records = load_records(args.input)
    dataset, kept, skipped = build_ragas_dataset(records)

    if len(dataset) == 0:
        raise SystemExit(f"No valid samples. Skipped {len(skipped)}/{len(records)} records.")

    metric_names = [m.strip() for m in args.metrics.split(",") if m.strip()]
    invalid = [m for m in metric_names if m not in METRICS]
    if invalid:
        raise SystemExit(f"Invalid metrics: {invalid}. Valid: {list(METRICS)}")

    llm, embeddings = build_evaluator_models()
    completed_keys, result_rows = load_completed_results(
        args.output,
        retry_failed=args.retry_failed,
    )
    remaining_count = sum(1 for row in kept if sample_key(row) not in completed_keys)
    print(
        f"Loaded {len(result_rows)} existing results. "
        f"Remaining: {remaining_count}"
    )

    evaluated_this_run = 0
    try:
        for idx, (ragas_row, kept_row) in enumerate(zip(dataset, kept), start=1):
            key = sample_key(kept_row)
            if key in completed_keys:
                continue
            if args.max_samples is not None and evaluated_this_run >= args.max_samples:
                print(f"Reached --max-samples={args.max_samples}; stopping this run.")
                break

            print(f"[{idx}/{len(dataset)}] Evaluating: {kept_row.get('question')}")
            try:
                result_row = evaluate_one(
                    row=ragas_row,
                    kept_row=kept_row,
                    metric_names=metric_names,
                    llm=llm,
                    embeddings=embeddings,
                )
            except Exception as exc:
                if args.fail_fast:
                    raise

                result_row = build_failed_result(kept_row, exc)
                print(
                    "Sample failed; saved failure and continuing. "
                    f"Error: {type(exc).__name__}: {exc}"
                )

            append_jsonl(args.output, result_row)
            result_rows.append(result_row)
            completed_keys.add(key)
            evaluated_this_run += 1
            write_summary(
                args.summary,
                result_rows,
                metric_names,
                n_total=len(records),
                n_valid=len(dataset),
                n_skipped=len(skipped),
            )
            print(f"Saved {len(result_rows)}/{len(dataset)} evaluated samples")
    except Exception as exc:
        write_summary(
            args.summary,
            result_rows,
            metric_names,
            n_total=len(records),
            n_valid=len(dataset),
            n_skipped=len(skipped),
        )
        raise SystemExit(
            "Stopped because one sample failed. "
            f"Saved {len(result_rows)}/{len(dataset)} evaluated samples to {args.output}. "
            f"Error: {type(exc).__name__}: {exc}"
        ) from exc

    write_summary(
        args.summary,
        result_rows,
        metric_names,
        n_total=len(records),
        n_valid=len(dataset),
        n_skipped=len(skipped),
    )

    print(f"Saved details to: {args.output}")
    print(f"Saved summary to: {args.summary}")

    if skipped:
        print(f"Skipped {len(skipped)} records. First skipped item:")
        print(json.dumps(skipped[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
