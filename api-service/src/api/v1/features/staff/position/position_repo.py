from fastapi import Depends
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.features.staff.models import Position
from src.api.v1.features.staff.position import schemas
from src.core.db.database import get_db
from src.utils.exeptions import ConflictException, DatabaseException, NotFoundException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class PositionRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    async def code_exists(self, code: str | None, exclude_position_id: int | None = None) -> bool:
        normalized_code = self._normalize_optional(code)
        if normalized_code is None:
            return False

        stmt = select(Position.position_id).where(Position.code == normalized_code)
        if exclude_position_id is not None:
            stmt = stmt.where(Position.position_id != exclude_position_id)
        return (await self.db.execute(stmt)).first() is not None

    async def name_exists(self, name: str | None, exclude_position_id: int | None = None) -> bool:
        normalized_name = self._normalize_optional(name)
        if normalized_name is None:
            return False

        stmt = select(Position.position_id).where(
            func.lower(Position.name) == normalized_name.lower()
        )
        if exclude_position_id is not None:
            stmt = stmt.where(Position.position_id != exclude_position_id)
        return (await self.db.execute(stmt)).first() is not None

    async def get_position_by_id(self, position_id: int) -> Position | None:
        return await self.db.scalar(select(Position).where(Position.position_id == position_id))

    async def get_position_or_404(self, position_id: int) -> Position:
        position = await self.get_position_by_id(position_id)
        if position is None:
            raise NotFoundException("Position")
        return position

    async def get_position_by_code(self, code: str) -> Position | None:
        return await self.db.scalar(select(Position).where(Position.code == code.strip()))

    async def list_positions(
        self,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> list[Position]:
        stmt: Select = select(Position)
        if is_active is not None:
            stmt = stmt.where(Position.is_active.is_(is_active))
        if search:
            term = search.strip().lower()
            if term:
                stmt = stmt.where(func.lower(Position.name).like(f"%{term}%"))
        result = await self.db.execute(stmt.order_by(Position.name))
        return list(result.scalars().all())

    async def create_position(
        self,
        name: str,
        code: str | None,
        description: str | None = None,
        is_active: bool = True,
    ) -> Position:
        normalized_name = name.strip()
        normalized_code = self._normalize_optional(code)

        if await self.name_exists(normalized_name):
            raise ConflictException("Position name already exists")
        if await self.code_exists(normalized_code):
            raise ConflictException("Position code already exists")

        position = Position(
            name=normalized_name,
            code=normalized_code,
            description=description,
            is_active=is_active,
        )
        self.db.add(position)
        try:
            await self.db.commit()
            await self.db.refresh(position)
            return position
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create position: name=%s code=%s",
                normalized_name,
                normalized_code,
            )
            raise DatabaseException("Failed to create position") from exc

    async def update_position(self, position_id: int, payload: schemas.PositionUpdate) -> Position:
        position = await self.get_position_or_404(position_id)
        changed = False

        if payload.name is not None:
            normalized_name = payload.name.strip()
            if normalized_name != position.name:
                if await self.name_exists(normalized_name, exclude_position_id=position_id):
                    raise ConflictException("Position name already exists")
                position.name = normalized_name
                changed = True

        if payload.code is not None:
            normalized_code = payload.code.strip()
            if normalized_code != position.code:
                if await self.code_exists(normalized_code, exclude_position_id=position_id):
                    raise ConflictException("Position code already exists")
                position.code = normalized_code
                changed = True
        elif "code" in payload.model_fields_set and position.code is not None:
            position.code = None
            changed = True

        if payload.description is not None and payload.description != position.description:
            position.description = payload.description
            changed = True

        if payload.is_active is not None and payload.is_active != position.is_active:
            position.is_active = payload.is_active
            changed = True

        if changed:
            try:
                await self.db.commit()
            except Exception as exc:
                await self.db.rollback()
                logger.exception(
                    "Failed to update position: position_id=%s",
                    position_id,
                )
                raise DatabaseException("Failed to update position") from exc

        updated = await self.get_position_by_id(position_id)
        if updated is None:
            raise DatabaseException("Failed to reload updated position")
        return updated

    async def delete_position(self, position_id: int) -> None:
        position = await self.get_position_or_404(position_id)

        try:
            await self.db.delete(position)
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to delete position: position_id=%s",
                position_id,
            )
            raise DatabaseException("Failed to delete position") from exc

    async def deactivate_position(self, position_id: int) -> Position:
        position = await self.get_position_or_404(position_id)

        if not position.is_active:
            return position

        position.is_active = False
        try:
            await self.db.commit()
            await self.db.refresh(position)
            return position
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to deactivate position: position_id=%s",
                position_id,
            )
            raise DatabaseException("Failed to deactivate position") from exc


def get_position_repo(db: AsyncSession = Depends(get_db)) -> PositionRepo:
    return PositionRepo(db)
