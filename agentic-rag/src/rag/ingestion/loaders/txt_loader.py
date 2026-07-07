from typing import Any


from src.rag.ingestion.loaders.base_loader import BaseLoader, Document, UploadFile
from src.core.setup_logging import setup_logger

logger = setup_logger(__name__)
# Thứ tự thử encoding: UTF-8 trước, sau đó Windows Vietnamese (CP1258),
# sau đó Latin-1 làm fallback cuối cùng (không bao giờ raise UnicodeDecodeError)
_ENCODINGS = ["utf-8", "cp1258", "latin-1"]


class TxtLoader(BaseLoader):
    """
    Load plain text file.

    Split theo double newline (paragraph break).
    Mỗi paragraph = 1 Document, giữ nguyên thứ tự.

    Dùng cho: văn bản đã copy-paste từ web, export từ tools khác.
    """

    def load(
        self,
        file: UploadFile,
        allowed_roles: list[Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        filename = self._upload_filename(file, extra_metadata)
        content = self._read_upload_with_encoding_fallback(file)

        # Split theo paragraph (2+ newlines liên tiếp)
        # strip từng paragraph, bỏ qua paragraph rỗng
        paragraphs = [
            p.strip()
            for p in content.split("\n\n")
            if p.strip()
        ]

        if not paragraphs:
            raise ValueError(f"'{filename}' is empty.")
        logger.info(f"Loaded {len(paragraphs)} paragraphs from TXT '{filename}'")

        return [
            Document(
                content=para,
                metadata=self._build_metadata(
                    {
                        "source_file":  filename,
                        "doc_type":     "txt",
                        "paragraph":    idx + 1,
                        "total_paras":  len(paragraphs),
                    },
                    allowed_roles,
                    extra_metadata,
                ),
            )
            for idx, para in enumerate(paragraphs)
        ]

    def _read_upload_with_encoding_fallback(self, file: UploadFile) -> str:
        self._reset_upload_file(file)
        content = file.file.read()

        for encoding in _ENCODINGS:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        # Không bao giờ reach đây vì latin-1 decode được mọi byte
        raise ValueError(f"Cannot decode '{file.filename}'")
