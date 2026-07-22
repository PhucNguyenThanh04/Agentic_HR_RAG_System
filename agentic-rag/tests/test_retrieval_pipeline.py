from __future__ import annotations

import unittest

from src.integrations.qdrant.store import QdrantSearchResult
from src.rag.retrieval.context_builder import ContextBuilder
from src.rag.retrieval.retrieval_pipeline import RetrievalPipeline


class FakeRetriever:
    def __init__(self, results: list[QdrantSearchResult]) -> None:
        self.results = results

    async def retrieve(self, **kwargs):
        return self.results


class FakeReranker:
    async def rerank(self, query, results, top_n=None):
        return results


def _qdrant_result(score: float) -> QdrantSearchResult:
    return QdrantSearchResult(
        point_id="chunk-1",
        score=score,
        content="Nội dung chính sách nghỉ phép.",
        metadata={
            "chunk_id": "chunk-1",
            "filename": "policy.pdf",
        },
    )


class RetrievalPipelineStatusTests(unittest.IsolatedAsyncioTestCase):
    def _pipeline(self, results: list[QdrantSearchResult]) -> RetrievalPipeline:
        return RetrievalPipeline(
            hybrid_retriever=FakeRetriever(results),  # type: ignore[arg-type]
            reranker_service=FakeReranker(),  # type: ignore[arg-type]
            context_builder=ContextBuilder(),
        )

    async def test_no_candidates_status(self) -> None:
        result = await self._pipeline([]).retrieve_context("query", "employee")
        self.assertEqual(result.status, "no_candidates")
        self.assertEqual(result.candidate_count, 0)

    async def test_below_quality_threshold_status(self) -> None:
        result = await self._pipeline([_qdrant_result(0.0)]).retrieve_context(
            "query",
            "employee",
        )
        self.assertEqual(result.status, "below_quality_threshold")
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.best_score, 0.0)

    async def test_context_budget_exhausted_status(self) -> None:
        result = await self._pipeline([_qdrant_result(0.99)]).retrieve_context(
            "query",
            "employee",
            max_context_tokens=1,
        )
        self.assertEqual(result.status, "context_budget_exhausted")
        self.assertEqual(result.qualified_count, 1)

    async def test_success_exposes_counts_score_and_latency(self) -> None:
        result = await self._pipeline([_qdrant_result(0.99)]).retrieve_context(
            "query",
            "employee",
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.qualified_count, 1)
        self.assertEqual(result.selected_chunk_count, 1)
        self.assertEqual(result.best_score, 0.99)
        self.assertGreaterEqual(result.latency_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
