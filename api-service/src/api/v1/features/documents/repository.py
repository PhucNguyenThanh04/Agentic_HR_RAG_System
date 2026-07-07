from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.features.documents import schemas
from src.api.v1.features.documents.models import Document
from src.api.v1.shared.enums import DocumentStatus
from src.core.db.database import get_db
from src.core.exceptions import DatabaseException, NotFoundException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class DocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_document_by_id(self, document_id: uuid.UUID) -> Document | None:
        return await self.db.scalar(select(Document).where(Document.id == document_id))

    async def get_document_or_404(self, document_id: uuid.UUID) -> Document:
        document = await self.get_document_by_id(document_id)
        if document is None:
            raise NotFoundException("Document")
        return document

    async def create_processing_document(
        self,
        *,
        document_id: uuid.UUID,
        title: str,
        file_name: str,
        file_url: str,
        file_type: str,
        uploaded_by: uuid.UUID,
        allowed_roles: list[str],
        qdrant_collection: str,
    ) -> Document:
        document = Document(
            id=document_id,
            title=title,
            file_name=file_name,
            file_url=file_url,
            file_type=file_type,
            uploaded_by=uploaded_by,
            allowed_roles=allowed_roles,
            status=DocumentStatus.processing,
            chunk_count=0,
            qdrant_collection=qdrant_collection,
        )
        self.db.add(document)
        try:
            await self.db.commit()
            await self.db.refresh(document)
            return document
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to create document: document_id=%s", document_id)
            raise DatabaseException("Failed to create document") from exc

    async def mark_ready(
        self,
        *,
        document_id: uuid.UUID,
        chunk_count: int,
        qdrant_collection: str,
    ) -> Document:
        document = await self.get_document_or_404(document_id)
        document.status = DocumentStatus.ready
        document.chunk_count = chunk_count
        document.qdrant_collection = qdrant_collection
        try:
            await self.db.commit()
            await self.db.refresh(document)
            return document
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to mark document ready: document_id=%s", document_id)
            raise DatabaseException("Failed to update document") from exc

    async def delete_document(self, document_id: uuid.UUID) -> None:
        document = await self.get_document_or_404(document_id)
        try:
            await self.db.delete(document)
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to delete document: document_id=%s", document_id)
            raise DatabaseException("Failed to delete document") from exc

    async def list_documents(
        self,
        query: schemas.DocumentListQuery,
    ) -> tuple[list[Document], int]:
        stmt: Select = select(Document)

        if query.search:
            term = query.search.strip().lower()
            stmt = stmt.where(
                or_(
                    func.lower(Document.title).like(f"%{term}%"),
                    func.lower(Document.file_name).like(f"%{term}%"),
                )
            )
        if query.uploaded_by is not None:
            stmt = stmt.where(Document.uploaded_by == query.uploaded_by)
        if query.allowed_role:
            stmt = stmt.where(Document.allowed_roles.any(query.allowed_role.strip()))
        if query.status is not None:
            stmt = stmt.where(Document.status == query.status)
        if query.file_type:
            stmt = stmt.where(func.lower(Document.file_type) == query.file_type.lower())
        if query.created_from is not None:
            stmt = stmt.where(Document.created_at >= query.created_from)
        if query.created_to is not None:
            stmt = stmt.where(Document.created_at <= query.created_to)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(await self.db.scalar(total_stmt) or 0)
        stmt = (
            stmt.order_by(Document.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total


def get_document_repository(
    db: AsyncSession = Depends(get_db),
) -> DocumentRepository:
    return DocumentRepository(db)
