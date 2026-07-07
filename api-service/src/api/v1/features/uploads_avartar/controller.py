import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends

from src.core.dependencies.auth import get_current_user
from src.api.v1.features.users.models import User
from src.core.exceptions import BadRequestException

router = APIRouter(prefix="/upload", tags=["Upload"])

BASE_DIR = Path(__file__).resolve().parents[5]
UPLOAD_DIR = BASE_DIR / "uploads" / "avatars"
ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


async def _save_avatar_image(file: UploadFile) -> dict[str, str]:
    if file.content_type not in ALLOWED_TYPES:
        raise BadRequestException("Only JPG and PNG images are allowed")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise BadRequestException("File size must be less than 5MB")

    if not content:
        raise BadRequestException("Empty file is not allowed")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    extension = ALLOWED_TYPES[file.content_type]
    filename = f"{uuid.uuid4()}{extension}"
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(content)

    return {
        "image_url": f"/uploads/avatars/{filename}",
        "filename": filename,
    }


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
) -> dict[str, str]:
    return await _save_avatar_image(file)


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
) -> dict[str, str]:
    return await _save_avatar_image(file)
