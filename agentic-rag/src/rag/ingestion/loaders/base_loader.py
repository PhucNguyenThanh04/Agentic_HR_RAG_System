from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
import unicodedata

if TYPE_CHECKING:
    from fastapi import UploadFile
else:
    UploadFile = Any


@dataclass
class Document:
    """
    Output chuẩn của mọi loader.
    Chunker downstream chỉ cần biết về class này, không cần biết file gốc là gì.
    """
    content: str
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        # NFC normalization cho tiếng Việt
        # "ệ" có thể được encode là 1 code point (NFC) hoặc "e" + combining marks (NFD)
        # BGE-M3 tokenizer expect NFC → normalize ngay tại đây
        self.content = unicodedata.normalize("NFC", self.content)


class BaseLoader(ABC):

    @abstractmethod
    def load(
        self,
        file: UploadFile,
        allowed_roles: list[Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        Load UploadFile do api-service gửi sang, trả về list[Document].
        Mỗi Document là một đơn vị logic: 1 trang PDF, 1 section DOCX, v.v.
        KHÔNG chunk ở đây — chunker làm việc đó.

        extra_metadata chứa metadata nghiệp vụ do api-service gửi sang
        như document_id, filename, file_path, allowed_roles.
        """
        ...

    def _is_empty(self, text: str) -> bool:
        return not text or not text.strip()

    def _build_metadata(
        self,
        metadata: dict[str, Any],
        allowed_roles: list[Any] | None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        api_metadata = self._normalize_extra_metadata(extra_metadata)
        roles = allowed_roles
        if roles is None:
            roles = api_metadata.get("allowed_roles")

        return {
            **api_metadata,
            **metadata,
            "allowed_roles": self._normalize_roles(roles),
        }

    def _with_allowed_roles(
        self,
        metadata: dict[str, Any],
        allowed_roles: list[Any] | None,
    ) -> dict[str, Any]:
        return self._build_metadata(metadata, allowed_roles)

    def _normalize_roles(self, roles: Any) -> list[str]:
        if roles is None:
            return []
        if isinstance(roles, (list, tuple, set)):
            return [str(role) for role in roles if role is not None]
        return [str(roles)]

    def _normalize_extra_metadata(
        self,
        extra_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        metadata = dict(extra_metadata or {})

        api_file_path = metadata.get("file_path")
        if api_file_path:
            metadata.setdefault("api_file_path", api_file_path)
            metadata.setdefault("original_file_path", api_file_path)

        if "allowed_roles" in metadata:
            metadata["allowed_roles"] = self._normalize_roles(
                metadata.get("allowed_roles")
            )

        return metadata

    def _upload_filename(
        self,
        file: UploadFile,
        extra_metadata: dict[str, Any] | None = None,
    ) -> str:
        metadata = extra_metadata or {}
        return str(metadata.get("filename") or file.filename or "uploaded_file")

    def _reset_upload_file(self, file: UploadFile) -> None:
        file.file.seek(0)
