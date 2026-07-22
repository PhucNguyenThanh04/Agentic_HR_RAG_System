from __future__ import annotations

import asyncio
import unittest

from src.rag.retrieval.context_builder import ContextCitation
from src.rag.retrieval.retrieval_pipeline import RetrievalPipelineResult
from src.rag.retrieval.schemas import RetrievedChunk
from src.tools.vector_search_tool import VectorSearchTool, validate_rewritten_query


def _result(
    score: float,
    *,
    chunk_ids: list[str] | None = None,
    status: str = "success",
) -> RetrievalPipelineResult:
    ids = chunk_ids or []
    chunks = [
        RetrievedChunk(
            chunk_id=chunk_id,
            content=f"Nội dung {chunk_id}",
            filename="policy.pdf",
            page=1,
            section="Quy định",
            clause_number=None,
            score=score,
        )
        for chunk_id in ids
    ]
    citations = [
        ContextCitation(
            index=index,
            chunk_id=chunk.chunk_id,
            document_id=None,
            filename=chunk.filename,
            page=chunk.page,
            section=chunk.section,
            clause_number=chunk.clause_number,
            score=score,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]
    used_context = status == "success" and bool(chunks)
    return RetrievalPipelineResult(
        chunks=chunks,
        citations=citations,
        token_count=100 if chunks else 0,
        low_confidence=len(chunks) == 1,
        used_context=used_context,
        status=status,  # type: ignore[arg-type]
        candidate_count=len(chunks),
        qualified_count=len(chunks),
        selected_chunk_count=len(chunks),
        best_score=score,
        latency_ms=5.0,
    )


class FakeRetrievalPipeline:
    def __init__(self, results: dict[str, RetrievalPipelineResult]) -> None:
        self.results = results
        self.calls: list[str] = []
        self.active_calls = 0
        self.max_active_calls = 0

    async def retrieve_context(self, query: str, allowed_role: str):
        self.calls.append(query)
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        await asyncio.sleep(0.01)
        self.active_calls -= 1
        return self.results[query]


class RewriteValidatorTests(unittest.TestCase):
    def test_same_query_does_not_need_rewrite(self) -> None:
        validation = validate_rewritten_query(
            "  Nghỉ phép năm  ",
            "nghỉ phép năm",
        )
        self.assertEqual(validation.status, "not_needed")

    def test_rejects_removed_or_added_protected_literals(self) -> None:
        removed = validate_rewritten_query(
            "Nghỉ ít nhất 12 giờ",
            "Thời gian nghỉ tối thiểu",
        )
        added = validate_rewritten_query(
            "Thời gian nghỉ tối thiểu",
            "Thời gian nghỉ tối thiểu 12 giờ",
        )
        self.assertEqual(removed.rejection_reason, "protected_literal_removed")
        self.assertEqual(added.rejection_reason, "protected_literal_added")

    def test_rejects_missing_preserved_term(self) -> None:
        validation = validate_rewritten_query(
            "Quy định về nghỉ phép năm",
            "Quy định về ngày nghỉ",
            ["nghỉ phép năm"],
        )
        self.assertEqual(
            validation.rejection_reason,
            "preserved_term_missing_from_rewrite",
        )

    def test_rejects_too_short_or_too_long_rewrite(self) -> None:
        too_short = validate_rewritten_query("Quy định ca làm", "ca")
        too_long = validate_rewritten_query("Quy định ca làm", "x" * 1001)
        self.assertEqual(too_short.rejection_reason, "query_too_short")
        self.assertEqual(too_long.rejection_reason, "query_too_long")


class VectorSearchToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_strategy_requires_a_calibrated_threshold(self) -> None:
        pipeline = FakeRetrievalPipeline({})
        with self.assertRaisesRegex(ValueError, "rewrite_fallback_score"):
            VectorSearchTool(
                pipeline,  # type: ignore[arg-type]
                allowed_role="employee",
                original_query="Nghỉ phép năm",
                retrieval_strategy="fallback",
            )

    async def test_identical_query_calls_pipeline_once(self) -> None:
        pipeline = FakeRetrievalPipeline({"Nghỉ phép năm": _result(0.9, chunk_ids=["a"])})
        tool = VectorSearchTool(
            pipeline,  # type: ignore[arg-type]
            allowed_role="employee",
            original_query="Nghỉ phép năm",
            retrieval_strategy="dual_parallel",
        )

        result = await tool.run("Nghỉ phép năm")

        self.assertEqual(pipeline.calls, ["Nghỉ phép năm"])
        self.assertEqual(result.metadata["rewrite_status"], "not_needed")
        self.assertEqual(result.metadata["retrieval_attempt_count"], 1)

    async def test_dual_strategy_runs_queries_concurrently_and_keeps_one_set(self) -> None:
        original = "Quy định nghỉ phép như thế nào?"
        rewrite = "Chính sách nghỉ phép cho người lao động"
        pipeline = FakeRetrievalPipeline(
            {
                original: _result(0.7, chunk_ids=["original"]),
                rewrite: _result(0.9, chunk_ids=["rewrite-1", "rewrite-2"]),
            }
        )
        tool = VectorSearchTool(
            pipeline,  # type: ignore[arg-type]
            allowed_role="employee",
            original_query=original,
            retrieval_strategy="dual_parallel",
        )

        result = await tool.run(rewrite, preserved_terms=["nghỉ phép"])

        self.assertEqual(pipeline.max_active_calls, 2)
        self.assertEqual(result.metadata["selected_query_source"], "rewrite")
        self.assertEqual(
            [citation.chunk_id for citation in result.citations],
            ["rewrite-1", "rewrite-2"],
        )

    async def test_fallback_skips_rewrite_when_original_is_strong(self) -> None:
        original = "Quy định nghỉ phép"
        rewrite = "Chính sách nghỉ phép"
        pipeline = FakeRetrievalPipeline(
            {
                original: _result(0.9, chunk_ids=["original"]),
                rewrite: _result(0.95, chunk_ids=["rewrite"]),
            }
        )
        tool = VectorSearchTool(
            pipeline,  # type: ignore[arg-type]
            allowed_role="employee",
            original_query=original,
            retrieval_strategy="fallback",
            rewrite_fallback_score=0.8,
        )

        result = await tool.run(rewrite, preserved_terms=["nghỉ phép"])

        self.assertEqual(pipeline.calls, [original])
        self.assertEqual(result.metadata["retrieval_attempt_count"], 1)

    async def test_rejected_rewrite_is_not_retrieved(self) -> None:
        original = "Người lao động được nghỉ ít nhất 12 giờ"
        unsafe_rewrite = "Thời gian nghỉ tối thiểu của người lao động"
        pipeline = FakeRetrievalPipeline(
            {original: _result(0.9, chunk_ids=["original"])}
        )
        tool = VectorSearchTool(
            pipeline,  # type: ignore[arg-type]
            allowed_role="employee",
            original_query=original,
            retrieval_strategy="dual_parallel",
        )

        result = await tool.run(unsafe_rewrite)

        self.assertEqual(pipeline.calls, [original])
        self.assertEqual(result.metadata["rewrite_status"], "rejected")
        self.assertEqual(
            result.metadata["rewrite_rejection_reason"],
            "protected_literal_removed",
        )

    async def test_fallback_runs_rewrite_for_each_empty_status(self) -> None:
        for status in (
            "no_candidates",
            "below_quality_threshold",
            "context_budget_exhausted",
        ):
            with self.subTest(status=status):
                original = "Quy định nghỉ phép"
                rewrite = "Chính sách nghỉ phép"
                pipeline = FakeRetrievalPipeline(
                    {
                        original: _result(0.0, status=status),
                        rewrite: _result(0.9, chunk_ids=["rewrite"]),
                    }
                )
                tool = VectorSearchTool(
                    pipeline,  # type: ignore[arg-type]
                    allowed_role="employee",
                    original_query=original,
                    retrieval_strategy="fallback",
                    rewrite_fallback_score=0.8,
                )

                result = await tool.run(rewrite, preserved_terms=["nghỉ phép"])

                self.assertEqual(pipeline.calls, [original, rewrite])
                self.assertEqual(result.metadata["fallback_reason"], status)
                self.assertEqual(result.metadata["evidence_status"], "sufficient")

    async def test_both_weak_returns_no_citations(self) -> None:
        original = "Quy định nghỉ phép"
        rewrite = "Chính sách nghỉ phép"
        pipeline = FakeRetrievalPipeline(
            {
                original: _result(0.4, chunk_ids=["original"]),
                rewrite: _result(0.6, chunk_ids=["rewrite"]),
            }
        )
        tool = VectorSearchTool(
            pipeline,  # type: ignore[arg-type]
            allowed_role="employee",
            original_query=original,
            retrieval_strategy="fallback",
            rewrite_fallback_score=0.8,
        )

        result = await tool.run(rewrite, preserved_terms=["nghỉ phép"])

        self.assertEqual(result.outcome, "empty")
        self.assertEqual(result.citations, [])
        self.assertEqual(result.metadata["evidence_status"], "insufficient")


if __name__ == "__main__":
    unittest.main()
