from fastapi import Depends
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.features.staff.departments import schemas
from src.api.v1.features.staff.models import Department
from src.core.db.database import get_db
from src.utils.exeptions import ConflictException, DatabaseException, NotFoundException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class DepartmentRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    async def code_exists(self, code: str | None, exclude_department_id: int | None = None) -> bool:
        normalized_code = self._normalize_optional(code)
        if normalized_code is None:
            return False

        stmt = select(Department.department_id).where(Department.code == normalized_code)
        if exclude_department_id is not None:
            stmt = stmt.where(Department.department_id != exclude_department_id)
        return (await self.db.execute(stmt)).first() is not None

    async def name_exists(self, name: str | None, exclude_department_id: int | None = None) -> bool:
        normalized_name = self._normalize_optional(name)
        if normalized_name is None:
            return False

        stmt = select(Department.department_id).where(
            func.lower(Department.name) == normalized_name.lower()
        )
        if exclude_department_id is not None:
            stmt = stmt.where(Department.department_id != exclude_department_id)
        return (await self.db.execute(stmt)).first() is not None

    async def get_department_by_id(self, department_id: int) -> Department | None:
        return await self.db.scalar(
            select(Department).where(Department.department_id == department_id)
        )

    async def get_department_or_404(self, department_id: int) -> Department:
        department = await self.get_department_by_id(department_id)
        if department is None:
            raise NotFoundException("Department")
        return department

    async def get_department_by_code(self, code: str) -> Department | None:
        return await self.db.scalar(select(Department).where(Department.code == code.strip()))

    async def list_departments(
        self,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> list[Department]:
        stmt: Select = select(Department)
        if is_active is not None:
            stmt = stmt.where(Department.is_active.is_(is_active))
        if search:
            term = search.strip().lower()
            if term:
                stmt = stmt.where(func.lower(Department.name).like(f"%{term}%"))
        result = await self.db.execute(stmt.order_by(Department.name))
        return list(result.scalars().all())

    async def create_department(
        self,
        name: str,
        code: str | None,
        description: str | None = None,
        is_active: bool = True,
    ) -> Department:
        normalized_name = name.strip()
        normalized_code = self._normalize_optional(code)

        if await self.name_exists(normalized_name):
            raise ConflictException("Department name already exists")
        if await self.code_exists(normalized_code):
            raise ConflictException("Department code already exists")

        department = Department(
            name=normalized_name,
            code=normalized_code,
            description=description,
            is_active=is_active,
        )
        self.db.add(department)
        try:
            await self.db.commit()
            await self.db.refresh(department)
            return department
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create department: name=%s code=%s",
                normalized_name,
                normalized_code,
            )
            raise DatabaseException("Failed to create department") from exc

    async def update_department(
        self,
        department_id: int,
        payload: schemas.DepartmentUpdate,
    ) -> Department:
        department = await self.get_department_or_404(department_id)
        changed = False

        if payload.name is not None:
            normalized_name = payload.name.strip()
            if normalized_name != department.name:
                if await self.name_exists(
                    normalized_name,
                    exclude_department_id=department_id,
                ):
                    raise ConflictException("Department name already exists")
                department.name = normalized_name
                changed = True

        if payload.code is not None:
            normalized_code = payload.code.strip()
            if normalized_code != department.code:
                if await self.code_exists(
                    normalized_code,
                    exclude_department_id=department_id,
                ):
                    raise ConflictException("Department code already exists")
                department.code = normalized_code
                changed = True
        elif "code" in payload.model_fields_set and department.code is not None:
            department.code = None
            changed = True

        if payload.description is not None and payload.description != department.description:
            department.description = payload.description
            changed = True

        if payload.is_active is not None and payload.is_active != department.is_active:
            department.is_active = payload.is_active
            changed = True

        if changed:
            try:
                await self.db.commit()
            except Exception as exc:
                await self.db.rollback()
                logger.exception(
                    "Failed to update department: department_id=%s",
                    department_id,
                )
                raise DatabaseException("Failed to update department") from exc

        updated = await self.get_department_by_id(department_id)
        if updated is None:
            raise DatabaseException("Failed to reload updated department")
        return updated

    async def delete_department(self, department_id: int) -> None:
        department = await self.get_department_or_404(department_id)
        try:
            await self.db.delete(department)
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to delete department: department_id=%s",
                department_id,
            )
            raise DatabaseException("Failed to delete department") from exc

    async def deactivate_department(self, department_id: int) -> Department:
        department = await self.get_department_or_404(department_id)
        if not department.is_active:
            return department

        department.is_active = False
        try:
            await self.db.commit()
            await self.db.refresh(department)
            return department
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to deactivate department: department_id=%s",
                department_id,
            )
            raise DatabaseException("Failed to deactivate department") from exc


def get_department_repo(db: AsyncSession = Depends(get_db)) -> DepartmentRepo:
    return DepartmentRepo(db)
