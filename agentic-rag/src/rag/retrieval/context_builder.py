from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

try:
    import tiktoken
except ImportError:
    tiktoken = None

from src.rag.retrieval.schemas import RetrievedChunk
from src.integrations.qdrant.store import QdrantSearchResult


DEFAULT_MAX_CONTEXT_TOKENS = 3000


@dataclass
class ContextCitation:
    index: int
    chunk_id: str
    document_id: str | None
    filename: str
    page: int | None
    section: str | None
    clause_number: str | None
    score: float
    file_path: str | None = None


@dataclass
class ContextBuildResult:
    context: str
    citations: list[ContextCitation]
    chunks: list[RetrievedChunk]
    token_count: int


class ContextBuilder:
    """
    Build prompt-ready context from reranked retrieval results.

    Assumptions:
    - Permission filtering already happened in retrieval.
    - Quality threshold check belongs to ChatService, not here.
    """

    def build(
        self,
        results: list[QdrantSearchResult],
        max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    ) -> ContextBuildResult:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be greater than 0")

        if not results:
            return ContextBuildResult(
                context="",
                citations=[],
                chunks=[],
                token_count=0,
            )

        selected_chunks = self._select_chunks_by_budget(results, max_tokens)
        ordered_chunks = self._lost_in_middle_order(selected_chunks)
        context, citations, token_count = self._format_context(ordered_chunks)

        return ContextBuildResult(
            context=context,
            citations=citations,
            chunks=ordered_chunks,
            token_count=token_count,
        )

    def _select_chunks_by_budget(
        self,
        results: list[QdrantSearchResult],
        max_tokens: int,
    ) -> list[RetrievedChunk]:
        selected: list[RetrievedChunk] = []
        used_tokens = 0

        for result in results:
            chunk = self._to_retrieved_chunk(result)
            block = self._format_chunk_block(index=len(selected) + 1, chunk=chunk)
            block_tokens = self._count_tokens(block)

            if used_tokens + block_tokens > max_tokens:
                continue

            selected.append(chunk)
            used_tokens += block_tokens

        return selected

    def _to_retrieved_chunk(self, result: QdrantSearchResult) -> RetrievedChunk:
        payload: dict[str, Any] = {
            **result.metadata,
            "chunk_id": result.metadata.get("chunk_id") or result.point_id,
            "content": result.content,
        }
        return RetrievedChunk.from_qdrant_payload(
            payload=payload,
            score=result.score,
        )

    def _lost_in_middle_order(
        self,
        chunks: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        head: list[RetrievedChunk] = []
        tail: list[RetrievedChunk] = []

        for index, chunk in enumerate(chunks):
            if index % 2 == 0:
                head.append(chunk)
            else:
                tail.append(chunk)

        return head + list(reversed(tail))

    def _format_context(
        self,
        chunks: list[RetrievedChunk],
    ) -> tuple[str, list[ContextCitation], int]:
        blocks: list[str] = []
        citations: list[ContextCitation] = []

        for index, chunk in enumerate(chunks, start=1):
            blocks.append(self._format_chunk_block(index=index, chunk=chunk))
            citations.append(self._build_citation(index=index, chunk=chunk))

        context = "\n\n".join(blocks)
        return context, citations, self._count_tokens(context)

    def _format_chunk_block(self, index: int, chunk: RetrievedChunk) -> str:
        return f"[{index}] {self._build_citation_label(chunk)}\n{chunk.content.strip()}"

    def _build_citation(
        self,
        index: int,
        chunk: RetrievedChunk,
    ) -> ContextCitation:
        return ContextCitation(
            index=index,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            filename=chunk.filename,
            page=chunk.page,
            section=chunk.section,
            clause_number=chunk.clause_number,
            score=chunk.score,
            file_path=chunk.file_path,
        )

    def _build_citation_label(self, chunk: RetrievedChunk) -> str:
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

    def _count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if tiktoken is None:
            return max(1, len(text) // 4)
        return len(_encoding().encode(text))


@lru_cache(maxsize=1)
def _encoding():
    if tiktoken is None:
        raise RuntimeError("tiktoken is not installed")
    return tiktoken.get_encoding("cl100k_base")
