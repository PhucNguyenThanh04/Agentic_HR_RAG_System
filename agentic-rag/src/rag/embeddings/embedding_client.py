from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache

from FlagEmbedding import BGEM3FlagModel
from qdrant_client import models

from src.core.settings import get_settings

settings = get_settings()


@dataclass
class EmbeddingBatch:
    dense_vectors: list[list[float]]
    sparse_vectors: list[models.SparseVector]


class EmbeddingClient:
    # max_workers=1: BGE-M3 không thread-safe
    # chỉ 1 inference tại 1 thời điểm, request sau queue lại chờ
    _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bge_m3")

    def __init__(self) -> None:
        self._device = self._resolve_device(settings.embedding_device)
        self._model = BGEM3FlagModel(
            settings.embedding_model,
            use_fp16=self._device == "cuda",
            device=self._device,
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
    # Luôn đi qua EmbeddingService (có run_in_executor)
    # ------------------------------------------------------------------

    def warmup(self) -> None:
        self.embed_hybrid(["warmup embedding model"])

    def embed_dense(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = self._model.encode(
            texts,
            batch_size=12,
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return [vec.tolist() for vec in result["dense_vecs"]]

    def embed_hybrid(self, texts: list[str]) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(dense_vectors=[], sparse_vectors=[])
        result = self._model.encode(
            texts,
            batch_size=12,
            max_length=8192,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense_vectors = [vec.tolist() for vec in result["dense_vecs"]]
        sparse_vectors = [
            self._to_sparse_vector(lw)
            for lw in result.get("lexical_weights", [])
        ]
        return EmbeddingBatch(
            dense_vectors=dense_vectors,
            sparse_vectors=sparse_vectors,
        )

    @staticmethod
    def _to_sparse_vector(lexical_weights: dict) -> models.SparseVector:
        items = sorted(
            (int(token_id), float(weight))
            for token_id, weight in lexical_weights.items()
            if float(weight) > 0
        )
        return models.SparseVector(
            indices=[token_id for token_id, _ in items],
            values=[weight for _, weight in items],
        )


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient()
