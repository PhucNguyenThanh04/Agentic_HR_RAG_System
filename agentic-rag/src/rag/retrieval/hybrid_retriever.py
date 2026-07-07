from __future__ import annotations

import time

from src.integrations.qdrant.store import QdrantSearchResult, QdrantVectorStore
from src.rag.embeddings.embedding_service import EmbeddingService

from src.core.settings import get_settings
from src.core.setup_logging import setup_logger

settings = get_settings()

logger = setup_logger(__name__)


class HybridRetriever:

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore,
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store

    async def retrieve(
        self,
        query: str,
        collection_name: str | None = None,
        top_k: int | None = None,
        allowed_role: str | None = None,
    ) -> list[QdrantSearchResult]:

        collection = collection_name or settings.default_qdrant_collection
        effective_top_k = top_k or settings.retrieval_top_k

        start = time.perf_counter()

        # 1. Embed query → dense + sparse vectors
        embedding_batch = await self._embedding_service.embed_query_hybrid(query)

        dense_vector = embedding_batch.dense_vectors[0]
        sparse_vector = (
            embedding_batch.sparse_vectors[0]
            if embedding_batch.sparse_vectors
            else None
        )

        # 2. Hybrid search trên Qdrant với permission filter ngay trong query.
        #    Các bước sau chỉ xử lý chunks user có quyền truy cập.
        results = await self._vector_store.search_hybrid(
            collection_name=collection,
            dense_query_vector=dense_vector,
            sparse_query_vector=sparse_vector,
            top_k=effective_top_k,
            allowed_role=allowed_role,
        )

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "HybridRetriever | query=%r | collection=%s | top_k=%d | allowed_role=%s | results=%d | %.0fms",
            query[:80],
            collection,
            effective_top_k,
            allowed_role,
            len(results),
            duration_ms,
        )

        return results
