from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status

from src.api.v1.features.staff.employees import schemas
from src.api.v1.features.staff.employees.service import EmployeeService, get_employee_service
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import RoleName
from src.api.v1.features.staff.models import Employee
from src.core.dependencies.auth import require_roles, get_current_user_or_rag_api_key, get_current_employee

router = APIRouter(prefix="/employees", tags=["Staff-Employees"])


@router.get("/me", response_model=schemas.EmployeeRead)
async def get_my_employee_profile(
    current_employee: Employee = Depends(get_current_employee),
) -> schemas.EmployeeRead:
    return current_employee


@router.get("/code/{employee_code}", response_model=schemas.EmployeeRead)
async def get_employee_by_code(
    employee_code: str,
    service: EmployeeService = Depends(get_employee_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> schemas.EmployeeRead:
    return await service.get_employee_by_code(employee_code)


@router.get("/{employee_id}", response_model=schemas.EmployeeRead)
async def get_employee( 
    employee_id: uuid.UUID,
    service: EmployeeService = Depends(get_employee_service),
    _: User = Depends(get_current_user_or_rag_api_key),
) -> schemas.EmployeeRead:
    return await service.get_employee(employee_id)


@router.get("/", response_model=dict)
async def list_employees(
    query: schemas.EmployeeListQuery = Depends(),
    service: EmployeeService = Depends(get_employee_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> dict:
    return await service.list_employees(query)


@router.patch("/{employee_id}", response_model=schemas.EmployeeRead)
async def update_employee(
    employee_id: uuid.UUID,
    payload: schemas.EmployeeUpdate,
    service: EmployeeService = Depends(get_employee_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeRead:
    return await service.update_employee(employee_id, payload)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: uuid.UUID,
    service: EmployeeService = Depends(get_employee_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> Response:
    await service.delete_employee(employee_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/activate/{employee_id}", response_model=schemas.EmployeeRead)
async def activate_employee(
    employee_id: uuid.UUID,
    service: EmployeeService = Depends(get_employee_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr)),
) -> schemas.EmployeeRead:
    return await service.activate_employee(employee_id)
