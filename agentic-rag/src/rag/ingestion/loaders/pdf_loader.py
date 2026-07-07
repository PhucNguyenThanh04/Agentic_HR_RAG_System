import re
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.rag.ingestion.loaders.base_loader import BaseLoader, Document, UploadFile

from src.core.setup_logging import setup_logger

logger = setup_logger(__name__)

# Regex nhận diện ranh giới "Điều X" trong văn bản pháp luật VN
_DIEU_PATTERN = re.compile(r"(Điều\s+\d+[\.\:])", re.UNICODE)


class PDFLoader(BaseLoader):

    def load(
        self,
        file: UploadFile,
        allowed_roles: list[Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        filename = self._upload_filename(file, extra_metadata)

        try:
            self._reset_upload_file(file)
            reader = PdfReader(file.file)
        except PdfReadError as e:
            raise ValueError(f"Cannot read PDF '{filename}': {e}") from e

        total_pages = len(reader.pages)
        docs: list[Document] = []

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""

            if self._is_empty(text):
                continue

            # Detect xem trang này có "Điều X" không → thêm vào metadata
            # để chunker sau có thể dùng thông tin này
            dieu_matches = _DIEU_PATTERN.findall(text)

            docs.append(Document(
                content=text.strip(),
                metadata=self._build_metadata(
                    {
                        "source_file":  filename,
                        "doc_type":     "pdf",
                        "page":         page_num,
                        "total_pages":  total_pages,
                        # Danh sách các "Điều" xuất hiện trên trang, dùng để filter sau
                        "dieu_refs":    dieu_matches if dieu_matches else [],
                    },
                    allowed_roles,
                    extra_metadata,
                ),
            ))

        if not docs:
            raise ValueError(
                f"'{filename}' appears to be a scanned PDF (no text layer). "
                "OCR is required for this file type."
            )
        logger.info(f"Loaded {len(docs)} pages from PDF '{filename}'")

        return docs
