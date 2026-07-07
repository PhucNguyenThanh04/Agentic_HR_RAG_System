from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class ToolCitation:
    index: int
    chunk_id: str
    filename: str
    score: float
    document_id: str | None = None
    page: int | None = None
    section: str | None = None
    clause_number: str | None = None
    file_path: str | None = None


@dataclass
class RetrievedChunk:
    """
    Chunk đã được retrieve và rerank, dùng để build context.
    Mapping từ Qdrant payload do DocumentIndexer._build_payload tạo.
    """
    chunk_id: str
    content: str
    filename: str
    page: int | None
    section: str | None          # clause_title hoặc section header
    clause_number: str | None    # số điều, ví dụ "Điều 5"
    score: float                 # rerank score
    document_id: str | None = None
    file_path: str | None = None
    doc_type: str | None = None
    total_pages: int | None = None
    chunk_level: str | None = None
    clause_title: str | None = None

    @classmethod
    def from_qdrant_payload(
        cls,
        payload: Mapping[str, Any],
        score: float,
    ) -> "RetrievedChunk":
        """
        Tạo RetrievedChunk từ payload Qdrant.

        Helper này giữ mapping metadata ở một nơi để các module khác không phải
        biết chi tiết schema lưu trong vector store.
        """
        clause_title = _optional_str(payload.get("clause_title"))
        section = clause_title or _optional_str(payload.get("section"))

        return cls(
            chunk_id=str(payload.get("chunk_id") or ""),
            content=str(payload.get("content") or ""),
            filename=str(
                payload.get("filename")
                or payload.get("source_file")
                or "unknown"
            ),
            page=_optional_int(payload.get("page")),
            section=section,
            clause_number=_optional_str(payload.get("clause_number")),
            score=float(score),
            document_id=_optional_str(payload.get("document_id")),
            file_path=_optional_str(payload.get("file_path")),
            doc_type=_optional_str(payload.get("doc_type")),
            total_pages=_optional_int(payload.get("total_pages")),
            chunk_level=_optional_str(payload.get("chunk_level")),
            clause_title=clause_title,
        )


def build_citation_label(chunk: RetrievedChunk) -> str:
    """
    Tạo label trích dẫn từ metadata chunk.

    Ví dụ output:
        Nguồn: noi_quy_cong_ty.pdf | Trang 3 | Điều 5: Giờ làm việc
        Nguồn: chinh_sach_nghi_phep.docx | Trang 1
    """
    parts = [f"Nguồn: {chunk.filename}"]

    if chunk.page:
        parts.append(f"Trang {chunk.page}")

    section = chunk.clause_title or chunk.section

    if chunk.clause_number and section:
        parts.append(f"{chunk.clause_number}: {section}")
    elif chunk.clause_number:
        parts.append(chunk.clause_number)
    elif section:
        parts.append(section)

    return " | ".join(parts)


# ── Internal helpers ──

def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
