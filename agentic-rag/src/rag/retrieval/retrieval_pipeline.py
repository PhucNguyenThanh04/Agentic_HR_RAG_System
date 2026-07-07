from __future__ import annotations

from dataclasses import dataclass
from fastapi import Depends

from src.core.settings import get_settings
from src.rag.retrieval.schemas import RetrievedChunk
from src.integrations.qdrant.store import QdrantSearchResult
from src.rag.retrieval.context_builder import ContextBuilder, ContextCitation
from src.rag.retrieval.hybrid_retriever import HybridRetriever
from src.rag.retrieval.reranker import RerankerService
from src.core.dependenci import get_embedding_service, get_vector_store, get_reranker_service
from src.rag.embeddings.embedding_service import EmbeddingService
from src.integrations.qdrant.store import QdrantVectorStore

settings = get_settings()

SCORE_SPREAD_THRESHOLD = 0.3
TOP_SCORE_WINDOW = 0.1


@dataclass
class RetrievalPipelineResult:
    chunks: list[RetrievedChunk]
    citations: list[ContextCitation]
    token_count: int
    low_confidence: bool
    used_context: bool


class RetrievalPipeline:
    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        reranker_service: RerankerService,
        context_builder: ContextBuilder,
    ) -> None:
        self.hybrid_retriever = hybrid_retriever
        self.reranker_service = reranker_service
        self.context_builder = context_builder

    async def retrieve_context(
        self,
        query: str,
        allowed_role: str,
        collection_name: str | None = None,
        top_k: int | None = None,
        rerank_top_n: int | None = None,
        max_context_tokens: int = 3000,
    ) -> RetrievalPipelineResult:
        retrieved_results = await self.hybrid_retriever.retrieve(
            query=query,
            collection_name=collection_name,
            top_k=top_k,
            allowed_role=allowed_role,
        )

        reranked_results = await self.reranker_service.rerank(
            query=query,
            results=retrieved_results,
            top_n=rerank_top_n,
        )

        qualified_results = self._filter_quality(reranked_results)
        if not qualified_results:
            return self._empty_result()

        low_confidence = len(qualified_results) == 1
        context_result = self.context_builder.build(
            qualified_results,
            max_tokens=max_context_tokens,
        )

        if not context_result.chunks:
            return self._empty_result()

        return RetrievalPipelineResult(
            chunks=context_result.chunks,
            citations=context_result.citations,
            token_count=context_result.token_count,
            low_confidence=low_confidence,
            used_context=True,
        )

    def _filter_quality(
        self,
        results: list[QdrantSearchResult],
    ) -> list[QdrantSearchResult]:
        qualified_results = [
            result
            for result in results
            if result.score >= settings.retrieval_score_threshold
        ]

        if len(qualified_results) <= 1:
            return qualified_results

        top_score = qualified_results[0].score
        last_score = qualified_results[-1].score
        if top_score - last_score <= SCORE_SPREAD_THRESHOLD:
            return qualified_results

        return [
            result
            for result in qualified_results
            if result.score >= top_score - TOP_SCORE_WINDOW
        ]

    @staticmethod
    def _empty_result() -> RetrievalPipelineResult:
        return RetrievalPipelineResult(
            chunks=[],
            citations=[],
            token_count=0,
            low_confidence=False,
            used_context=False,
        )



def get_retrieval_pipeline(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store: QdrantVectorStore = Depends(get_vector_store),
    reranker_service: RerankerService = Depends(get_reranker_service),
) -> RetrievalPipeline:
    return RetrievalPipeline(
        hybrid_retriever=HybridRetriever(
            embedding_service=embedding_service,
            vector_store=vector_store,
        ),
        reranker_service=reranker_service,
        context_builder=ContextBuilder(),
    )
