from fastapi import Depends, HTTPException, UploadFile
from typing import Any

from src.rag.ingestion.pipeline import IngestionPipeline
from src.core.dependenci import get_ingestion_pipeline
from src.core.settings import get_settings
from src.features.documents.schemas import (
    DocumentIngestResponse,
    DocumentVectorDeleteResponse,
)

from src.core.setup_logging import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


class DocumentService:
    def __init__(self,
        ingestion_pipeline: IngestionPipeline,
    ) -> None:
        self.ingestion_pipeline = ingestion_pipeline

    @staticmethod
    def _normalize_allowed_roles(allowed_roles: list[Any]) -> list[str]:
        return [
            role.strip()
            for item in allowed_roles
            for role in str(item).split(",")
            if role.strip()
        ]

    async def ingestion(self,
        file: UploadFile,
        document_id: str,
        filename: str,
        file_path: str,
        allowed_roles: list[Any],
    ) -> DocumentIngestResponse:
        try:
            normalized_allowed_roles = self._normalize_allowed_roles(allowed_roles)
            result = await self.ingestion_pipeline.ingestion(
                file=file,
                document_id=document_id,
                filename=filename,
                file_path=file_path,
                allowed_roles=normalized_allowed_roles,
            )
        except ValueError as exc:
            logger.error(f"Ingestion failed for document {document_id}: {exc}")
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error(f"Unexpected error during ingestion of document {document_id}: {exc}")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return DocumentIngestResponse(
            document_id=result.document_id,
            filename=result.filename,
            collection=result.collection,
            status=result.status,
            chunks_count=result.chunks_count,
            vector_indexed=result.vector_indexed,
            keyword_indexed=result.keyword_indexed,
            error_code=result.error_code,
            message=result.message,
        )

    async def delete_document_vectors(
        self,
        document_id: str,
    ) -> DocumentVectorDeleteResponse:
        normalized_document_id = document_id.strip()
        if not normalized_document_id:
            raise ValueError("document_id must not be empty")

        deleted = await self.ingestion_pipeline.delete_document(
            document_id=normalized_document_id,
        )
        if not deleted:
            raise RuntimeError("Failed to delete document vectors")

        collection = settings.default_qdrant_collection
        return DocumentVectorDeleteResponse(
            document_id=normalized_document_id,
            collection=collection,
            status="deleted",
            deleted=True,
            message=(
                "Document vectors deleted successfully from collection "
                f"{collection}"
            ),
        )



def get_document_service(ingestion_pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)) -> DocumentService:
    return DocumentService(
        ingestion_pipeline=ingestion_pipeline,
    )
