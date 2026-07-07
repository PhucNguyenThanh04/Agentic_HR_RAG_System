from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from qdrant_client import AsyncQdrantClient, models

from src.integrations.qdrant.client import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME

from src.core.setup_logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class QdrantSearchResult:
    point_id: str
    score: float
    content: str
    metadata: dict[str, Any]


class QdrantVectorStore:

    def __init__(
        self,
        client: AsyncQdrantClient,
        dense_vector_name: str = DENSE_VECTOR_NAME,
        sparse_vector_name: str = SPARSE_VECTOR_NAME,
    ) -> None:
        self.client = client
        self.dense_vector_name = dense_vector_name
        self.sparse_vector_name = sparse_vector_name

    async def upsert_points(
        self,
        collection_name: str,
        points: Sequence[models.PointStruct],
        wait: bool = True,
    ) -> int:
        if not points:
            return 0

        await self.client.upsert(
            collection_name=collection_name,
            points=list(points),
            wait=wait,
        )
        return len(points)

    async def search_dense(
        self,
        collection_name: str,
        query_vector: Sequence[float],
        top_k: int = 10,
        allowed_role: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[QdrantSearchResult]:
        scored_points = await self.client.search(
            collection_name=collection_name,
            query_vector=(self.dense_vector_name, list(query_vector)),
            query_filter=self._build_filter(allowed_role, metadata_filter),
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        return [self._to_search_result(point) for point in scored_points]

    async def search_hybrid(
        self,
        collection_name: str,
        dense_query_vector: Sequence[float],
        sparse_query_vector: models.SparseVector | None,
        top_k: int = 10,
        allowed_role: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
        prefetch_limit: int | None = None,
    ) -> list[QdrantSearchResult]:
        if sparse_query_vector is None:
            return await self.search_dense(
                collection_name=collection_name,
                query_vector=dense_query_vector,
                top_k=top_k,
                allowed_role=allowed_role,
                metadata_filter=metadata_filter,
            )

        query_filter = self._build_filter(allowed_role, metadata_filter)
        prefetch_limit = prefetch_limit or max(top_k * 4, top_k)

        response = await self.client.query_points(
            collection_name=collection_name,
            prefetch=[
                models.Prefetch(
                    query=list(dense_query_vector),
                    using=self.dense_vector_name,
                    filter=query_filter,
                    limit=prefetch_limit,
                ),
                models.Prefetch(
                    query=sparse_query_vector,
                    using=self.sparse_vector_name,
                    filter=query_filter,
                    limit=prefetch_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        return [
            self._to_search_result(point)
            for point in getattr(response, "points", response)
        ]

    async def delete_by_document_id(
        self,
        collection_name: str,
        document_id: str,
        wait: bool = True,
    ) -> None:
        await self.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=wait,
        )

    def _build_filter(
        self,
        allowed_role: str | None,
        metadata_filter: dict[str, Any] | None,
    ) -> models.Filter | None:
        conditions: list[models.FieldCondition] = []

        if allowed_role:
            conditions.append(
                models.FieldCondition(
                    key="allowed_roles",
                    match=models.MatchValue(value=allowed_role),
                )
            )

        for key, value in (metadata_filter or {}).items():
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchAny(any=list(value)),
                    )
                )
            else:
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                )

        if not conditions:
            return None

        return models.Filter(must=conditions)

    @staticmethod
    def _to_search_result(
        point: Any,
        score: float | None = None,
    ) -> QdrantSearchResult:
        payload = dict(point.payload or {})
        content = str(payload.pop("content", ""))
        return QdrantSearchResult(
            point_id=str(point.id),
            score=float(point.score if score is None else score),
            content=content,
            metadata=payload,
        )
