from __future__ import annotations

import asyncio

from src.rag.embeddings.embedding_client import EmbeddingBatch, EmbeddingClient


class EmbeddingService:
    """
    Async business logic layer cho embedding.
    Biết về use case — không biết model là gì.

    Mọi call đều non-blocking: chạy EmbeddingClient sync methods
    trong thread pool executor để không block FastAPI event loop.
    """

    def __init__(self, client: EmbeddingClient) -> None:
        self._client = client

    async def warmup(self) -> None:
        await self._run(self._client.warmup)

    async def embed_query(self, query: str) -> list[float]:
        """Dense embedding cho 1 query — dùng trong hybrid search."""
        results = await self._run(self._client.embed_dense, [query])
        return results[0]

    async def embed_query_hybrid(self, query: str) -> EmbeddingBatch:
        """Dense + sparse embedding cho 1 query — dùng trong hybrid search."""
        return await self._run(self._client.embed_hybrid, [query])

    # ------------------------------------------------------------------
    # Ingestion path — encode batch documents
    # ------------------------------------------------------------------

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Dense embedding cho batch documents."""
        return await self._run(self._client.embed_dense, texts)

    async def embed_document_batch(self, texts: list[str]) -> EmbeddingBatch:
        """Dense + sparse embedding cho batch documents."""
        return await self._run(self._client.embed_hybrid, texts)

    async def _run(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._client.executor, func, *args)
