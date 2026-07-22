from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core.settings import get_settings
from src.rag.retrieval.retrieval_pipeline import (
    RetrievalPipeline,
    RetrievalPipelineResult,
)
from src.tools.base_tool import BaseTool, ToolCitation, ToolResult

settings = get_settings()
logger = logging.getLogger(__name__)

RetrievalQueryStrategy = Literal["dual_parallel", "fallback"]
RewriteStatus = Literal["accepted", "not_needed", "rejected"]
MIN_REWRITE_QUERY_CHARS = 3
MAX_REWRITE_QUERY_CHARS = 1000

_PROTECTED_LITERAL_PATTERNS = (
    re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{1,4}[-/.]\d{1,2}(?:[-/.]\d{1,4})?\b"),
    re.compile(r"\b\d+(?:[.,]\d+)?%?\b"),
    re.compile(
        r"\b(?=[A-Za-z0-9_-]*[A-Za-z])"
        r"(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{3,}\b"
    ),
)


class VectorSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        description="Câu hỏi hoặc từ khóa cần tìm trong tài liệu nội bộ.",
    )
    preserved_terms: list[str] = Field(
        default_factory=list,
        description=(
            "Các thuật ngữ quan trọng lấy nguyên văn từ câu hỏi gốc và phải "
            "được giữ lại trong query."
        ),
    )


@dataclass(frozen=True)
class RewriteValidationResult:
    status: RewriteStatus
    query: str | None
    rejection_reason: str | None = None


@dataclass
class RetrievalDecision:
    result: RetrievalPipelineResult
    selected_query_source: Literal["original", "rewrite"]
    attempts: dict[str, RetrievalPipelineResult]
    rewrite_validation: RewriteValidationResult
    fallback_reason: str | None
    evidence_status: Literal["sufficient", "insufficient"]


