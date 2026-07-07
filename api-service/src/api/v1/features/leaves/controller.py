from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from src.api.v1.features.leaves import schemas
from src.api.v1.features.leaves.service import LeaveService, get_leave_service
from src.api.v1.features.staff.models import Employee
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import RoleName
from src.core.dependencies.auth import get_current_employee, get_current_user, require_roles

router = APIRouter(prefix="/leaves", tags=["Leaves"])


@router.get("/types", response_model=list[schemas.LeaveTypeRead])
async def list_leave_types(
    service: LeaveService = Depends(get_leave_service),
    _: User = Depends(get_current_user),
) -> list[schemas.LeaveTypeRead]:
    return await service.list_leave_types()


@router.post(
    "/types",
    response_model=schemas.LeaveTypeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_type(
    payload: schemas.LeaveTypeCreate,
    service: LeaveService = Depends(get_leave_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.LeaveTypeRead:
    return await service.create_leave_type(payload)


@router.patch("/types/{id}", response_model=schemas.LeaveTypeRead)
async def update_leave_type(
    id: int,
    payload: schemas.LeaveTypeUpdate,
    service: LeaveService = Depends(get_leave_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.LeaveTypeRead:
    return await service.update_leave_type(id, payload)


@router.get("/balance/{employee_id}", response_model=schemas.LeaveBalanceRead)
async def get_leave_balance(
    employee_id: uuid.UUID,
    year: int | None = None,
    service: LeaveService = Depends(get_leave_service),
    current_user: User = Depends(
        require_roles(RoleName.hr, RoleName.manager, RoleName.employee)
    ),
) -> schemas.LeaveBalanceRead:
    return await service.get_leave_balance(
        employee_id=employee_id,
        current_user=current_user,
        year=year,
    )


@router.get("/requests", response_model=schemas.LeaveRequestListResponse)
async def list_leave_requests(
    query: schemas.LeaveRequestListQuery = Depends(),
    service: LeaveService = Depends(get_leave_service),
    current_user: User = Depends(
        require_roles(RoleName.admin, RoleName.hr, RoleName.manager, RoleName.employee)
    ),
) -> schemas.LeaveRequestListResponse:
    return await service.list_leave_requests(
        query=query,
        current_user=current_user,
    )


@router.post(
    "/requests",
    response_model=schemas.LeaveRequestRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_request(
    payload: schemas.LeaveRequestCreate,
    service: LeaveService = Depends(get_leave_service),
    _: User = Depends(require_roles(RoleName.employee)),
    current_employee: Employee = Depends(get_current_employee),
) -> schemas.LeaveRequestRead:
    return await service.create_leave_request(
        employee_id=current_employee.employee_id,
        payload=payload,
    )


@router.get("/requests/{request_id}", response_model=schemas.LeaveRequestRead)
async def get_leave_request(
    request_id: uuid.UUID,
    service: LeaveService = Depends(get_leave_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> schemas.LeaveRequestRead:
    return await service.get_leave_request(request_id)


@router.patch("/requests/{request_id}", response_model=schemas.LeaveRequestRead)
async def update_pending_leave_request(
    request_id: uuid.UUID,
    payload: schemas.LeaveRequestUpdate,
    service: LeaveService = Depends(get_leave_service),
    _: User = Depends(require_roles(RoleName.employee)),
    current_employee: Employee = Depends(get_current_employee),
) -> schemas.LeaveRequestRead:
    return await service.update_pending_leave_request(
        request_id=request_id,
        payload=payload,
        employee_id=current_employee.employee_id,
    )


@router.post("/requests/{request_id}/cancel", response_model=schemas.LeaveRequestRead)
async def cancel_leave_request(
    request_id: uuid.UUID,
    service: LeaveService = Depends(get_leave_service),
    _: User = Depends(require_roles(RoleName.employee)),
    current_employee: Employee = Depends(get_current_employee),
) -> schemas.LeaveRequestRead:
    return await service.cancel_leave_request(
        request_id=request_id,
        employee_id=current_employee.employee_id,
    )


@router.post("/requests/{request_id}/review", response_model=schemas.LeaveRequestRead)
async def review_leave_request(
    request_id: uuid.UUID,
    payload: schemas.ReviewLeaveRequest,
    service: LeaveService = Depends(get_leave_service),
    current_user: User = Depends(require_roles(RoleName.manager, RoleName.hr, RoleName.admin)),
    current_employee: Employee = Depends(get_current_employee),
) -> schemas.LeaveRequestRead:
    return await service.review_leave_request(
        request_id=request_id,
        payload=payload,
        approver_id=current_employee.employee_id,
        reviewer_role=current_user.role_name,
    )


@router.get("/requests/{request_id}/logs", response_model=list[schemas.LeaveApprovalLogRead])
async def list_leave_request_logs(
    request_id: uuid.UUID,
    service: LeaveService = Depends(get_leave_service),
    current_user: User = Depends(
        require_roles(RoleName.admin, RoleName.hr, RoleName.manager, RoleName.employee)
    ),
) -> list[schemas.LeaveApprovalLogRead]:
    return await service.list_leave_request_logs(
        request_id=request_id,
        current_user=current_user,
    )
