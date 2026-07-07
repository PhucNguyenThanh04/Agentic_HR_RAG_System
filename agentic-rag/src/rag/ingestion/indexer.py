from typing import Any
import logging

from qdrant_client import models as qdrant_models

from src.integrations.qdrant.store import QdrantVectorStore
from src.rag.embeddings.embedding_service import EmbeddingService
from src.rag.ingestion.chunkers.base_chunker import DocumentChunk

from src.core.settings import get_settings
from src.core.setup_logging import setup_logger

settings = get_settings()

logger = setup_logger(__name__, level=logging.DEBUG if settings.api_debug else logging.INFO)

class DocumentIndexer: 
    def __init__(self,
        embedding_service: EmbeddingService,
        vector_store: QdrantVectorStore,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def _build_payload(
        self,
        *,
        document_id: str,
        filename: str,
        chunk: DocumentChunk,
        chunk_index: int,
        source: str = "admin_upload",
        language: str = "vi",
    ) -> dict[str, Any]:
        metadata = dict(chunk.metadata or {})
        content = getattr(chunk, "text", None) or chunk.content

        return {
            "chunk_id": chunk.chunk_id,
            "document_id": document_id,
            "content": content,
            "filename": filename,
            "file_path": metadata.get("file_path"),
            "doc_type": metadata.get("doc_type"),
            "language": language,
            "page": metadata.get("page"),
            "total_pages": metadata.get("total_pages"),
            "chunk_index": chunk_index,
            "chunk_level": metadata.get("chunk_level"),
            "clause_number": metadata.get("clause_number"),
            "clause_title": metadata.get("clause_title"),
            "dieu_refs": metadata.get("dieu_refs", []),
            "allowed_roles": metadata.get("allowed_roles", []),
            "source": metadata.get("source") or source,
        }

    def _build_point(
        self,
        *,
        point_id: str,
        dense_vector: list[float],
        sparse_vector: qdrant_models.SparseVector | None,
        payload: dict[str, Any],
    ) -> qdrant_models.PointStruct:
        vector: dict[str, Any] = {
            settings.dense_vector_name: dense_vector,
        }
        if sparse_vector is not None:
            vector[settings.sparse_vector_name] = sparse_vector

        return qdrant_models.PointStruct(
            id=point_id,
            vector=vector,
            payload=payload,
        )

    async def _upsert_in_batches(
        self,
        *,
        collection_name: str,
        points: list[qdrant_models.PointStruct],
        batch_size: int | None = None,
    ) -> None:
        if not points:
            logger.debug("No points to upsert")
            return

        effective_batch_size = batch_size or settings.qdrant_upsert_batch_size
        if effective_batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")

        for start in range(0, len(points), effective_batch_size):
            end = start + effective_batch_size
            batch = points[start:end]
            await self.vector_store.upsert_points(
                collection_name=collection_name,
                points=batch,
            )

    async def index_chunks(
        self,
        *,
        collection_name: str,
        document_id: str,
        filename: str,
        chunks: list[DocumentChunk],
        language: str = "vi",
        batch_size: int | None = None,
    ) -> int:
        if not chunks:
            logger.debug("No chunks to index")
            return 0

        valid_chunks = [
            DocumentChunk(
                chunk_id=chunk.chunk_id,
                content=self._extract_chunk_text(chunk),
                metadata=chunk.metadata,
            )
            for chunk in chunks
            if self._extract_chunk_text(chunk)
        ]

        if not valid_chunks:
            logger.debug("No non-empty chunks to index")
            return 0

        texts = [chunk.content for chunk in valid_chunks]
        embedding_batch = await self.embedding_service.embed_document_batch(texts)

        dense_vectors = embedding_batch.dense_vectors
        sparse_vectors = embedding_batch.sparse_vectors

        if len(dense_vectors) != len(valid_chunks):
            raise ValueError(
                "dense embedding count does not match chunk count: "
                f"{len(dense_vectors)} != {len(valid_chunks)}"
            )

        if len(sparse_vectors) != len(valid_chunks):
            raise ValueError(
                "sparse embedding count does not match chunk count: "
                f"{len(sparse_vectors)} != {len(valid_chunks)}"
            )

        points: list[qdrant_models.PointStruct] = []
        for chunk_index, (chunk, dense_vector, sparse_vector) in enumerate(
            zip(valid_chunks, dense_vectors, sparse_vectors)
        ):
            payload = self._build_payload(
                document_id=document_id,
                filename=filename,
                chunk=chunk,
                chunk_index=chunk_index,
                language=language,
            )
            point = self._build_point(
                point_id=chunk.chunk_id,
                dense_vector=dense_vector,
                sparse_vector=sparse_vector,
                payload=payload,
            )
            points.append(point)

        await self._upsert_in_batches(
            collection_name=collection_name,
            points=points,
            batch_size=batch_size,
        )

        return len(points)

    def _extract_chunk_text(self, chunk: DocumentChunk) -> str:
        text = getattr(chunk, "text", None) or chunk.content
        return text.strip()

    async def delete_document(
        self,
        *,
        collection_name: str,
        document_id: str,
    ) -> None:
        if not collection_name.strip():
            raise ValueError("collection_name must not be empty")

        if not document_id.strip():
            raise ValueError("document_id must not be empty")

        await self.vector_store.delete_by_document_id(
            collection_name=collection_name,
            document_id=document_id,
        )

    
