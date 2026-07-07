from pathlib import Path
from typing import Any

from src.rag.ingestion.loaders.base_loader import BaseLoader, Document, UploadFile
from src.rag.ingestion.loaders.pdf_loader import PDFLoader
from src.rag.ingestion.loaders.docx_loader import DocxLoader
from src.rag.ingestion.loaders.txt_loader import TxtLoader


class UnsupportedFileTypeError(ValueError):
    def __init__(self, extension: str, supported: list[str]):
        super().__init__(
            f"No loader registered for '{extension}'. "
            f"Supported: {supported}"
        )


class LoaderFactory:
    """
    Registry-based factory.

    Dùng registry thay vì if/elif vì:
    - Thêm loader mới không cần sửa factory (Open/Closed Principle)
    - Có thể list supported types ở runtime
    - Dễ mock trong tests

    Usage:
        docs = LoaderFactory.load(
            file,
            allowed_roles=allowed_roles,
            extra_metadata={"document_id": "..."},
        )

        # Hoặc lấy loader instance nếu cần inspect:
        loader = LoaderFactory.get_loader(".pdf")
        docs = loader.load(path)

        # Đăng ký loader mới (e.g. xlsx):
        LoaderFactory.register(".xlsx", ExcelLoader)
    """

    # extension → loader class (chưa instantiate)
    _registry: dict[str, type[BaseLoader]] = {}
    _content_type_extensions: dict[str, str] = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/plain": ".txt",
    }

    @classmethod
    def register(cls, extension: str, loader_class: type[BaseLoader]) -> None:
        """Đăng ký loader cho một file extension."""
        ext = extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        cls._registry[ext] = loader_class

    @classmethod
    def get_loader(cls, extension: str) -> BaseLoader:
        """Trả về loader instance cho extension đã cho."""
        ext = extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"

        loader_class = cls._registry.get(ext)
        if loader_class is None:
            raise UnsupportedFileTypeError(
                extension=ext,
                supported=list(cls._registry.keys()),
            )
        return loader_class()

    @classmethod
    def load(
        cls,
        file: UploadFile,
        allowed_roles: list[Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        Load UploadFile, tự chọn loader phù hợp theo filename/extension.
        Đây là method chính — hầu hết code sẽ gọi cái này.
        """
        extension = cls._detect_extension(file, extra_metadata)

        loader = cls.get_loader(extension)
        return loader.load(
            file,
            allowed_roles=allowed_roles,
            extra_metadata=extra_metadata,
        )

    @classmethod
    def _detect_extension(
        cls,
        file: UploadFile,
        extra_metadata: dict[str, Any] | None = None,
    ) -> str:
        upload_filename = str(getattr(file, "filename", "") or "")
        extension = Path(upload_filename).suffix.lower()
        if extension:
            return extension

        metadata_filename = str((extra_metadata or {}).get("filename") or "")
        extension = Path(metadata_filename).suffix.lower()
        if extension:
            return extension

        content_type = str(getattr(file, "content_type", "") or "")
        return cls._content_type_extensions.get(content_type, "")

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return list(cls._registry.keys())


# ── Đăng ký các loaders mặc định ─────────────────────────────────────────────
LoaderFactory.register(".pdf",  PDFLoader)
LoaderFactory.register(".docx", DocxLoader)
LoaderFactory.register(".txt",  TxtLoader)



"""
sau khi loader thì có meta data:

{
    "document_id": "...",
    "filename": "...",
    "file_path": "...",              # path bên api-service, chỉ để metadata/citation
    "api_file_path": "...",
    "original_file_path": "...",
    "allowed_roles": [...],
    "source_file": "...",            # tên file upload, không phải path để đọc
    "doc_type": "pdf|docx|txt"
}

"""