class VectorSearchTool(BaseTool):
    name = "vector_search"
    description = (
        "Tìm kiếm thông tin trong tài liệu nội bộ bằng vector/RAG search. "
        "Dùng khi cần tra cứu chính sách, nội quy, quy trình hoặc tài liệu đã index."
    )
    usage_hint = (
        "Tìm nội quy, chính sách, quy định trong tài liệu. "
        "Nếu câu hỏi đã rõ thì giữ nguyên query. Khi viết lại, không đổi số, ngày, "
        "mã, tên riêng hoặc thuật ngữ quan trọng; khai báo chúng trong preserved_terms."
    )
    input_example = (
        '{"query":"câu hỏi đầy đủ, giữ cụm từ chính của người dùng",'
        '"preserved_terms":["thuật ngữ quan trọng"]}'
    )
    args_schema = VectorSearchInput

    def __init__(
        self,
        retrieval_pipeline: RetrievalPipeline,
        allowed_role: str,
        original_query: str | None = None,
        retrieval_strategy: RetrievalQueryStrategy | None = None,
        rewrite_fallback_score: float | None = None,
    ) -> None:
        self.retrieval_pipeline = retrieval_pipeline
        self.allowed_role = allowed_role
        self.original_query = (original_query or "").strip()
        self.retrieval_strategy = retrieval_strategy or settings.retrieval_query_strategy
        self.rewrite_fallback_score = (
            rewrite_fallback_score
            if rewrite_fallback_score is not None
            else settings.retrieval_rewrite_fallback_score
        )
        if (
            self.retrieval_strategy == "fallback"
            and self.rewrite_fallback_score is None
        ):
            raise ValueError(
                "rewrite_fallback_score is required for fallback retrieval strategy"
            )

    async def run(
        self,
        query: str,
        preserved_terms: list[str] | None = None,
    ) -> ToolResult:
        query = query.strip()
        if not query:
            return ToolResult(
                observation="Không có truy vấn để tìm kiếm trong tài liệu nội bộ.",
                outcome="error",
                retryable=False,
            )

        decision = await self._retrieve_context(
            rewritten_query=query,
            preserved_terms=preserved_terms or [],
        )
        result = decision.result
        metadata = self._build_metadata(decision)
        logger.info(
            "Vector search decision | strategy=%s selected_source=%s "
            "attempts=%d rewrite_status=%s fallback_reason=%s "
            "evidence_status=%s attempt_metrics=%s",
            metadata["retrieval_strategy"],
            metadata["selected_query_source"],
            metadata["retrieval_attempt_count"],
            metadata["rewrite_status"],
            metadata["fallback_reason"],
            metadata["evidence_status"],
            metadata["retrieval_attempts"],
        )

        if decision.evidence_status == "insufficient":
            return ToolResult(
                observation=(
                    "Không tìm thấy bằng chứng đủ tin cậy trong tài liệu nội bộ. "
                    "Evidence status: insufficient. Nếu câu hỏi còn thiếu chủ thể, "
                    "loại chính sách, mốc thời gian hoặc có tham chiếu chưa rõ, hãy "
                    "dùng ask_user để làm rõ. Nếu câu hỏi đã cụ thể, hãy trả lời rằng "
                    "chưa tìm thấy thông tin phù hợp và không suy đoán."
                ),
                outcome="empty",
                used_context=False,
                low_confidence=True,
                metadata={
                    **metadata,
                    "tool": self.name,
                    "result_count": 0,
                    "query_complete": True,
                },
            )

        return ToolResult(
            observation=self._format_result(result),
            citations=[
                ToolCitation(
                    index=citation.index,
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    filename=citation.filename,
                    page=citation.page,
                    section=citation.section,
                    clause_number=citation.clause_number,
                    score=citation.score,
                    file_path=citation.file_path,
                )
                for citation in result.citations
            ],
            used_context=True,
            low_confidence=result.low_confidence,
            metadata={
                **metadata,
                "tool": self.name,
                "result_count": len(result.chunks),
                "query_complete": True,
            },
        )

    async def _retrieve_context(
        self,
        rewritten_query: str,
        preserved_terms: list[str],
    ) -> RetrievalDecision:
        original_query = self.original_query or rewritten_query
        validation = validate_rewritten_query(
            original_query=original_query,
            rewritten_query=rewritten_query,
            preserved_terms=preserved_terms,
        )

        if self.retrieval_strategy == "dual_parallel":
            return await self._retrieve_dual_parallel(
                original_query=original_query,
                validation=validation,
            )
        return await self._retrieve_with_fallback(
            original_query=original_query,
            validation=validation,
        )

    async def _retrieve_dual_parallel(
        self,
        original_query: str,
        validation: RewriteValidationResult,
    ) -> RetrievalDecision:
        if validation.status != "accepted" or validation.query is None:
            original_result = await self._retrieve_one(original_query)
            attempts = {"original": original_result}
        else:
            original_result, rewrite_result = await asyncio.gather(
                self._retrieve_one(original_query),
                self._retrieve_one(validation.query),
            )
            attempts = {
                "original": original_result,
                "rewrite": rewrite_result,
            }

        selected_source, selected_result = self._select_best_result(attempts)
        return RetrievalDecision(
            result=selected_result,
            selected_query_source=selected_source,
            attempts=attempts,
            rewrite_validation=validation,
            fallback_reason=None,
            evidence_status=(
                "sufficient"
                if self._has_usable_context(selected_result)
                else "insufficient"
            ),
        )

    async def _retrieve_with_fallback(
        self,
        original_query: str,
        validation: RewriteValidationResult,
    ) -> RetrievalDecision:
        original_result = await self._retrieve_one(original_query)
        attempts = {"original": original_result}
        fallback_reason = self._fallback_reason(original_result)

        if (
            fallback_reason is not None
            and validation.status == "accepted"
            and validation.query is not None
        ):
            attempts["rewrite"] = await self._retrieve_one(validation.query)

        selected_source, selected_result = self._select_best_result(attempts)
        threshold = self.rewrite_fallback_score
        evidence_is_sufficient = (
            self._has_usable_context(selected_result)
            and threshold is not None
            and self._best_score(selected_result) >= threshold
        )
        return RetrievalDecision(
            result=selected_result,
            selected_query_source=selected_source,
            attempts=attempts,
            rewrite_validation=validation,
            fallback_reason=fallback_reason,
            evidence_status=(
                "sufficient" if evidence_is_sufficient else "insufficient"
            ),
        )

    async def _retrieve_one(self, query: str) -> RetrievalPipelineResult:
        return await self.retrieval_pipeline.retrieve_context(
            query=query,
            allowed_role=self.allowed_role,
        )

    def _fallback_reason(self, result: RetrievalPipelineResult) -> str | None:
        if not self._has_usable_context(result):
            return result.status
        threshold = self.rewrite_fallback_score
        if threshold is not None and self._best_score(result) < threshold:
            return "best_score_below_fallback_threshold"
        return None

    @classmethod
    def _select_best_result(
        cls,
        attempts: dict[str, RetrievalPipelineResult],
    ) -> tuple[Literal["original", "rewrite"], RetrievalPipelineResult]:
        source, result = max(
            attempts.items(),
            key=lambda item: (
                cls._has_usable_context(item[1]),
                cls._best_score(item[1]),
            ),
        )
        return ("rewrite" if source == "rewrite" else "original"), result

    @staticmethod
    def _best_score(result: RetrievalPipelineResult) -> float:
        if result.best_score is not None:
            return result.best_score
        return max((citation.score for citation in result.citations), default=0.0)

    @staticmethod
    def _has_usable_context(result: RetrievalPipelineResult) -> bool:
        return (
            result.status == "success"
            and result.used_context
            and bool(result.chunks)
        )

    def _build_metadata(self, decision: RetrievalDecision) -> dict[str, object]:
        validation = decision.rewrite_validation
        return {
            "retrieval_strategy": self.retrieval_strategy,
            "selected_query_source": decision.selected_query_source,
            "retrieval_attempt_count": len(decision.attempts),
            "rewrite_status": validation.status,
            "rewrite_rejection_reason": validation.rejection_reason,
            "fallback_reason": decision.fallback_reason,
            "evidence_status": decision.evidence_status,
            "retrieval_attempts": {
                source: {
                    "status": result.status,
                    "candidate_count": result.candidate_count,
                    "qualified_count": result.qualified_count,
                    "selected_chunk_count": result.selected_chunk_count,
                    "best_score": result.best_score,
                    "latency_ms": result.latency_ms,
                }
                for source, result in decision.attempts.items()
            },
        }

    def _format_result(self, result: RetrievalPipelineResult) -> str:
        citation_by_index = {
            citation.index: citation
            for citation in result.citations
        }

        lines = ["Kết quả tìm kiếm:"]

        for index, chunk in enumerate(result.chunks, start=1):
            citation = citation_by_index.get(index)
            filename = citation.filename if citation else chunk.filename
            page = citation.page if citation else chunk.page
            section = citation.section if citation else chunk.section
            clause_number = citation.clause_number if citation else chunk.clause_number

            source_parts = []
            if clause_number and section:
                source_parts.append(f"{clause_number} - {section}")
            elif clause_number:
                source_parts.append(clause_number)
            elif section:
                source_parts.append(section)
            source_parts.append(filename)
            if page:
                source_parts.append(f"Trang {page}")

            lines.extend(
                [
                    "",
                    f"[{index}] {' | '.join(source_parts)}",
                    chunk.content.strip(),
                ]
            )

        return "\n".join(lines)


