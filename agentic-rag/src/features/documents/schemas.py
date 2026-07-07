from typing import Literal

from pydantic import BaseModel


class DocumentIngestResponse(BaseModel):
    document_id: str
    filename: str
    collection: str
    status: Literal["ready", "failed", "processing"]
    chunks_count: int
    vector_indexed: bool
    keyword_indexed: bool
    error_code: str | None = None
    message: str | None = None


class DocumentVectorDeleteResponse(BaseModel):
    document_id: str
    collection: str
    status: Literal["deleted"]
    deleted: bool
    message: str
