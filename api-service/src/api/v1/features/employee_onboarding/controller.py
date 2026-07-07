from fastapi import APIRouter, Depends, File, UploadFile, status

from src.api.v1.features.employee_onboarding import schemas
from src.api.v1.features.employee_onboarding.service import (
    EmployeeOnboardingService,
    get_employee_onboarding_service,
)
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import RoleName
from src.core.dependencies.auth import require_roles
from src.utils.exeptions import BadRequestException

router = APIRouter(prefix="/employee-onboarding", tags=["Employee Onboarding"])


@router.post(
    "/start-session",
    response_model=schemas.EmployeeOnboardingStartSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_onboarding_session(
    payload: schemas.EmployeeOnboardingStartSessionRequest,
    service: EmployeeOnboardingService = Depends(get_employee_onboarding_service),
    current_user: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeOnboardingStartSessionResponse:
    return await service.start_onboarding_session(
        payload=payload,
        created_by=current_user.user_id,
    )


@router.post(
    "/{session_id}/images",
    response_model=schemas.EmployeeOnboardingPhotoUploadResponse,
)
async def upload_onboarding_image(
    session_id: str,
    file: UploadFile = File(...),
    service: EmployeeOnboardingService = Depends(get_employee_onboarding_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeOnboardingPhotoUploadResponse:
    image_bytes = await file.read()
    if not image_bytes:
        raise BadRequestException("Empty file is not allowed")

    content_type = file.content_type or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise BadRequestException("File must be an image")

    return await service.upload_photo_to_session(
        session_id=session_id,
        image_bytes=image_bytes,
        filename=file.filename or "face.jpg",
        content_type=content_type,
    )


@router.post(
    "/commit",
    response_model=schemas.EmployeeOnboardingCommitResponse,
)
async def commit_onboarding_session(
    payload: schemas.EmployeeOnboardingCommitRequest,
    service: EmployeeOnboardingService = Depends(get_employee_onboarding_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeOnboardingCommitResponse:
    return await service.commit_onboarding_session(payload.session_id)


@router.post(
    "/{session_id}/cancel",
    response_model=schemas.EmployeeOnboardingCancelResponse,
)
async def cancel_onboarding_session(
    session_id: str,
    service: EmployeeOnboardingService = Depends(get_employee_onboarding_service),
    current_user: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeOnboardingCancelResponse:
    return await service.cancel_onboarding_session(
        session_id=session_id,
        cancelled_by=current_user.user_id,
    )
