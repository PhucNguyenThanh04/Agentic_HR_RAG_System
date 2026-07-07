from fastapi import APIRouter, Depends, Response, status

from src.api.v1.features.staff.position import schemas
from src.api.v1.features.staff.position.service import PositionService, get_position_service
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import RoleName
from src.core.dependencies.auth import require_roles

router = APIRouter(prefix="/positions", tags=["Staff-Positions"])


@router.post("/", response_model=schemas.PositionRead, status_code=status.HTTP_201_CREATED)
async def create_position(
    payload: schemas.PositionCreate,
    service: PositionService = Depends(get_position_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.PositionRead:
    return await service.create_position(payload)


@router.get("/code/{code}", response_model=schemas.PositionRead)
async def get_position_by_code(
    code: str,
    service: PositionService = Depends(get_position_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> schemas.PositionRead:
    return await service.get_position_by_code(code)


@router.get("/{position_id}", response_model=schemas.PositionRead)
async def get_position(
    position_id: int,
    service: PositionService = Depends(get_position_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> schemas.PositionRead:
    return await service.get_position_by_id(position_id)


@router.get("/", response_model=list[schemas.PositionRead])
async def list_positions(
    search: str | None = None,
    is_active: bool | None = None,
    service: PositionService = Depends(get_position_service),
    _: User = Depends(require_roles(RoleName.admin, RoleName.hr, RoleName.manager)),
) -> list[schemas.PositionRead]:
    return await service.list(search=search, is_active=is_active)


@router.patch("/{position_id}", response_model=schemas.PositionRead)
async def update_position(
    position_id: int,
    payload: schemas.PositionUpdate,
    service: PositionService = Depends(get_position_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.PositionRead:
    return await service.update_position(position_id, payload)


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(
    position_id: int,
    service: PositionService = Depends(get_position_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> Response:
    await service.delete_position(position_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/deactivate/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_position(
    position_id: int,
    service: PositionService = Depends(get_position_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> Response:
    await service.deactivate_position(position_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
