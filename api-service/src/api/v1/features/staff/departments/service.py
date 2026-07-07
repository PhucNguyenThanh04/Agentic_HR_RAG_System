from fastapi import Depends

from src.api.v1.features.staff.departments import schemas
from src.api.v1.features.staff.departments.department_repo import (
    DepartmentRepo,
    get_department_repo,
)
from src.utils.exeptions import ConflictException, NotFoundException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class DepartmentService:
    def __init__(self, department_repo: DepartmentRepo):
        self.department_repo = department_repo

    @staticmethod
    def _to_read(department) -> schemas.DepartmentRead:
        return schemas.DepartmentRead.model_validate(department)

    async def create_department(self, payload: schemas.DepartmentCreate) -> schemas.DepartmentRead:
        logger.info(
            "Create department request: name=%s code=%s",
            payload.name,
            payload.code,
        )
        if await self.department_repo.code_exists(code=payload.code):
            logger.warning("Create department conflict: code=%s", payload.code)
            raise ConflictException("Department code already exists")
        if await self.department_repo.name_exists(name=payload.name):
            logger.warning("Create department conflict: name=%s", payload.name)
            raise ConflictException("Department name already exists")

        department = await self.department_repo.create_department(
            name=payload.name,
            code=payload.code,
            description=payload.description,
            is_active=payload.is_active,
        )
        logger.info(
            "Department created: department_id=%s name=%s",
            department.department_id,
            department.name,
        )
        return self._to_read(department)

    async def get_department_by_id(self, department_id: int) -> schemas.DepartmentRead:
        department = await self.department_repo.get_department_by_id(department_id)
        if department is None:
            logger.warning("Department not found by id: department_id=%s", department_id)
            raise NotFoundException("Department")
        return self._to_read(department)

    async def get_department_by_code(self, code: str) -> schemas.DepartmentRead:
        department = await self.department_repo.get_department_by_code(code)
        if department is None:
            logger.warning("Department not found by code: code=%s", code)
            raise NotFoundException("Department")
        return self._to_read(department)

    async def list(
        self,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> list[schemas.DepartmentRead]:
        departments = await self.department_repo.list_departments(
            search=search,
            is_active=is_active,
        )
        logger.info(
            "List departments: search=%s is_active=%s count=%s",
            search,
            is_active,
            len(departments),
        )
        return [self._to_read(department) for department in departments]

    async def update_department(
        self,
        department_id: int,
        payload: schemas.DepartmentUpdate,
    ) -> schemas.DepartmentRead:
        department = await self.department_repo.get_department_by_id(department_id)
        if department is None:
            logger.warning("Update department not found: department_id=%s", department_id)
            raise NotFoundException("Department")

        if payload.code and await self.department_repo.code_exists(
            code=payload.code,
            exclude_department_id=department_id,
        ):
            logger.warning(
                "Update department conflict code: department_id=%s code=%s",
                department_id,
                payload.code,
            )
            raise ConflictException("Department code already exists")
        if payload.name and await self.department_repo.name_exists(
            name=payload.name,
            exclude_department_id=department_id,
        ):
            logger.warning(
                "Update department conflict name: department_id=%s name=%s",
                department_id,
                payload.name,
            )
            raise ConflictException("Department name already exists")

        updated_department = await self.department_repo.update_department(
            department_id=department_id,
            payload=payload,
        )
        logger.info("Department updated: department_id=%s", department_id)
        return self._to_read(updated_department)

    async def delete_department(self, department_id: int) -> None:
        department = await self.department_repo.get_department_by_id(department_id)
        if department is None:
            logger.warning("Delete department not found: department_id=%s", department_id)
            raise NotFoundException("Department")

        await self.department_repo.delete_department(department_id)
        logger.info("Department deleted: department_id=%s", department_id)

    async def deactivate_department(self, department_id: int) -> None:
        department = await self.department_repo.get_department_by_id(department_id)
        if department is None:
            logger.warning("Deactivate department not found: department_id=%s", department_id)
            raise NotFoundException("Department")

        await self.department_repo.deactivate_department(department_id)
        logger.info("Department deactivated: department_id=%s", department_id)


def get_department_service(
    department_repo: DepartmentRepo = Depends(get_department_repo),
) -> DepartmentService:
    return DepartmentService(department_repo=department_repo)
