from fastapi import Depends

from src.api.v1.features.staff.position import schemas
from src.api.v1.features.staff.position.position_repo import PositionRepo, get_position_repo
from src.utils.exeptions import ConflictException, NotFoundException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class PositionService:
    def __init__(self, position_repo: PositionRepo):
        self.position_repo = position_repo

    @staticmethod
    def _to_read(position) -> schemas.PositionRead:
        return schemas.PositionRead.model_validate(position)

    async def create_position(self, payload: schemas.PositionCreate) -> schemas.PositionRead:
        logger.info("Create position request: name=%s code=%s", payload.name, payload.code)
        if await self.position_repo.code_exists(code=payload.code):
            logger.warning("Create position conflict: code=%s", payload.code)
            raise ConflictException("Position code already exists")
        if await self.position_repo.name_exists(name=payload.name):
            logger.warning("Create position conflict: name=%s", payload.name)
            raise ConflictException("Position name already exists")

        position = await self.position_repo.create_position(
            name=payload.name,
            code=payload.code,
            description=payload.description,
            is_active=payload.is_active,
        )
        logger.info(
            "Position created: position_id=%s name=%s",
            position.position_id,
            position.name,
        )
        return self._to_read(position)

    async def get_position_by_id(self, position_id: int) -> schemas.PositionRead:
        position = await self.position_repo.get_position_by_id(position_id)
        if position is None:
            logger.warning("Position not found by id: position_id=%s", position_id)
            raise NotFoundException("Position")
        return self._to_read(position)

    async def list(
        self,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> list[schemas.PositionRead]:
        positions = await self.position_repo.list_positions(
            search=search,
            is_active=is_active,
        )
        logger.info(
            "List positions: search=%s is_active=%s count=%s",
            search,
            is_active,
            len(positions),
        )
        return [self._to_read(position) for position in positions]

    async def update_position(self, position_id: int, payload: schemas.PositionUpdate) -> schemas.PositionRead:
        position = await self.position_repo.get_position_by_id(position_id)
        if position is None:
            logger.warning("Update position not found: position_id=%s", position_id)
            raise NotFoundException("Position")

        if payload.code and await self.position_repo.code_exists(
            code=payload.code,
            exclude_position_id=position_id,
        ):
            logger.warning(
                "Update position conflict code: position_id=%s code=%s",
                position_id,
                payload.code,
            )
            raise ConflictException("Position code already exists")
        if payload.name and await self.position_repo.name_exists(
            name=payload.name,
            exclude_position_id=position_id,
        ):
            logger.warning(
                "Update position conflict name: position_id=%s name=%s",
                position_id,
                payload.name,
            )
            raise ConflictException("Position name already exists")

        updated_position = await self.position_repo.update_position(
            position_id=position_id,
            payload=payload,
        )
        logger.info("Position updated: position_id=%s", position_id)
        return self._to_read(updated_position)

    async def delete_position(self, position_id: int) -> None:
        position = await self.position_repo.get_position_by_id(position_id)
        if position is None:
            logger.warning("Delete position not found: position_id=%s", position_id)
            raise NotFoundException("Position")

        await self.position_repo.delete_position(position_id)
        logger.info("Position deleted: position_id=%s", position_id)

    async def deactivate_position(self, position_id: int) -> None:
        position = await self.position_repo.get_position_by_id(position_id)
        if position is None:
            logger.warning("Deactivate position not found: position_id=%s", position_id)
            raise NotFoundException("Position")

        await self.position_repo.deactivate_position(position_id)
        logger.info("Position deactivated: position_id=%s", position_id)

    async def get_position_by_code(self, code: str) -> schemas.PositionRead:
        position = await self.position_repo.get_position_by_code(code)
        if position is None:
            logger.warning("Position not found by code: code=%s", code)
            raise NotFoundException("Position")
        return self._to_read(position)


def get_position_service(
    position_repo: PositionRepo = Depends(get_position_repo),
) -> PositionService:
    return PositionService(position_repo=position_repo)
