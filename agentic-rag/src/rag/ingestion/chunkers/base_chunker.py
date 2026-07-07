from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.rag.ingestion.loaders.base_loader import Document


@dataclass
class DocumentChunk:
    chunk_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, documents: list[Document]) -> list[DocumentChunk]:
        """
        Convert loaded Documents into smaller retrieval/indexing chunks.
        Loader loads. Chunker chunks.
        """
        ...


"""
sau bước chunk thì meta data:

{
    "document_id": "doc_001",
    "filename": "noi_quy.pdf",
    "file_path": "/uploads/docs/noi_quy.pdf",
    "api_file_path": "/uploads/docs/noi_quy.pdf",
    "original_file_path": "/uploads/docs/noi_quy.pdf",
    "allowed_roles": ["admin", "hr"],
    "source_file": "noi_quy.pdf",
    "doc_type": "pdf",
    "page": 3,
    "total_pages": 12,
    "dieu_refs": ["Điều 5."],
    "chunk_index": 0,
    "chunk_level": "clause",
    "clause_number": "1",
    "clause_title": "Quy định chung"
}

"""