def validate_rewritten_query(
    original_query: str,
    rewritten_query: str,
    preserved_terms: list[str] | None = None,
) -> RewriteValidationResult:
    original = _normalize_query(original_query)
    rewritten = _normalize_query(rewritten_query)

    if not rewritten:
        return RewriteValidationResult("rejected", None, "empty_query")
    if len(rewritten) < MIN_REWRITE_QUERY_CHARS:
        return RewriteValidationResult("rejected", None, "query_too_short")
    if len(rewritten) > MAX_REWRITE_QUERY_CHARS:
        return RewriteValidationResult("rejected", None, "query_too_long")
    if rewritten == original:
        return RewriteValidationResult("not_needed", None)

    for term in preserved_terms or []:
        normalized_term = _normalize_query(term)
        if not normalized_term:
            continue
        if normalized_term not in original:
            return RewriteValidationResult(
                "rejected",
                None,
                "preserved_term_not_in_original",
            )
        if normalized_term not in rewritten:
            return RewriteValidationResult(
                "rejected",
                None,
                "preserved_term_missing_from_rewrite",
            )

    original_literals = _extract_protected_literals(original)
    rewritten_literals = _extract_protected_literals(rewritten)
    if original_literals - rewritten_literals:
        return RewriteValidationResult(
            "rejected",
            None,
            "protected_literal_removed",
        )
    if rewritten_literals - original_literals:
        return RewriteValidationResult(
            "rejected",
            None,
            "protected_literal_added",
        )

    return RewriteValidationResult("accepted", rewritten_query.strip())


def _normalize_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return " ".join(normalized.casefold().split())


def _extract_protected_literals(value: str) -> set[str]:
    return {
        match.group(0).casefold()
        for pattern in _PROTECTED_LITERAL_PATTERNS
        for match in pattern.finditer(value)
    }
