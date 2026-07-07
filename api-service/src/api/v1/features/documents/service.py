from __future__ import annotations

import re
import uuid
from pathlib import Path

import httpx
from fastapi import Depends, UploadFile

from src.api.v1.features.documents import schemas
from src.api.v1.features.documents.models import Document
from src.api.v1.features.documents.repository import (
    DocumentRepository,
    get_document_repository,
)
from src.api.v1.features.staff.models import Employee
from src.core.clients.chatbox.client import ChatboxClient
from src.core.dependencies.dep import get_chatbox_http_client
from src.core.exceptions import BadRequestException, MLProcessingException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[5]
UPLOAD_DIR = BASE_DIR / "uploads" / "documents"
PUBLIC_UPLOAD_PREFIX = "/uploads/documents"
MAX_DOCUMENT_SIZE = 25 * 1024 * 1024
PENDING_QDRANT_COLLECTION = "pending"
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}


class DocumentService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chatbox_client: ChatboxClient,
    ) -> None:
        self.document_repository = document_repository
        self.chatbox_client = chatbox_client

    @staticmethod
    def _to_read(document: Document) -> schemas.DocumentRead:
        return schemas.DocumentRead.model_validate(document)

    @staticmethod
    def _safe_filename(filename: str) -> str:
        basename = Path(filename).name.strip()
        if not basename:
            raise BadRequestException("filename is required")
        stem = Path(basename).stem.strip() or "document"
        suffix = Path(basename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise BadRequestException(
                f"Unsupported file type. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
        return f"{safe_stem or 'document'}{suffix}"

    @staticmethod
    def _normalize_allowed_roles(allowed_roles: list[str]) -> list[str]:
        normalized = [
            role.strip()
            for item in allowed_roles
            for role in item.split(",")
            if role.strip()
        ]
        if not normalized:
            raise BadRequestException("allowed_roles is required")
        if len(normalized) != len(set(normalized)):
            raise BadRequestException("allowed_roles must not contain duplicates")
        return normalized

    @staticmethod
    def _delete_local_file(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            logger.warning("Failed to delete local document file: path=%s", path, exc_info=True)

    async def upload_document(
        self,
        *,
        title: str,
        allowed_roles: list[str],
        file: UploadFile,
        current_employee: Employee,
    ) -> schemas.DocumentRead:
        normalized_title = title.strip()
        if not normalized_title:
            raise BadRequestException("title is required")

        normalized_allowed_roles = self._normalize_allowed_roles(allowed_roles)
        safe_original_filename = self._safe_filename(file.filename or "")
        file_bytes = await file.read()
        if not file_bytes:
            raise BadRequestException("Empty file is not allowed")
        if len(file_bytes) > MAX_DOCUMENT_SIZE:
            raise BadRequestException("File size must be less than 25MB")

        document_id = uuid.uuid4()
        stored_filename = f"{document_id}_{safe_original_filename}"
        local_path = UPLOAD_DIR / stored_filename
        public_file_path = f"{PUBLIC_UPLOAD_PREFIX}/{stored_filename}"
        file_type = Path(safe_original_filename).suffix.lower().lstrip(".")

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(file_bytes)

        document_created = False
        rag_cleanup_needed = False
        try:
            await self.document_repository.create_processing_document(
                document_id=document_id,
                title=normalized_title,
                file_name=stored_filename,
                file_url=public_file_path,
                file_type=file_type,
                uploaded_by=current_employee.employee_id,
                allowed_roles=normalized_allowed_roles,
                qdrant_collection=PENDING_QDRANT_COLLECTION,
            )
            document_created = True

            rag_cleanup_needed = True
            ingest_result = await self.chatbox_client.ingest_document(
                document_id=str(document_id),
                filename=stored_filename,
                file_path=public_file_path,
                allowed_roles=normalized_allowed_roles,
                file_bytes=file_bytes,
                upload_filename=stored_filename,
                content_type=file.content_type or "application/octet-stream",
            )

            document = await self.document_repository.mark_ready(
                document_id=document_id,
                chunk_count=ingest_result.chunks_count,
                qdrant_collection=ingest_result.collection,
            )
            return self._to_read(document)
        except (httpx.HTTPError, ValueError) as exc:
            if rag_cleanup_needed:
                await self._cleanup_document_vectors(document_id)
            if document_created:
                await self._cleanup_document_record(document_id)
            self._delete_local_file(local_path)
            raise MLProcessingException(
                step="rag_document_ingest",
                reason=str(exc),
                task_id=str(document_id),
            ) from exc
        except Exception:
            if rag_cleanup_needed:
                await self._cleanup_document_vectors(document_id)
            if document_created:
                await self._cleanup_document_record(document_id)
            self._delete_local_file(local_path)
            raise

    async def _cleanup_document_record(self, document_id: uuid.UUID) -> None:
        try:
            await self.document_repository.delete_document(document_id)
        except Exception:
            logger.warning(
                "Failed to cleanup document record: document_id=%s",
                document_id,
                exc_info=True,
            )

    async def _cleanup_document_vectors(self, document_id: uuid.UUID) -> None:
        try:
            await self.chatbox_client.delete_document_vectors(str(document_id))
        except Exception:
            logger.warning(
                "Failed to cleanup document vectors: document_id=%s",
                document_id,
                exc_info=True,
            )

    async def get_document(self, document_id: uuid.UUID) -> schemas.DocumentRead:
        document = await self.document_repository.get_document_or_404(document_id)
        return self._to_read(document)

    async def list_documents(self, query: schemas.DocumentListQuery) -> dict:
        documents, total = await self.document_repository.list_documents(query)
        return {
            "items": [self._to_read(document) for document in documents],
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
        }

    async def delete_document(self, document_id: uuid.UUID) -> None:
        document = await self.document_repository.get_document_or_404(document_id)
        try:
            await self.chatbox_client.delete_document_vectors(str(document_id))
        except (httpx.HTTPError, ValueError) as exc:
            logger.exception("Failed to delete document vectors: document_id=%s", document_id)
            raise MLProcessingException(
                step="rag_document_delete",
                reason=str(exc),
                task_id=str(document_id),
            ) from exc

        await self.document_repository.delete_document(document_id)
        local_path = UPLOAD_DIR / document.file_name
        self._delete_local_file(local_path)


def get_document_service(
    document_repository: DocumentRepository = Depends(get_document_repository),
    chatbox_http_client: httpx.AsyncClient = Depends(get_chatbox_http_client),
) -> DocumentService:
    return DocumentService(
        document_repository=document_repository,
        chatbox_client=ChatboxClient(chatbox_http_client),
    )
