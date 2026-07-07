from fastapi import APIRouter, Depends, Response, status

from src.api.v1.features.staff.departments import schemas
from src.api.v1.features.staff.departments.service import (
    DepartmentService,
    get_department_service,
)
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import RoleName
from src.core.dependencies.auth import require_roles

router = APIRouter(prefix="/departments", tags=["Staff-Departments"])


@router.post("/", response_model=schemas.DepartmentRead, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: schemas.DepartmentCreate,
    service: DepartmentService = Depends(get_department_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.DepartmentRead:
    return await service.create_department(payload)


@router.get("/code/{code}", response_model=schemas.DepartmentRead)
async def get_department_by_code(
    code: str,
    service: DepartmentService = Depends(get_department_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> schemas.DepartmentRead:
    return await service.get_department_by_code(code)


@router.get("/{department_id}", response_model=schemas.DepartmentRead)
async def get_department(
    department_id: int,
    service: DepartmentService = Depends(get_department_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> schemas.DepartmentRead:
    return await service.get_department_by_id(department_id)


@router.get("/", response_model=list[schemas.DepartmentRead])
async def list_departments(
    search: str | None = None,
    is_active: bool | None = None,
    service: DepartmentService = Depends(get_department_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> list[schemas.DepartmentRead]:
    return await service.list(search=search, is_active=is_active)


@router.patch("/{department_id}", response_model=schemas.DepartmentRead)
async def update_department(
    department_id: int,
    payload: schemas.DepartmentUpdate,
    service: DepartmentService = Depends(get_department_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.DepartmentRead:
    return await service.update_department(department_id, payload)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: int,
    service: DepartmentService = Depends(get_department_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> Response:
    await service.delete_department(department_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/deactivate/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_department(
    department_id: int,
    service: DepartmentService = Depends(get_department_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> Response:
    await service.deactivate_department(department_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
