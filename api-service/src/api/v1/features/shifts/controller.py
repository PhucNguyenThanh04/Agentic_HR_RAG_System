from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Response, status

from src.api.v1.features.shifts import schemas
from src.api.v1.features.shifts.service import (
    WorkShiftService,
    get_work_shift_service,
)
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import RoleName
from src.core.dependencies.auth import require_roles, get_current_user_or_rag_api_key

router = APIRouter(prefix="/work-shifts", tags=["Work-Shifts"])


@router.post("/", response_model=schemas.WorkShiftRead, status_code=status.HTTP_201_CREATED)
async def create_work_shift(
    payload: schemas.WorkShiftCreate,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.WorkShiftRead:
    return await service.create_work_shift(payload)


@router.get("/", response_model=list[schemas.WorkShiftRead])
async def list_work_shifts(
    search: str | None = None,
    is_active: bool | None = None,
    code: str | None = None,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> list[schemas.WorkShiftRead]:
    return await service.list_work_shifts(
        search=search,
        is_active=is_active,
        code=code,
    )


@router.get("/{shift_id}", response_model=schemas.WorkShiftRead)
async def get_work_shift(
    shift_id: int,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> schemas.WorkShiftRead:
    return await service.get_work_shift(shift_id)


@router.patch("/{shift_id}", response_model=schemas.WorkShiftRead)
async def update_work_shift(
    shift_id: int,
    payload: schemas.WorkShiftUpdate,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.WorkShiftRead:
    return await service.update_work_shift(shift_id, payload)


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_shift(
    shift_id: int,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> Response:
    await service.delete_work_shift(shift_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{shift_id}/activate", response_model=schemas.WorkShiftRead)
async def activate_work_shift(
    shift_id: int,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.WorkShiftRead:
    return await service.set_work_shift_active(shift_id=shift_id, is_active=True)


@router.patch("/{shift_id}/deactivate", response_model=schemas.WorkShiftRead)
async def deactivate_work_shift(
    shift_id: int,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.WorkShiftRead:
    return await service.set_work_shift_active(shift_id=shift_id, is_active=False)


# ── shift assignments ───────────────────────────────────────────────────────
assignment_router = APIRouter(tags=["Shift-Assignments"])


@assignment_router.post(
    "/employees/{employee_id}/shift-assignments",
    response_model=schemas.EmployeeShiftAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee_shift_assignment(
    employee_id: uuid.UUID,
    payload: schemas.EmployeeShiftAssignmentCreateForEmployee,
    service: WorkShiftService = Depends(get_work_shift_service),
    current_user: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeShiftAssignmentRead:
    return await service.create_shift_assignment(
        employee_id=employee_id,
        payload=payload,
        created_by=current_user.user_id,
    )


@assignment_router.get(
    "/employees/{employee_id}/shift-assignments",
    response_model=list[schemas.EmployeeShiftAssignmentRead],
)
async def list_employee_shift_assignments(
    employee_id: uuid.UUID,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> list[schemas.EmployeeShiftAssignmentRead]:
    return await service.list_employee_shift_assignments(employee_id)


@assignment_router.get(
    "/employees/{employee_id}/current-shift",
    response_model=schemas.CurrentShiftRead,
)
async def get_employee_current_shift(
    employee_id: uuid.UUID,
    as_of: date | None = None,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(get_current_user_or_rag_api_key),
) -> schemas.CurrentShiftRead:
    return await service.get_current_shift(employee_id=employee_id, as_of=as_of)


@assignment_router.post(
    "/employees/{employee_id}/change-shift",
    response_model=schemas.EmployeeShiftAssignmentRead,
)
async def change_employee_shift(
    employee_id: uuid.UUID,
    payload: schemas.ChangeShiftPayload,
    service: WorkShiftService = Depends(get_work_shift_service),
    current_user: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeShiftAssignmentRead:
    return await service.change_employee_shift(
        employee_id=employee_id,
        payload=payload,
        created_by=current_user.user_id,
    )


@assignment_router.patch(
    "/shift-assignments/{assignment_id}",
    response_model=schemas.EmployeeShiftAssignmentRead,
)
async def update_shift_assignment(
    assignment_id: int,
    payload: schemas.EmployeeShiftAssignmentUpdate,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeShiftAssignmentRead:
    return await service.update_shift_assignment(assignment_id, payload)


@assignment_router.patch(
    "/shift-assignments/{assignment_id}/close",
    response_model=schemas.EmployeeShiftAssignmentRead,
)
async def close_shift_assignment(
    assignment_id: int,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeShiftAssignmentRead:
    return await service.close_shift_assignment(assignment_id)


@assignment_router.delete(
    "/shift-assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_shift_assignment(
    assignment_id: int,
    service: WorkShiftService = Depends(get_work_shift_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> Response:
    await service.delete_shift_assignment(assignment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
