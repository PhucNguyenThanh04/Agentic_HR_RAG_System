from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
import asyncio


from FlagEmbedding import FlagReranker

from src.core.settings import get_settings
from src.core.setup_logging import setup_logger
from src.integrations.qdrant.store import QdrantSearchResult

settings = get_settings()

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# RerankerClient — sync inference layer
# Không gọi trực tiếp từ async code, luôn đi qua RerankerService.
# ---------------------------------------------------------------------------


class RerankerClient:
    """Thin wrapper quanh FlagReranker (BGE-Reranker-v2-m3).

    Pattern giống EmbeddingClient:
    - ThreadPoolExecutor(max_workers=1): FlagReranker không thread-safe
    - Sync methods dùng nội bộ, async code gọi qua RerankerService
    """

    _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reranker")

    def __init__(self) -> None:
        self._device = self._resolve_device(settings.reranker_device)
        self._model = FlagReranker(
            settings.reranker_model,
            use_fp16=self._device == "cuda",
            device=self._device,
        )
        logger.info(
            "RerankerClient loaded | model=%s | device=%s | fp16=%s",
            settings.reranker_model,
            self._device,
            self._device == "cuda",
        )

    @staticmethod
    def _resolve_device(device: str) -> str:
        return "cuda" if device == "gpu" else device

    @property
    def device(self) -> str:
        return self._device

    @property
    def executor(self) -> ThreadPoolExecutor:
        return self._executor

    # ------------------------------------------------------------------
    # Sync methods — KHÔNG gọi trực tiếp từ async code
    # ------------------------------------------------------------------

    def warmup(self) -> None:
        """Chạy 1 lần dummy inference để load model weights vào GPU."""
        self.compute_scores("warmup query", ["warmup passage"])

    def compute_scores(
        self,
        query: str,
        passages: list[str],
    ) -> list[float]:
        """Tính relevance scores cho từng cặp (query, passage).

        Returns:
            List[float] cùng thứ tự với passages.
        """
        if not passages:
            return []

        pairs = [[query, passage] for passage in passages]
        scores = self._model.compute_score(pairs, normalize=True)

        # compute_score trả về float nếu chỉ có 1 pair, list[float] nếu nhiều
        if isinstance(scores, (int, float)):
            scores = [float(scores)]

        return [float(s) for s in scores]




class RerankerService:
    """Async wrapper cho RerankerClient.

    Biết về use case (rerank QdrantSearchResult), không biết model cụ thể.
    Mọi call đều non-blocking qua run_in_executor.
    """

    def __init__(self, client: RerankerClient) -> None:
        self._client = client

    async def warmup(self) -> None:
        await self._run(self._client.warmup)

    async def rerank(
        self,
        query: str,
        results: list[QdrantSearchResult],
        top_n: int | None = None,
    ) -> list[QdrantSearchResult]:
        """Rerank search results và trả về top_n kết quả tốt nhất.

        Args:
            query: câu hỏi gốc của user
            results: kết quả từ HybridRetriever (chưa lọc role)
            top_n: số lượng kết quả giữ lại (default: settings.rerank_top_n)

        Returns:
            list[QdrantSearchResult] đã rerank, score được cập nhật
            thành relevance score từ reranker, sắp xếp giảm dần.
        """
        if not results:
            return []

        effective_top_n = top_n or settings.rerank_top_n

        start = time.perf_counter()

        # 1. Lấy content text từ mỗi chunk để tính score
        passages = [r.content for r in results]

        # 2. Compute relevance scores (sync, chạy trong thread pool)
        scores = await self._run(self._client.compute_scores, query, passages)

        # 3. Gán score mới + sort giảm dần
        scored_results = []
        for result, rerank_score in zip(results, scores):
            scored_results.append(
                QdrantSearchResult(
                    point_id=result.point_id,
                    score=rerank_score,
                    content=result.content,
                    metadata=result.metadata,
                )
            )

        scored_results.sort(key=lambda r: r.score, reverse=True)

        # 4. Cắt top_n
        top_results = scored_results[:effective_top_n]

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "RerankerService | query=%r | input=%d | top_n=%d | best_score=%.4f | %.0fms",
            query[:80],
            len(results),
            effective_top_n,
            top_results[0].score if top_results else 0.0,
            duration_ms,
        )

        return top_results

    async def _run(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._client.executor, func, *args)
