from __future__ import annotations

from typing import Any
from dataclasses import dataclass

from fastapi import UploadFile

from src.rag.ingestion.loaders.base_loader import Document
from src.rag.ingestion.chunkers.base_chunker import DocumentChunk
from src.rag.ingestion.loaders.factory_loader import LoaderFactory
from src.rag.ingestion.chunkers.legachunker import LegalStructureAwareChunker
from src.rag.ingestion.indexer import DocumentIndexer
from src.integrations.qdrant.client import QdrantClientManager



from src.core.setup_logging import setup_logger
from src.core.settings import get_settings

settings = get_settings()

logger = setup_logger(__name__)

@dataclass
class IngestionResult:
    document_id: str
    filename: str
    collection: str
    status: str
    chunks_count: int
    vector_indexed: bool
    keyword_indexed: bool
    error_code: str | None = None
    message: str | None = None

class IngestionPipeline:
    def __init__(
        self,
        loader: type[LoaderFactory],
        chunker: LegalStructureAwareChunker,
        indexer: DocumentIndexer,
        qdrant_manager: QdrantClientManager | None = None,
    ) -> None:
        self.loader = loader
        self.chunker = chunker
        self.indexer = indexer
        self.qdrant_manager = qdrant_manager

    
    async def ingestion(
        self,
        file: UploadFile,
        document_id: str,
        filename: str,
        allowed_roles: list[Any],
        file_path: str,
        collection_name: str | None = None,
        batch_size: int | None = None,
    ) -> IngestionResult:
        collection = collection_name or settings.default_qdrant_collection

        documents = await self._load_documents(
            file=file,
            allowed_roles=allowed_roles,
            document_id=document_id,
            filename=filename,
            file_path=file_path,
        )

        chunks = await self._chunk_documents(documents)

        if self.qdrant_manager is not None:
            await self.qdrant_manager.ensure_collection(collection)

        indexed_count = await self._index_chunks(
            collection_name=collection,
            document_id=document_id,
            filename=filename,
            chunks=chunks,
            language="vi",
            batch_size=batch_size,
        )

        return IngestionResult(
            document_id=document_id,
            filename=filename,
            collection=collection,
            status="ready",
            chunks_count=indexed_count,
            vector_indexed=indexed_count > 0,
            keyword_indexed=indexed_count > 0,
            message="Document indexed successfully",
        )
    
        

    async def delete_document(
        self,
        document_id: str,
        collection_name: str | None = None,
    ) -> bool:
        try:
            await self.indexer.delete_document(
                document_id=document_id,
                collection_name=collection_name or settings.default_qdrant_collection,
            )
            logger.info(f"Deleted document {document_id} from index")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_id} from index: {e}")
            return False
    
    async def _index_chunks(self,
        collection_name: str,
        document_id: str,
        filename: str,
        chunks: list[DocumentChunk],
        language: str = "vi",
        batch_size: int | None = None,
    )-> int:
        try:
            indexed_count = await self.indexer.index_chunks(
                collection_name=collection_name,
                document_id=document_id,
                filename=filename,
                chunks=chunks,
                language=language,
                batch_size=batch_size,
            )
            logger.info(f"Indexed {indexed_count}/{len(chunks)} chunks for document {filename} (ID: {document_id})")
            return indexed_count
        except Exception as e:
            logger.error(f"Failed to index chunks for document {filename} (ID: {document_id}): {e}")
            raise

    async def _validate_input(
        self,
        file: UploadFile,
        allowed_roles: list[Any],
        document_id: str,  
        filename: str,
        file_path: str,
    ) -> None:
        if not file:
            raise ValueError("file is required")
        if not allowed_roles:
            raise ValueError("allowed_roles is required")
        if not file_path:
            raise ValueError("file_path is required")

        if not filename:
            raise ValueError("filename is required")

        if not document_id:
            raise ValueError("document_id is required")


    async def _chunk_documents(self,
        documents: list[Document],
    ) -> list[DocumentChunk]:
        try: 
            chunk = self.chunker.chunk(documents)
            logger.info(f"Chunked into {len(chunk)} chunks")
            return chunk
        except Exception as e:
            logger.error(f"Failed to chunk documents: {e}")
            raise
    
    async def _load_documents(self, 
        file: UploadFile,
        allowed_roles: list[Any],
        document_id: str,  
        filename: str,
        file_path: str,
    ) -> list[Document]:
        await self._validate_input(file, allowed_roles, document_id, filename, file_path)
        extra_metadata = {
            "document_id": document_id,
            "filename": filename,
            "file_path": file_path,
            "allowed_roles": allowed_roles,
        }
        try: 
            documents = self.loader.load(
                file=file,
                allowed_roles=allowed_roles,
                extra_metadata=extra_metadata,
            )
            logger.info(f"Loaded {len(documents)} documents from {filename} (ID: {document_id})")
            return documents
        except Exception as e:
            logger.error(f"Failed to load document {filename} (ID: {document_id}): {e}")
            raise




    
        

    
